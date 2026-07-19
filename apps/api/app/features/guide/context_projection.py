"""Project overview projection helpers for Ask Thesys guide context."""

from __future__ import annotations

import uuid

from app.features.guide import actions as guide_actions
from app.schemas.guide import GuideChatTurnRead, GuideContextRead, GuideEvidenceSummaryRead
from app.schemas.overview import ProjectOverviewRead


def bounded_recent_turns(recent_turns: list[GuideChatTurnRead]) -> list[dict[str, str]]:
    return [{"role": turn.role, "content": turn.content[:500]} for turn in recent_turns[-6:]]


def guide_context_from_overview(
    overview: ProjectOverviewRead,
    *,
    active_validation_plan_id: uuid.UUID | None,
    latest_research_sprint_id: uuid.UUID | None,
) -> GuideContextRead:
    snapshot = overview.strategic_snapshot
    project = overview.project
    actions = guide_actions.available_actions(overview)
    return GuideContextRead(
        project_id=project.id,
        project_name=project.name,
        stage=snapshot.current_stage,
        verdict=overview.current_recommendation.recommendation,
        next_action=overview.next_best_action.label,
        risk_level=risk_level(overview),
        confidence_level=(
            "unknown"
            if snapshot.current_stage == "draft_idea" and overview.evidence_health.source_count == 0
            else snapshot.current_confidence
        ),
        current_thesis=snapshot.current_thesis,
        target_user=snapshot.target_user,
        primary_problem=snapshot.primary_problem,
        current_wedge=snapshot.proposed_wedge,
        biggest_unknown=biggest_unknown(overview),
        active_validation_plan_id=active_validation_plan_id,
        latest_research_sprint_id=latest_research_sprint_id,
        evidence_summary=GuideEvidenceSummaryRead(
            sources=overview.evidence_health.source_count,
            competitors=overview.evidence_health.competitor_count,
            supported_findings=overview.evidence_health.cited_claim_count,
            open_questions=overview.evidence_health.unsupported_claim_count
            + len(overview.idea_readiness.missing_items),
            validated_assumptions=overview.evidence_health.validated_assumption_count,
        ),
        missing_context=[item.label for item in overview.idea_readiness.missing_items],
        available_actions=actions,
    )


def risk_level(overview: ProjectOverviewRead) -> str:
    if overview.strategic_snapshot.current_stage in {"killed"}:
        return "none"
    if any(
        assumption.kill_risk or assumption.importance in {"critical", "high"}
        for assumption in overview.key_assumptions
    ):
        return "high"
    if overview.evidence_health.unsupported_claim_count > 0 or overview.key_risks:
        return "medium"
    if overview.evidence_health.source_count == 0:
        return "medium"
    return "low"


def biggest_unknown(overview: ProjectOverviewRead) -> str | None:
    if overview.key_assumptions:
        return overview.key_assumptions[0].text
    if overview.key_risks:
        return overview.key_risks[0].text
    if overview.idea_readiness.weakest_area:
        return overview.idea_readiness.weakest_area
    return None
