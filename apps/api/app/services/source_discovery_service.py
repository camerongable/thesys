import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any
from urllib.parse import quote_plus

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import (
    SOURCE_DISCOVERY_PROMPT_VERSION,
    UNTRUSTED_RETRIEVED_CONTENT_RULE,
)
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
from app.db.models import AIRun, AIStep, DiscoveredSource, ResearchSprint
from app.schemas.research import SourceDiscoveryDraft
from app.services import (
    ai_run_service,
    evidence_service,
    external_search_service,
    langsmith_observability_service,
    project_service,
)


@dataclass(frozen=True)
class SourceDiscoveryResult:
    run: AIRun
    step: AIStep
    generated_count: int
    candidate_count: int
    search_diagnostics: dict[str, Any]
    sources: list[DiscoveredSource]


def list_discovered_sources(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> list[DiscoveredSource]:
    _get_sprint(db, auth, project_id, sprint_id)
    return _list_sources(db, auth, project_id, sprint_id)


def discover_sources(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> SourceDiscoveryResult:
    require_permission(auth, "run_research")
    project = project_service.get_project(db, auth, project_id)
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if sprint.status not in {"approved", "running", "needs_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the research plan before discovering sources.",
        )

    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="source_discovery",
        prompt_version=SOURCE_DISCOVERY_PROMPT_VERSION,
        input_summary=sprint.plan.objective[:500],
        project_id=project_id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    trace = langsmith_observability_service.ensure_research_sprint_trace(
        db,
        auth,
        settings,
        project,
        sprint,
        workflow_version=SOURCE_DISCOVERY_PROMPT_VERSION,
        model_provider=run.model_provider,
        model_name=run.model_name,
        run=run,
    )
    messages = _source_discovery_messages(sprint)
    step = ai_run_service.start_step(
        db,
        run,
        step_name="generate_source_candidates",
        input_json={
            "schema": SourceDiscoveryDraft.__name__,
            "research_sprint_id": str(sprint.id),
            "research_plan_id": str(sprint.plan.id),
            "market_queries": sprint.plan.market_queries,
            "competitor_queries": sprint.plan.competitor_queries,
            "substitute_queries": sprint.plan.substitute_queries,
            "source_types": sprint.plan.source_types,
            "messages": [message.model_dump() for message in messages],
        },
    )
    started = perf_counter()
    try:
        if settings.external_search_enabled:
            search_batch = external_search_service.search_many(
                settings,
                _search_queries_for_sprint(sprint),
            )
            draft = SourceDiscoveryDraft(sources=[])
            completion = _external_search_completion(settings, messages, search_batch)
            specs = _candidate_specs_from_search(search_batch)
            search_diagnostics = external_search_service.diagnostics(search_batch)
        else:
            draft, completion = _generate_source_draft(settings, sprint, messages)
            specs = _candidate_specs_from_draft(draft)
            search_diagnostics = {
                "enabled": False,
                "provider": settings.external_search_provider,
                "query_count": 0,
                "result_count": 0,
                "deduped_count": 0,
                "fallback_used": False,
                "fallback_reason": None,
            }
        generated_count = len(specs)
        existing_by_url = {
            _normalize_url(source.url): source
            for source in _list_sources(db, auth, project_id, sprint_id)
        }
        for spec in specs:
            key = _normalize_url(spec["url"])
            if key in existing_by_url:
                continue
            source = DiscoveredSource(
                workspace_id=auth.workspace_id,
                project_id=project_id,
                research_sprint_id=sprint.id,
                url=spec["url"],
                title=spec["title"],
                snippet=spec["snippet"],
                source_type=spec["source_type"],
                relevance_score=spec["relevance_score"],
                reason_selected=spec["reason_selected"],
                associated_research_question=spec["associated_research_question"],
                search_provider=spec.get("search_provider"),
                search_query=spec.get("search_query"),
                search_result_rank=spec.get("search_result_rank"),
                retrieved_at=spec.get("retrieved_at"),
                risk_level=spec.get("risk_level") or "medium",
                provenance_metadata=spec.get("provenance_metadata") or {},
                status="candidate",
                created_by=auth.user_id,
            )
            db.add(source)
            existing_by_url[key] = source

        if sprint.status == "approved":
            sprint.status = "running"
            sprint.started_at = sprint.started_at or datetime.now(UTC)
        db.commit()
        sources = _list_sources(db, auth, project_id, sprint_id)
        step = ai_run_service.complete_step(
            db,
            step,
            output_json={
                "generated_count": generated_count,
                "candidate_count": len(sources),
                "source_ids": [str(source.id) for source in sources],
                "search_diagnostics": search_diagnostics,
                "used_stub": completion.used_stub,
                "model_provider": completion.model_provider,
                "model_name": completion.model_name,
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
        langsmith_observability_service.record_step_span(
            db,
            settings,
            run=run,
            step=step,
            trace=trace,
            span_name="source_discovery",
            input_json=step.input_json,
            output_json=step.output_json,
            run_type="llm" if completion.model_provider != "stub" else "chain",
        )
        run = ai_run_service.complete_run(
            db,
            run,
            output_summary=f"Generated {len(sources)} source candidates.",
            total_tokens=completion.total_tokens,
            total_cost=completion.total_cost,
            model_provider=completion.model_provider,
            model_name=completion.model_name,
        )
        return SourceDiscoveryResult(
            run=run,
            step=step,
            generated_count=generated_count,
            candidate_count=len(sources),
            search_diagnostics=search_diagnostics,
            sources=sources,
        )
    except Exception as exc:
        db.rollback()
        ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        langsmith_observability_service.record_step_span(
            db,
            settings,
            run=run,
            step=step,
            trace=trace,
            span_name="source_discovery",
            input_json=step.input_json,
            error=str(exc),
        )
        ai_run_service.fail_run(db, run, error=str(exc))
        raise


def approve_source_candidate(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    source_id: uuid.UUID,
) -> DiscoveredSource:
    require_permission(auth, "run_research")
    return ingest_source_candidate(db, auth, settings, project_id, sprint_id, source_id)


def ingest_source_candidate(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    source_id: uuid.UUID,
) -> DiscoveredSource:
    require_permission(auth, "run_research")
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    source = _get_source(db, auth, project_id, sprint_id, source_id)
    if source.status == "ingested":
        return source
    if source.status not in {"candidate", "approved", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only candidate, approved, or failed sources can be ingested.",
        )
    source.status = "approved"
    source.ingestion_error = None
    db.commit()
    try:
        evidence = evidence_service.add_discovered_url_source(
            db,
            auth,
            settings,
            project_id,
            url=source.url,
            title=source.title,
            fallback_text=_snapshot_text(source),
            metadata=_source_evidence_metadata(source, sprint),
        )
    except evidence_service.EvidenceIngestionError as exc:
        source = _get_source(db, auth, project_id, sprint_id, source_id)
        source.status = "failed"
        source.ingestion_error = str(exc)[:2000]
        db.commit()
        db.refresh(source)
        return source

    source = _get_source(db, auth, project_id, sprint_id, source_id)
    source.evidence_source_id = evidence.id
    source.status = "ingested"
    source.ingested_at = evidence.ingested_at or datetime.now(UTC)
    source.ingestion_error = None
    db.commit()
    db.refresh(source)
    return source


def reject_source_candidate(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    source_id: uuid.UUID,
) -> DiscoveredSource:
    require_permission(auth, "run_research")
    source = _get_source(db, auth, project_id, sprint_id, source_id)
    if source.status not in {"candidate", "approved", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only unfinalized sources can be rejected.",
        )
    source.status = "rejected"
    db.commit()
    db.refresh(source)
    return source


def _get_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> ResearchSprint:
    project_service.get_project(db, auth, project_id)
    sprint = db.scalar(
        select(ResearchSprint)
        .where(
            ResearchSprint.id == sprint_id,
            ResearchSprint.workspace_id == auth.workspace_id,
            ResearchSprint.project_id == project_id,
        )
        .options(selectinload(ResearchSprint.plan))
    )
    if sprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research sprint not found.",
        )
    return sprint


def _list_sources(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> list[DiscoveredSource]:
    return list(
        db.scalars(
            select(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
                DiscoveredSource.research_sprint_id == sprint_id,
            )
            .order_by(DiscoveredSource.relevance_score.desc(), DiscoveredSource.created_at)
        )
    )


def _get_source(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    source_id: uuid.UUID,
) -> DiscoveredSource:
    source = db.scalar(
        select(DiscoveredSource).where(
            DiscoveredSource.id == source_id,
            DiscoveredSource.workspace_id == auth.workspace_id,
            DiscoveredSource.project_id == project_id,
            DiscoveredSource.research_sprint_id == sprint_id,
        )
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discovered source not found.",
    )
    return source


def _generate_source_draft(
    settings: Settings,
    sprint: ResearchSprint,
    messages: list[ChatMessage],
) -> tuple[SourceDiscoveryDraft, LLMCompletion]:
    if settings.should_use_llm_stub or should_use_fallback_without_model(settings):
        draft = SourceDiscoveryDraft(sources=_fallback_candidate_specs(sprint)[:12])
        return draft, _fallback_completion(
            settings,
            messages,
            draft,
            "stub" if settings.should_use_llm_stub else "policy_always",
        )

    try:
        result = generate_structured_output(
            settings,
            SourceDiscoveryDraft,
            messages,
            model=settings.litellm_model,
            temperature=0.1,
            max_tokens=3500,
        )
        return SourceDiscoveryDraft.model_validate(result.parsed), result.completion
    except (StructuredOutputError, RuntimeError) as exc:
        if not should_use_fallback_after_error(settings):
            raise
        draft = SourceDiscoveryDraft(sources=_fallback_candidate_specs(sprint)[:12])
        return draft, _fallback_completion(settings, messages, draft, "emergency", exc)


def _source_discovery_messages(sprint: ResearchSprint) -> list[ChatMessage]:
    plan = sprint.plan
    payload = {
        "objective": plan.objective,
        "target_customer_hypotheses": plan.target_customer_hypotheses,
        "research_questions": plan.research_questions,
        "competitor_queries": plan.competitor_queries,
        "market_queries": plan.market_queries,
        "substitute_queries": plan.substitute_queries,
        "requested_source_types": plan.source_types,
        "max_candidates": 10,
    }
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a source discovery planner for a founder strategy workspace. "
                "Generate candidate public sources for a human to review before ingestion. "
                "Do not claim that you browsed the web. Prefer high-signal primary pages, "
                "pricing pages, review directories, forums, market reports, and specific "
                "search-result URLs when a concrete source is uncertain. Each candidate must "
                "explain why it is worth reviewing and which research question it supports. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE}"
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Create a ranked source candidate list from this approved research plan. "
                "Return only the structured JSON.\n\n"
                f"{json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}"
            ),
        ),
    ]


def _candidate_specs_from_draft(draft: SourceDiscoveryDraft) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for source in draft.sources:
        url = _clean_url(source.url)
        if not url:
            continue
        specs.append(
            {
                "url": url,
                "title": source.title[:500] if source.title else None,
                "snippet": source.snippet,
                "source_type": source.source_type,
                "relevance_score": _clamp_score(source.relevance_score),
                "reason_selected": source.reason_selected,
                "associated_research_question": source.associated_research_question,
            }
        )
    return _dedupe_specs(specs)


def _candidate_specs_from_search(
    batch: external_search_service.ExternalSearchBatch,
) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for result in batch.results:
        url = _clean_url(result.url)
        if not url:
            continue
        source_type = _infer_source_type(
            result.url,
            result.title,
            result.snippet,
            result.metadata.get("source_type_hint"),
        )
        specs.append(
            {
                "url": url,
                "title": result.title[:500] if result.title else None,
                "snippet": result.snippet,
                "source_type": source_type,
                "relevance_score": _clamp_score(result.score),
                "reason_selected": (
                    "External search result selected for human review before ingestion."
                ),
                "associated_research_question": result.query,
                "search_provider": result.provider,
                "search_query": result.query,
                "search_result_rank": result.rank,
                "retrieved_at": result.retrieved_at,
                "risk_level": _risk_level(source_type),
                "provenance_metadata": {
                    "search_provider": result.provider,
                    "search_query": result.query,
                    "search_result_rank": result.rank,
                    "retrieved_at": result.retrieved_at.isoformat(),
                    "search_score": str(result.score),
                    **result.metadata,
                },
            }
        )
    return _dedupe_specs(specs)


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    draft: SourceDiscoveryDraft,
    fallback_name: str,
    error: BaseException | None = None,
) -> LLMCompletion:
    content = draft.model_dump_json()
    prompt_tokens = sum(len(message.content.split()) for message in messages)
    completion_tokens = len(content.split())
    return LLMCompletion(
        content=content,
        model_provider="stub" if settings.should_use_llm_stub else "local-fallback",
        model_name=(
            f"deterministic-dev-stub:{settings.litellm_model}"
            if settings.should_use_llm_stub
            else settings.litellm_model
        ),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        total_cost=Decimal("0"),
        raw_response={
            "fallback": f"source_discovery_{fallback_name}",
            "error": str(error)[:500] if error is not None else None,
        },
        used_stub=True,
    )


def _external_search_completion(
    settings: Settings,
    messages: list[ChatMessage],
    batch: external_search_service.ExternalSearchBatch,
) -> LLMCompletion:
    content = json.dumps(
        {
            "provider": batch.provider,
            "query_count": batch.query_count,
            "result_count": batch.result_count,
        },
        ensure_ascii=True,
    )
    prompt_tokens = sum(len(message.content.split()) for message in messages)
    completion_tokens = len(content.split())
    return LLMCompletion(
        content=content,
        model_provider=batch.provider,
        model_name=f"{batch.provider}:external-search",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        total_cost=Decimal("0"),
        raw_response={
            "external_search": True,
            "provider": batch.provider,
            "query_count": batch.query_count,
            "result_count": batch.result_count,
            "fallback_used": batch.fallback_used,
            "fallback_reason": batch.fallback_reason,
        },
        used_stub=batch.provider == "deterministic",
    )


def _fallback_candidate_specs(sprint: ResearchSprint) -> list[dict[str, Any]]:
    plan = sprint.plan
    queries = _ordered_queries(
        [
            *plan.market_queries,
            *plan.competitor_queries,
            *plan.substitute_queries,
            *plan.research_questions,
        ]
    )
    if not queries:
        queries = [plan.objective]

    specs: list[dict[str, Any]] = []
    for index, query in enumerate(queries[:8]):
        score_base = max(Decimal("0.95") - Decimal(index) * Decimal("0.03"), Decimal("0.62"))
        specs.extend(
            [
                _spec(
                    query,
                    "directory",
                    f"https://www.g2.com/search?query={quote_plus(query)}",
                    f"G2 search for {query}",
                    score_base,
                    "Directory pages can reveal named competitors, categories, and review "
                    "patterns.",
                ),
                _spec(
                    query,
                    "forum",
                    f"https://www.reddit.com/search/?q={quote_plus(query)}",
                    f"Reddit discussions for {query}",
                    score_base - Decimal("0.04"),
                    "Forum threads can reveal customer pain, substitutes, and language users use.",
                ),
                _spec(
                    query,
                    "market_report",
                    f"https://www.google.com/search?q={quote_plus(query + ' market report')}",
                    f"Market report search for {query}",
                    score_base - Decimal("0.08"),
                    "Market landscape sources can help calibrate category maturity and trends.",
                ),
            ]
        )

    for query in plan.competitor_queries[:4]:
        specs.append(
            _spec(
                query,
                "pricing_page",
                f"https://www.google.com/search?q={quote_plus(query + ' pricing')}",
                f"Pricing page search for {query}",
                Decimal("0.81"),
                "Pricing pages help test willingness-to-pay and packaging assumptions.",
            )
        )
    return _dedupe_specs(specs)


def _spec(
    query: str,
    source_type: str,
    url: str,
    title: str,
    score: Decimal,
    reason: str,
) -> dict[str, Any]:
    clean_query = " ".join(query.split())
    return {
        "url": url,
        "title": title[:500],
        "snippet": f"Candidate public source to inspect for: {clean_query}",
        "source_type": source_type,
        "relevance_score": max(min(score, Decimal("1.00")), Decimal("0.00")),
        "reason_selected": reason,
        "associated_research_question": clean_query,
    }


def _ordered_queries(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = " ".join(str(value).split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            ordered.append(cleaned)
            seen.add(key)
    return ordered


def _search_queries_for_sprint(sprint: ResearchSprint) -> list[str]:
    plan = sprint.plan
    queries = _ordered_queries(
        [
            *plan.competitor_queries,
            *plan.substitute_queries,
            *plan.market_queries,
            *plan.research_questions,
        ]
    )
    return queries or [plan.objective]


def _dedupe_specs(specs: list[dict[str, object]]) -> list[dict[str, object]]:
    by_url: dict[str, dict[str, object]] = {}
    for spec in specs:
        key = _normalize_url(str(spec["url"]))
        if key not in by_url:
            by_url[key] = spec
    return list(by_url.values())


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").casefold()


def _clean_url(url: str) -> str:
    cleaned = " ".join(url.split())
    if not cleaned:
        return ""
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://www.google.com/search?q={quote_plus(cleaned)}"


def _clamp_score(score: Decimal) -> Decimal:
    return max(min(score, Decimal("1.00")), Decimal("0.00"))


def _infer_source_type(
    url: str,
    title: str | None,
    snippet: str | None,
    hint: object | None,
) -> str:
    allowed = {
        "company_site",
        "pricing_page",
        "product_page",
        "review",
        "forum",
        "blog",
        "market_report",
        "directory",
        "docs",
        "unknown",
    }
    if isinstance(hint, str) and hint in allowed:
        return hint
    combined = f"{url} {title or ''} {snippet or ''}".casefold()
    if any(term in combined for term in ["pricing", "plans", "price"]):
        return "pricing_page"
    if any(term in combined for term in ["reddit", "forum", "community", "discussion"]):
        return "forum"
    if any(term in combined for term in ["review", "g2", "capterra", "trustpilot"]):
        return "review"
    if any(term in combined for term in ["market", "report", "trend", "industry"]):
        return "market_report"
    if any(term in combined for term in ["docs", "documentation", "changelog"]):
        return "docs"
    if any(term in combined for term in ["directory", "alternatives", "list"]):
        return "directory"
    if any(term in combined for term in ["product", "features"]):
        return "product_page"
    return "unknown"


def _risk_level(source_type: str) -> str:
    if source_type in {"forum", "review", "unknown"}:
        return "medium"
    return "low"


def _snapshot_text(source: DiscoveredSource) -> str:
    return "\n\n".join(
        part
        for part in [
            source.title,
            f"URL: {source.url}",
            source.snippet,
            f"Reason selected: {source.reason_selected}",
            (
                f"Associated research question: {source.associated_research_question}"
                if source.associated_research_question
                else None
            ),
        ]
        if part
    )


def _source_evidence_metadata(
    source: DiscoveredSource,
    sprint: ResearchSprint,
) -> dict[str, object]:
    return {
        "origin": "source_discovery",
        "research_sprint_id": str(sprint.id),
        "research_sprint_ids": [str(sprint.id)],
        "research_plan_id": str(sprint.plan.id),
        "discovered_source_id": str(source.id),
        "discovered_source_ids": [str(source.id)],
        "source_candidate_type": source.source_type,
        "source_candidate_types": [source.source_type],
        "source_relevance_score": str(source.relevance_score),
        "reason_selected": source.reason_selected,
        "associated_research_question": source.associated_research_question,
        "search_provider": source.search_provider,
        "search_query": source.search_query,
        "search_result_rank": source.search_result_rank,
        "retrieved_at": source.retrieved_at.isoformat() if source.retrieved_at else None,
        "risk_level": source.risk_level,
        "provenance": source.provenance_metadata or {},
        "research_questions": (
            [source.associated_research_question] if source.associated_research_question else []
        ),
        "assumptions_to_test": sprint.plan.assumptions_to_test,
        "source_fetched_at": datetime.now(UTC).isoformat(),
    }
