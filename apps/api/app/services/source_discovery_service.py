"""Source discovery workflow for research sprints."""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.fallback_completion import fallback_completion
from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import SOURCE_DISCOVERY_PROMPT_VERSION
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
from app.db.models import AIRun, AIStep, DiscoveredSource, ResearchSprint
from app.features.research import source_discovery as source_discovery_feature
from app.schemas.research import SourceDiscoveryDraft
from app.services import (
    ai_run_service,
    evidence_service,
    external_search_service,
    langsmith_observability_service,
    project_service,
    security_policy_service,
    workflow_budget_service,
)


@dataclass(frozen=True)
class SourceDiscoveryResult:
    """Generated source candidates plus persisted run/step metadata."""

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
    """Generate source candidates from the approved research plan."""
    require_permission(auth, "run_research")
    project = project_service.get_project(db, auth, project_id)
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if sprint.status not in {"approved", "running", "needs_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the research plan before discovering sources.",
        )
    if settings.external_search_enabled:
        security_policy_service.enforce_source_fetching_allowed(
            db,
            auth,
            settings,
            project_id=project_id,
            workflow_type="source_discovery",
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
                db,
                auth,
                settings,
                _search_queries_for_sprint(sprint),
                project_id=project_id,
                research_sprint_id=sprint.id,
            )
            draft = SourceDiscoveryDraft(sources=[])
            completion = _external_search_completion(settings, messages, search_batch)
            specs = _candidate_specs_from_search(search_batch)
            search_diagnostics = external_search_service.diagnostics(search_batch)
        else:
            with workflow_budget_service.workflow_budget_scope(
                db,
                auth,
                settings,
                project_id=project_id,
                research_sprint_id=sprint.id,
            ):
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
    """Ingest an approved candidate while preserving discovery provenance."""
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


_source_discovery_messages = source_discovery_feature.source_discovery_messages


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    draft: SourceDiscoveryDraft,
    fallback_name: str,
    error: BaseException | None = None,
) -> LLMCompletion:
    return fallback_completion(
        settings,
        messages,
        draft,
        fallback_name,
        error,
        fallback_prefix="source_discovery",
        use_stub_provider=True,
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


_candidate_specs_from_draft = source_discovery_feature.candidate_specs_from_draft
_candidate_specs_from_search = source_discovery_feature.candidate_specs_from_search
_fallback_candidate_specs = source_discovery_feature.fallback_candidate_specs
_spec = source_discovery_feature.spec
_ordered_queries = source_discovery_feature.ordered_queries
_search_queries_for_sprint = source_discovery_feature.search_queries_for_sprint
_dedupe_specs = source_discovery_feature.dedupe_specs
_normalize_url = source_discovery_feature.normalize_url
_clean_url = source_discovery_feature.clean_url
_clamp_score = source_discovery_feature.clamp_score
_infer_source_type = source_discovery_feature.infer_source_type
_risk_level = source_discovery_feature.risk_level
_snapshot_text = source_discovery_feature.snapshot_text
_source_evidence_metadata = source_discovery_feature.source_evidence_metadata
