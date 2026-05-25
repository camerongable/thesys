import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import COMPETITOR_DISCOVERY_PROMPT_VERSION
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import (
    AIRun,
    AIStep,
    CompetitorCandidate,
    CompetitorEvidenceLink,
    DiscoveredSource,
    EvidenceChunk,
    EvidenceSource,
    ResearchSprint,
)
from app.schemas.competitors import CompetitorCreate, CompetitorUpdate
from app.schemas.research import CompetitorCandidateUpdate, CompetitorDiscoveryDraft
from app.services import ai_run_service, competitor_service, project_service


@dataclass(frozen=True)
class CompetitorDiscoveryResult:
    run: AIRun
    step: AIStep
    generated_count: int
    candidate_count: int
    candidates: list[CompetitorCandidate]


def list_competitor_candidates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> list[CompetitorCandidate]:
    _get_sprint(db, auth, project_id, sprint_id)
    return _list_candidates(db, auth, project_id, sprint_id)


def discover_competitors(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> CompetitorDiscoveryResult:
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if sprint.status not in {"approved", "running", "needs_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the research plan before discovering competitors.",
        )

    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="competitor_discovery",
        prompt_version=COMPETITOR_DISCOVERY_PROMPT_VERSION,
        input_summary=sprint.plan.objective[:500],
        project_id=project_id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    sources = _list_sources(db, auth, project_id, sprint_id)
    messages = _competitor_discovery_messages(sprint, sources)
    step = ai_run_service.start_step(
        db,
        run,
        step_name="generate_competitor_candidates",
        input_json={
            "schema": CompetitorDiscoveryDraft.__name__,
            "research_sprint_id": str(sprint.id),
            "research_plan_id": str(sprint.plan.id),
            "competitor_queries": sprint.plan.competitor_queries,
            "substitute_queries": sprint.plan.substitute_queries,
            "target_customer_hypotheses": sprint.plan.target_customer_hypotheses,
            "source_count": len(sources),
            "messages": [message.model_dump() for message in messages],
        },
    )
    started = perf_counter()
    try:
        draft, completion = _generate_competitor_draft(settings, sprint, sources, messages)
        specs = _candidate_specs_from_draft(draft, {str(source.id) for source in sources})
        generated_count = len(specs)
        existing = {
            _candidate_key(candidate.name, candidate.url): candidate
            for candidate in _list_candidates(db, auth, project_id, sprint_id)
        }
        for spec in specs:
            key = _candidate_key(str(spec["name"]), spec.get("url"))
            if key in existing:
                continue
            candidate = CompetitorCandidate(
                workspace_id=auth.workspace_id,
                project_id=project_id,
                research_sprint_id=sprint.id,
                name=str(spec["name"])[:255],
                url=_clean_url(spec.get("url")),
                category=str(spec["category"]),
                target_user=_optional_text(spec.get("target_user")),
                positioning=_optional_text(spec.get("positioning")),
                pricing_signal=_optional_text(spec.get("pricing_signal")),
                core_features=list(spec.get("core_features", [])),
                why_it_matters=str(spec["why_it_matters"]),
                threat_level=str(spec["threat_level"]),
                relevance_score=spec["relevance_score"],
                source_ids=list(spec.get("source_ids", [])),
                status="candidate",
                created_by=auth.user_id,
            )
            db.add(candidate)
            existing[key] = candidate

        if sprint.status == "approved":
            sprint.status = "running"
            sprint.started_at = sprint.started_at or datetime.now(UTC)
        db.commit()
        candidates = _list_candidates(db, auth, project_id, sprint_id)
        step = ai_run_service.complete_step(
            db,
            step,
            output_json={
                "generated_count": generated_count,
                "candidate_count": len(candidates),
                "candidate_ids": [str(candidate.id) for candidate in candidates],
                "used_stub": completion.used_stub,
                "model_provider": completion.model_provider,
                "model_name": completion.model_name,
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
        run = ai_run_service.complete_run(
            db,
            run,
            output_summary=f"Generated {len(candidates)} competitor candidates.",
            total_tokens=completion.total_tokens,
            total_cost=completion.total_cost,
            model_provider=completion.model_provider,
            model_name=completion.model_name,
        )
        return CompetitorDiscoveryResult(
            run=run,
            step=step,
            generated_count=generated_count,
            candidate_count=len(candidates),
            candidates=candidates,
        )
    except Exception as exc:
        db.rollback()
        ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        ai_run_service.fail_run(db, run, error=str(exc))
        raise


def update_competitor_candidate(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: CompetitorCandidateUpdate,
) -> CompetitorCandidate:
    candidate = _get_candidate(db, auth, project_id, sprint_id, candidate_id)
    if candidate.status != "candidate":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only candidate competitors can be edited.",
        )
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is None:
            continue
        if field == "core_features":
            candidate.core_features = _clean_list(value)
        elif field == "url":
            candidate.url = _clean_url(value)
        elif field in {"name", "why_it_matters"}:
            setattr(candidate, field, " ".join(str(value).split()))
        else:
            setattr(candidate, field, value)
    db.commit()
    db.refresh(candidate)
    return candidate


def approve_competitor_candidate(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> CompetitorCandidate:
    candidate = _get_candidate(db, auth, project_id, sprint_id, candidate_id)
    if candidate.status != "candidate":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only candidate competitors can be approved.",
        )

    competitor = competitor_service.create_competitor(
        db,
        auth,
        project_id,
        CompetitorCreate(
            name=candidate.name,
            url=candidate.url,
            category=_project_competitor_category(candidate.category),
        ),
    )
    competitor = competitor_service.update_competitor(
        db,
        auth,
        project_id,
        competitor.id,
        CompetitorUpdate(
            target_user=candidate.target_user,
            positioning=candidate.positioning,
            pricing_summary=candidate.pricing_signal,
            key_features=candidate.core_features,
            differentiation_notes=candidate.why_it_matters,
            threat_level=candidate.threat_level,
        ),
    )
    _link_candidate_sources(db, auth, candidate, competitor.id)
    candidate = _get_candidate(db, auth, project_id, sprint_id, candidate_id)
    candidate.competitor_id = competitor.id
    candidate.status = "merged"
    db.commit()
    db.refresh(candidate)
    return candidate


def reject_competitor_candidate(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> CompetitorCandidate:
    candidate = _get_candidate(db, auth, project_id, sprint_id, candidate_id)
    if candidate.status not in {"candidate", "approved"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only unmerged competitor candidates can be rejected.",
        )
    candidate.status = "rejected"
    db.commit()
    db.refresh(candidate)
    return candidate


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


def _list_candidates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> list[CompetitorCandidate]:
    return list(
        db.scalars(
            select(CompetitorCandidate)
            .where(
                CompetitorCandidate.workspace_id == auth.workspace_id,
                CompetitorCandidate.project_id == project_id,
                CompetitorCandidate.research_sprint_id == sprint_id,
            )
            .order_by(
                CompetitorCandidate.relevance_score.desc(),
                CompetitorCandidate.created_at,
            )
        )
    )


def _get_candidate(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> CompetitorCandidate:
    candidate = db.scalar(
        select(CompetitorCandidate).where(
            CompetitorCandidate.id == candidate_id,
            CompetitorCandidate.workspace_id == auth.workspace_id,
            CompetitorCandidate.project_id == project_id,
            CompetitorCandidate.research_sprint_id == sprint_id,
        )
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competitor candidate not found.",
        )
    return candidate


def _list_sources(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> list[DiscoveredSource]:
    return list(
        db.scalars(
            select(DiscoveredSource).where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
                DiscoveredSource.research_sprint_id == sprint_id,
            )
        )
    )


def _generate_competitor_draft(
    settings: Settings,
    sprint: ResearchSprint,
    sources: list[DiscoveredSource],
    messages: list[ChatMessage],
) -> tuple[CompetitorDiscoveryDraft, LLMCompletion]:
    if settings.should_use_llm_stub or should_use_fallback_without_model(settings):
        draft = CompetitorDiscoveryDraft(candidates=_fallback_candidate_specs(sprint, sources))
        return draft, _fallback_completion(
            settings,
            messages,
            draft,
            "stub" if settings.should_use_llm_stub else "policy_always",
        )

    try:
        result = generate_structured_output(
            settings,
            CompetitorDiscoveryDraft,
            messages,
            model=settings.litellm_model,
            temperature=0.1,
            max_tokens=4000,
        )
        return CompetitorDiscoveryDraft.model_validate(result.parsed), result.completion
    except (StructuredOutputError, RuntimeError) as exc:
        if not should_use_fallback_after_error(settings):
            raise
        draft = CompetitorDiscoveryDraft(candidates=_fallback_candidate_specs(sprint, sources))
        return draft, _fallback_completion(settings, messages, draft, "emergency", exc)


def _competitor_discovery_messages(
    sprint: ResearchSprint,
    sources: list[DiscoveredSource],
) -> list[ChatMessage]:
    plan = sprint.plan
    payload = {
        "objective": plan.objective,
        "target_customer_hypotheses": plan.target_customer_hypotheses,
        "research_questions": plan.research_questions,
        "competitor_queries": plan.competitor_queries,
        "substitute_queries": plan.substitute_queries,
        "approved_or_candidate_sources": [
            {
                "id": str(source.id),
                "url": source.url,
                "title": source.title,
                "source_type": source.source_type,
                "status": source.status,
                "snippet": source.snippet,
                "reason_selected": source.reason_selected,
            }
            for source in sources[:10]
        ],
        "max_candidates": 8,
    }
    return [
        ChatMessage(
            role="system",
            content=(
                "You identify competitor candidates for a founder strategy workspace. "
                "Use the approved research plan and discovered source context to produce "
                "a reviewable competitor set. Include direct competitors, indirect "
                "competitors, substitutes, incumbent platforms, and adjacent solutions. "
                "Do not claim that you browsed the web. Prefer well-known, verifiable "
                "companies or clearly labeled substitute behaviors over obscure guesses. "
                "Only include source_ids from the provided source list."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Create a ranked competitor candidate list from this approved research "
                "plan. Return only the structured JSON.\n\n"
                f"{json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}"
            ),
        ),
    ]


def _candidate_specs_from_draft(
    draft: CompetitorDiscoveryDraft,
    allowed_source_ids: set[str],
) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for candidate in draft.candidates:
        name = " ".join(candidate.name.split())
        if not name:
            continue
        specs.append(
            {
                "name": name,
                "url": _clean_url(candidate.url),
                "category": candidate.category,
                "target_user": candidate.target_user,
                "positioning": candidate.positioning,
                "pricing_signal": candidate.pricing_signal,
                "core_features": _clean_list(candidate.core_features),
                "why_it_matters": candidate.why_it_matters,
                "threat_level": candidate.threat_level,
                "relevance_score": _clamp_score(candidate.relevance_score),
                "source_ids": [
                    source_id
                    for source_id in candidate.source_ids
                    if source_id in allowed_source_ids
                ],
            }
        )
    return _dedupe_specs(specs)


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    draft: CompetitorDiscoveryDraft,
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
            "fallback": f"competitor_discovery_{fallback_name}",
            "error": str(error)[:500] if error is not None else None,
        },
        used_stub=True,
    )


def _fallback_candidate_specs(
    sprint: ResearchSprint,
    sources: list[DiscoveredSource],
) -> list[dict[str, object]]:
    context = " ".join(
        [
            sprint.plan.objective,
            *sprint.plan.target_customer_hypotheses,
            *sprint.plan.competitor_queries,
            *sprint.plan.substitute_queries,
        ]
    ).casefold()
    source_ids = [str(source.id) for source in sources[:4]]
    specs = _known_competitor_specs(context, sprint, source_ids)
    specs.extend(_generic_competitor_specs(sprint, source_ids))
    return _dedupe_specs(specs)


def _known_competitor_specs(
    context: str,
    sprint: ResearchSprint,
    source_ids: list[str],
) -> list[dict[str, object]]:
    target_user = _primary_target_user(sprint)
    if any(token in context for token in ["fitness", "coach", "workout", "training"]):
        return [
            _spec(
                "TrueCoach",
                "https://truecoach.co",
                "direct_competitor",
                target_user,
                "Coaching software for workout delivery, client management, and messaging.",
                "Published subscription pricing exists.",
                ["programming", "client management", "messaging"],
                "Directly overlaps with independent coach workflow and may already own parts "
                "of the proposed wedge.",
                "high",
                Decimal("0.95"),
                source_ids,
            ),
            _spec(
                "Trainerize",
                "https://www.trainerize.com",
                "direct_competitor",
                target_user,
                "Fitness coaching platform covering workouts, habits, nutrition, and client "
                "communication.",
                "Subscription packaging is visible publicly.",
                ["workouts", "habit coaching", "payments", "client app"],
                "A broad incumbent that tests whether a narrower AI-powered wedge is defensible.",
                "high",
                Decimal("0.92"),
                source_ids,
            ),
            _spec(
                "Google Sheets and manual check-ins",
                None,
                "substitute_behavior",
                target_user,
                "Manual programming, weekly forms, spreadsheets, and text-based client updates.",
                "Mostly free except time cost.",
                ["spreadsheets", "forms", "manual notes"],
                "Manual workflows are the real switching baseline for many solo operators.",
                "medium",
                Decimal("0.84"),
                source_ids,
            ),
        ]
    if any(token in context for token in ["plant", "houseplant", "garden"]):
        return [
            _spec(
                "Planta",
                "https://getplanta.com",
                "direct_competitor",
                target_user,
                "Consumer plant-care app with reminders and plant guidance.",
                "Consumer subscription signal.",
                ["care reminders", "plant identification", "guidance"],
                "Directly overlaps with personalized plant-care guidance for beginners.",
                "high",
                Decimal("0.93"),
                source_ids,
            ),
            _spec(
                "PictureThis",
                "https://www.picturethisai.com",
                "indirect_competitor",
                target_user,
                "Plant identification and diagnosis app.",
                "Consumer app subscription signal.",
                ["identification", "diagnosis", "care information"],
                "May own diagnosis moments even if it does not own education or community.",
                "medium",
                Decimal("0.88"),
                source_ids,
            ),
            _spec(
                "Free plant-care content",
                None,
                "substitute_behavior",
                target_user,
                "Search, YouTube, Reddit, and nursery advice.",
                "Free.",
                ["search", "community advice", "video education"],
                "Free substitutes raise willingness-to-pay risk for generic guidance.",
                "high",
                Decimal("0.86"),
                source_ids,
            ),
        ]
    if any(token in context for token in ["founder", "research", "strategy", "intelligence"]):
        return [
            _spec(
                "Perplexity",
                "https://www.perplexity.ai",
                "indirect_competitor",
                target_user,
                "AI research assistant with cited web answers.",
                "Freemium and paid subscriptions.",
                ["web research", "citations", "summaries"],
                "Commoditizes one-off cited research, so durable project memory must be the wedge.",
                "high",
                Decimal("0.92"),
                source_ids,
            ),
            _spec(
                "ChatGPT",
                "https://chatgpt.com",
                "substitute_behavior",
                target_user,
                "General-purpose AI assistant used for brainstorming and strategy drafts.",
                "Free and paid tiers.",
                ["brainstorming", "summaries", "drafting"],
                "The common default substitute; the product must prove it is more stateful "
                "than chat.",
                "high",
                Decimal("0.90"),
                source_ids,
            ),
            _spec(
                "Notion",
                "https://www.notion.com",
                "incumbent_platform",
                target_user,
                "Workspace for documents, databases, notes, and lightweight workflows.",
                "Freemium and team pricing.",
                ["docs", "databases", "AI summaries"],
                "Captures the workspace layer even if it does not provide structured strategy "
                "intelligence.",
                "medium",
                Decimal("0.84"),
                source_ids,
            ),
        ]
    return []


def _generic_competitor_specs(
    sprint: ResearchSprint,
    source_ids: list[str],
) -> list[dict[str, object]]:
    target_user = _primary_target_user(sprint)
    category_phrase = _category_phrase(sprint)
    return [
        _spec(
            f"Existing {category_phrase} software",
            None,
            "indirect_competitor",
            target_user,
            "Category incumbents solving part of the workflow with established distribution.",
            "Pricing needs research.",
            ["workflow management", "reporting", "collaboration"],
            "Incumbents may already own budget and workflow attention even if they lack the "
            "exact AI feature.",
            "medium",
            Decimal("0.78"),
            source_ids,
        ),
        _spec(
            "Spreadsheet/manual workflow",
            None,
            "substitute_behavior",
            target_user,
            "Current manual process using spreadsheets, docs, email, forms, or messages.",
            "Free or bundled with existing tools.",
            ["manual tracking", "notes", "status updates"],
            "Manual work is often the true competitor before a buyer switches to a new tool.",
            "high",
            Decimal("0.76"),
            source_ids,
        ),
        _spec(
            "Generic AI assistants",
            "https://chatgpt.com",
            "substitute_behavior",
            target_user,
            "General AI tools used to draft, summarize, and analyze ad hoc context.",
            "Free and paid subscriptions.",
            ["summarization", "drafting", "ideation"],
            "Generic AI can satisfy low-frequency needs unless this product owns persistent "
            "workflow state.",
            "medium",
            Decimal("0.74"),
            source_ids,
        ),
    ]


def _spec(
    name: str,
    url: str | None,
    category: str,
    target_user: str,
    positioning: str,
    pricing_signal: str,
    core_features: list[str],
    why_it_matters: str,
    threat_level: str,
    relevance_score: Decimal,
    source_ids: list[str],
) -> dict[str, object]:
    return {
        "name": name,
        "url": url,
        "category": category,
        "target_user": target_user,
        "positioning": positioning,
        "pricing_signal": pricing_signal,
        "core_features": core_features,
        "why_it_matters": why_it_matters,
        "threat_level": threat_level,
        "relevance_score": relevance_score,
        "source_ids": source_ids,
    }


def _dedupe_specs(specs: list[dict[str, object]]) -> list[dict[str, object]]:
    by_key: dict[str, dict[str, object]] = {}
    for spec in specs:
        key = _candidate_key(str(spec["name"]), spec.get("url"))
        if key not in by_key:
            by_key[key] = spec
    return list(by_key.values())


def _candidate_key(name: str, url: object | None) -> str:
    if url:
        return _clean_url(url) or name.casefold()
    return " ".join(name.casefold().split())


def _primary_target_user(sprint: ResearchSprint) -> str:
    return next(
        (
            " ".join(user.split())
            for user in sprint.plan.target_customer_hypotheses
            if " ".join(user.split())
        ),
        "the target customer",
    )


def _category_phrase(sprint: ResearchSprint) -> str:
    text = sprint.plan.objective.strip()
    if not text:
        return "category"
    words = [word.strip(".,:;()[]").casefold() for word in text.split()]
    stop = {
        "the",
        "this",
        "that",
        "whether",
        "investigate",
        "validate",
        "market",
        "competitors",
        "risks",
        "for",
        "with",
        "and",
        "next",
    }
    useful = [word for word in words if len(word) > 3 and word not in stop]
    return " ".join(useful[:3]) or "category"


def _project_competitor_category(candidate_category: str) -> str:
    return {
        "direct_competitor": "direct",
        "indirect_competitor": "adjacent",
        "substitute_behavior": "substitute",
        "incumbent_platform": "incumbent",
        "adjacent_solution": "adjacent",
        "irrelevant": "unknown",
    }.get(candidate_category, "unknown")


def _link_candidate_sources(
    db: Session,
    auth: AuthContext,
    candidate: CompetitorCandidate,
    competitor_id: uuid.UUID,
) -> None:
    for source_id in candidate.source_ids:
        try:
            discovered_source_id = uuid.UUID(str(source_id))
        except ValueError:
            continue
        discovered_source = db.scalar(
            select(DiscoveredSource).where(
                DiscoveredSource.id == discovered_source_id,
                DiscoveredSource.workspace_id == auth.workspace_id,
            )
        )
        if discovered_source is None or discovered_source.evidence_source_id is None:
            continue
        evidence_source = db.scalar(
            select(EvidenceSource)
            .where(
                EvidenceSource.id == discovered_source.evidence_source_id,
                EvidenceSource.workspace_id == auth.workspace_id,
            )
            .options(selectinload(EvidenceSource.chunks))
        )
        if evidence_source is None:
            continue
        first_chunk = evidence_source.chunks[0] if evidence_source.chunks else None
        existing = db.scalar(
            select(CompetitorEvidenceLink).where(
                CompetitorEvidenceLink.competitor_id == competitor_id,
                CompetitorEvidenceLink.evidence_source_id == evidence_source.id,
            )
        )
        if existing is not None:
            continue
        db.add(
            CompetitorEvidenceLink(
                competitor_id=competitor_id,
                evidence_source_id=evidence_source.id,
                evidence_chunk_id=(
                    first_chunk.id if isinstance(first_chunk, EvidenceChunk) else None
                ),
            )
        )
    db.commit()


def _clean_url(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "://" not in text:
        return f"https://{text}"
    return text


def _clamp_score(score: Decimal) -> Decimal:
    return max(min(score, Decimal("1.00")), Decimal("0.00"))


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        key = text.casefold()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned
