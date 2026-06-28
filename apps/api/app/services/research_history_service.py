"""Research history assembly for sprint timelines.

The history view is derived from durable workflow records: plans, discovered
sources, competitor candidates, generated memos, approval requests, and sprint
status transitions are folded into a readable timeline.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthContext
from app.db.models import Artifact, ArtifactVersion, ResearchSprint
from app.schemas.research import (
    ProjectResearchHistoryRead,
    ResearchHistoryEventRead,
    ResearchPlanRead,
    ResearchSprintHistoryRead,
    ResearchSprintRead,
)
from app.services import project_service


def get_project_research_history(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    limit: int = 10,
) -> ProjectResearchHistoryRead:
    """Return recent research sprints with derived timeline events."""

    project_service.get_project(db, auth, project_id)
    sprints = _research_sprints(db, auth, project_id, limit)
    memo_versions = _memo_versions_by_sprint(db, auth, project_id)
    histories = [_sprint_history(sprint, memo_versions.get(sprint.id)) for sprint in sprints]
    latest_recommendation = next(
        (history.recommendation_change for history in histories if history.recommendation_change),
        None,
    )
    return ProjectResearchHistoryRead(
        project_id=project_id,
        sprint_count=len(sprints),
        completed_sprint_count=sum(1 for sprint in sprints if sprint.status == "completed"),
        pending_review_sprint_count=sum(1 for sprint in sprints if sprint.status == "needs_review"),
        latest_recommendation_change=latest_recommendation,
        sprints=histories,
    )


def _research_sprints(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    limit: int,
) -> list[ResearchSprint]:
    """Load research sprints with the relationships needed for timeline assembly."""

    return list(
        db.scalars(
            select(ResearchSprint)
            .where(
                ResearchSprint.workspace_id == auth.workspace_id,
                ResearchSprint.project_id == project_id,
            )
            .options(
                selectinload(ResearchSprint.plan),
                selectinload(ResearchSprint.discovered_sources),
                selectinload(ResearchSprint.competitor_candidates),
            )
            .order_by(ResearchSprint.created_at.desc())
            .limit(limit)
        )
    )


def _memo_versions_by_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> dict[uuid.UUID, tuple[Artifact, ArtifactVersion]]:
    """Map each sprint to the latest generated research memo version."""

    artifacts = list(
        db.scalars(
            select(Artifact)
            .where(
                Artifact.workspace_id == auth.workspace_id,
                Artifact.project_id == project_id,
                Artifact.artifact_type == "research_memo",
            )
            .options(selectinload(Artifact.versions))
        )
    )
    versions_by_sprint: dict[uuid.UUID, tuple[Artifact, ArtifactVersion]] = {}
    for artifact in artifacts:
        for version in artifact.versions:
            content = version.structured_content or {}
            sprint_id = _parse_uuid(content.get("research_sprint_id"))
            if sprint_id is None:
                continue
            existing = versions_by_sprint.get(sprint_id)
            if existing is None or version.created_at > existing[1].created_at:
                versions_by_sprint[sprint_id] = (artifact, version)
    return versions_by_sprint


def _sprint_history(
    sprint: ResearchSprint,
    memo_pair: tuple[Artifact, ArtifactVersion] | None,
) -> ResearchSprintHistoryRead:
    """Convert one sprint and optional memo into a user-facing history record."""

    events: list[ResearchHistoryEventRead] = [_plan_created_event(sprint)]
    if sprint.plan.approved_at:
        events.append(_plan_approved_event(sprint))
    if sprint.plan.rejected_at:
        events.append(_plan_rejected_event(sprint))

    source_candidate_count = len(sprint.discovered_sources)
    ingested_source_count = sum(
        1 for source in sprint.discovered_sources if source.status == "ingested"
    )
    if source_candidate_count:
        events.append(_source_discovery_event(sprint, source_candidate_count))
    if ingested_source_count:
        events.append(_source_ingestion_event(sprint, ingested_source_count))

    competitor_candidate_count = len(sprint.competitor_candidates)
    merged_competitor_count = sum(
        1 for candidate in sprint.competitor_candidates if candidate.status == "merged"
    )
    if competitor_candidate_count:
        events.append(_competitor_discovery_event(sprint, competitor_candidate_count))
    if merged_competitor_count:
        events.append(_competitor_merge_event(sprint, merged_competitor_count))

    artifact: Artifact | None = None
    version: ArtifactVersion | None = None
    content: dict[str, Any] = {}
    if memo_pair is not None:
        artifact, version = memo_pair
        content = version.structured_content or {}
        events.append(_memo_generated_event(sprint, artifact, version, content))
        status_value = content.get("memory_update_status")
        if status_value == "approved":
            events.append(_memory_update_approved_event(sprint, version, content))
        elif status_value == "rejected":
            events.append(_memory_update_rejected_event(sprint, version, content))

    if sprint.status == "completed":
        events.append(_sprint_completed_event(sprint))
    elif sprint.status == "failed":
        events.append(_sprint_failed_event(sprint))

    events.sort(key=lambda event: _aware_datetime(event.created_at))
    return ResearchSprintHistoryRead(
        sprint=_serialize_sprint(sprint),
        source_candidate_count=source_candidate_count,
        ingested_source_count=ingested_source_count,
        competitor_candidate_count=competitor_candidate_count,
        merged_competitor_count=merged_competitor_count,
        memo_artifact_id=artifact.id if artifact else None,
        memo_version_id=version.id if version else None,
        memory_update_status=_optional_str(content.get("memory_update_status")),
        memory_update_summary=_optional_dict(content.get("memory_update_summary")),
        recommendation_change=_decision_recommendation(content),
        events=events,
    )


def _serialize_sprint(sprint: ResearchSprint) -> ResearchSprintRead:
    return ResearchSprintRead.model_validate(
        {
            **sprint.__dict__,
            "plan": ResearchPlanRead.model_validate(sprint.plan),
        }
    )


def _plan_created_event(sprint: ResearchSprint) -> ResearchHistoryEventRead:
    return _event(
        sprint,
        "plan_created",
        "Research plan created",
        "A bounded research plan was drafted from the project thesis.",
        (
            "The plan defines what the system is allowed to investigate before any "
            "autonomous work starts."
        ),
        "research_plan",
        sprint.plan.id,
        sprint.created_at,
    )


def _plan_approved_event(sprint: ResearchSprint) -> ResearchHistoryEventRead:
    return _event(
        sprint,
        "plan_approved",
        "Research plan approved",
        "The user approved the research plan for source and competitor discovery.",
        "Human approval keeps autonomous investigation bounded to the intended scope.",
        "research_plan",
        sprint.plan.id,
        sprint.plan.approved_at or sprint.updated_at,
    )


def _plan_rejected_event(sprint: ResearchSprint) -> ResearchHistoryEventRead:
    return _event(
        sprint,
        "plan_rejected",
        "Research plan rejected",
        "The user rejected the proposed research plan.",
        (
            "Rejected plans are useful history because they explain what the system was "
            "not allowed to pursue."
        ),
        "research_plan",
        sprint.plan.id,
        sprint.plan.rejected_at or sprint.updated_at,
    )


def _source_discovery_event(
    sprint: ResearchSprint,
    source_count: int,
) -> ResearchHistoryEventRead:
    return _event(
        sprint,
        "source_discovery",
        "Source candidates discovered",
        f"{source_count} public source candidate{_plural(source_count)} were ranked for review.",
        "Source review shows which external evidence was considered before ingestion.",
        "research_sprint",
        sprint.id,
        _latest_timestamp([source.updated_at for source in sprint.discovered_sources]),
    )


def _source_ingestion_event(
    sprint: ResearchSprint,
    source_count: int,
) -> ResearchHistoryEventRead:
    source = next(
        (source for source in sprint.discovered_sources if source.evidence_source_id is not None),
        None,
    )
    return _event(
        sprint,
        "source_ingestion",
        "Sources added to evidence graph",
        f"{source_count} approved source{_plural(source_count)} became searchable evidence.",
        "Ingested sources are what make the later memo citeable instead of generic.",
        "evidence" if source and source.evidence_source_id else "research_sprint",
        source.evidence_source_id if source and source.evidence_source_id else sprint.id,
        _latest_timestamp(
            [
                source.ingested_at or source.updated_at
                for source in sprint.discovered_sources
                if source.status == "ingested"
            ]
        ),
    )


def _competitor_discovery_event(
    sprint: ResearchSprint,
    candidate_count: int,
) -> ResearchHistoryEventRead:
    return _event(
        sprint,
        "competitor_discovery",
        "Competitor candidates discovered",
        (
            f"{candidate_count} competitor or substitute candidate"
            f"{_plural(candidate_count)} were classified."
        ),
        "The candidate set makes competitor pressure explicit before the memo recommends a wedge.",
        "research_sprint",
        sprint.id,
        _latest_timestamp([candidate.updated_at for candidate in sprint.competitor_candidates]),
    )


def _competitor_merge_event(
    sprint: ResearchSprint,
    candidate_count: int,
) -> ResearchHistoryEventRead:
    candidate = next(
        (candidate for candidate in sprint.competitor_candidates if candidate.competitor_id),
        None,
    )
    return _event(
        sprint,
        "competitor_merge",
        "Competitors merged into project",
        (
            f"{candidate_count} approved candidate{_plural(candidate_count)} became "
            "project competitors."
        ),
        (
            "Approved competitors become first-class strategic objects for later "
            "retrieval and comparison."
        ),
        "competitor" if candidate and candidate.competitor_id else "research_sprint",
        candidate.competitor_id if candidate and candidate.competitor_id else sprint.id,
        _latest_timestamp(
            [
                candidate.updated_at
                for candidate in sprint.competitor_candidates
                if candidate.status == "merged"
            ]
        ),
    )


def _memo_generated_event(
    sprint: ResearchSprint,
    artifact: Artifact,
    version: ArtifactVersion,
    content: dict[str, Any],
) -> ResearchHistoryEventRead:
    gaps = content.get("evidence_gaps")
    gap_count = len(gaps) if isinstance(gaps, list) else 0
    return _event(
        sprint,
        "memo_generated",
        "Research memo generated",
        f"A cited research memo was generated with {gap_count} evidence gap{_plural(gap_count)}.",
        (
            "The memo ties research, evidence, weak claims, assumptions, and validation "
            "actions together."
        ),
        "artifact",
        artifact.id,
        version.created_at,
    )


def _memory_update_approved_event(
    sprint: ResearchSprint,
    version: ArtifactVersion,
    content: dict[str, Any],
) -> ResearchHistoryEventRead:
    summary = _optional_dict(content.get("memory_update_summary")) or {}
    assumption_count = len(summary.get("assumption_ids") or [])
    risk_count = len(summary.get("risk_ids") or [])
    return _event(
        sprint,
        "memory_update_approved",
        "Memory updates approved",
        (
            f"{assumption_count} assumption{_plural(assumption_count)} and "
            f"{risk_count} risk{_plural(risk_count)} were written to project memory."
        ),
        "Approved memory updates explain how a research memo changed the project state.",
        "artifact_version",
        version.id,
        _parse_datetime(content.get("memory_update_approved_at")) or version.created_at,
    )


def _memory_update_rejected_event(
    sprint: ResearchSprint,
    version: ArtifactVersion,
    content: dict[str, Any],
) -> ResearchHistoryEventRead:
    return _event(
        sprint,
        "memory_update_rejected",
        "Memory updates rejected",
        "The research memo was kept, but proposed project-memory changes were rejected.",
        "Rejected updates are still part of the decision trail and prevent opaque state changes.",
        "artifact_version",
        version.id,
        _parse_datetime(content.get("memory_update_rejected_at")) or version.created_at,
    )


def _sprint_completed_event(sprint: ResearchSprint) -> ResearchHistoryEventRead:
    return _event(
        sprint,
        "sprint_completed",
        "Research sprint completed",
        "The research sprint finished its review and memory update path.",
        "Completed sprints create an auditable trail from plan to evidence to recommendation.",
        "research_sprint",
        sprint.id,
        sprint.completed_at or sprint.updated_at,
    )


def _sprint_failed_event(sprint: ResearchSprint) -> ResearchHistoryEventRead:
    return _event(
        sprint,
        "sprint_failed",
        "Research sprint failed",
        "The research sprint failed before completion.",
        "Failures should be visible so the user can retry or inspect the workflow trace.",
        "research_sprint",
        sprint.id,
        sprint.updated_at,
    )


def _event(
    sprint: ResearchSprint,
    event_type: str,
    title: str,
    summary: str,
    why_it_matters: str,
    related_entity_type: str,
    related_entity_id: uuid.UUID,
    created_at: datetime,
) -> ResearchHistoryEventRead:
    return ResearchHistoryEventRead(
        id=f"{event_type}:{sprint.id}:{related_entity_id}",
        research_sprint_id=sprint.id,
        event_type=event_type,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        why_it_matters=why_it_matters,
        related_entity_type=related_entity_type,  # type: ignore[arg-type]
        related_entity_id=related_entity_id,
        created_at=created_at,
    )


def _latest_timestamp(values: list[datetime | None]) -> datetime:
    dates = [value for value in values if value is not None]
    return max(dates) if dates else datetime.now(UTC)


def _decision_recommendation(content: dict[str, Any]) -> str | None:
    memo = content.get("memo")
    if not isinstance(memo, dict):
        return None
    recommendation = memo.get("decision_recommendation")
    if isinstance(recommendation, str) and recommendation.strip():
        return recommendation.strip()
    return None


def _aware_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _optional_dict(value: object) -> dict[str, object] | None:
    return value if isinstance(value, dict) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _parse_uuid(value: object) -> uuid.UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _plural(count: int) -> str:
    return "" if count == 1 else "s"


def require_reviewable_research_memo(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> tuple[Artifact, ArtifactVersion]:
    """Find a generated research memo that can be reviewed or approved."""

    memo_versions = _memo_versions_by_sprint(db, auth, project_id)
    memo_pair = memo_versions.get(sprint_id)
    if memo_pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research memo not found for this sprint.",
        )
    return memo_pair
