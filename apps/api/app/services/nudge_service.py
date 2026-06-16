import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.db.models import ProjectNudge
from app.schemas.guide import GuideActionRead
from app.schemas.nudges import ProjectNudgeRead
from app.schemas.overview import ProjectOverviewRead
from app.schemas.validation import ValidationMissionRead
from app.services import project_overview_service, project_service, validation_service


class ProjectNudgeNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class _NudgeCandidate:
    nudge_key: str
    severity: str
    title: str
    message: str
    why_it_matters: str
    action: GuideActionRead


def list_project_nudges(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    limit: int = 2,
) -> list[ProjectNudgeRead]:
    overview = project_overview_service.get_project_overview(db, auth, project_id)
    mission = validation_service.get_current_validation_mission(db, auth, project_id)
    candidates = _nudge_candidates(overview, mission)
    stored = _sync_candidates(db, auth, project_id, candidates)
    ordered = [
        _serialize_nudge(stored[candidate.nudge_key])
        for candidate in candidates
        if candidate.nudge_key in stored and not stored[candidate.nudge_key].dismissed
    ]
    return ordered[:limit]


def dismiss_project_nudge(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    nudge_id: uuid.UUID,
) -> ProjectNudgeRead:
    project_service.get_project(db, auth, project_id)
    nudge = db.scalar(
        select(ProjectNudge).where(
            ProjectNudge.id == nudge_id,
            ProjectNudge.workspace_id == auth.workspace_id,
            ProjectNudge.project_id == project_id,
        )
    )
    if nudge is None:
        raise ProjectNudgeNotFoundError(nudge_id)
    nudge.dismissed = True
    db.commit()
    db.refresh(nudge)
    return _serialize_nudge(nudge)


def _sync_candidates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    candidates: list[_NudgeCandidate],
) -> dict[str, ProjectNudge]:
    if not candidates:
        return {}
    keys = [candidate.nudge_key for candidate in candidates]
    existing = {
        nudge.nudge_key: nudge
        for nudge in db.scalars(
            select(ProjectNudge).where(
                ProjectNudge.workspace_id == auth.workspace_id,
                ProjectNudge.project_id == project_id,
                ProjectNudge.nudge_key.in_(keys),
            )
        )
    }
    for candidate in candidates:
        action_payload = candidate.action.model_dump(mode="json")
        nudge = existing.get(candidate.nudge_key)
        if nudge is None:
            nudge = ProjectNudge(
                workspace_id=auth.workspace_id,
                project_id=project_id,
                nudge_key=candidate.nudge_key,
                severity=candidate.severity,
                title=candidate.title,
                message=candidate.message,
                why_it_matters=candidate.why_it_matters,
                action_payload=action_payload,
                dismissed=False,
            )
            db.add(nudge)
            existing[candidate.nudge_key] = nudge
            continue
        nudge.severity = candidate.severity
        nudge.title = candidate.title
        nudge.message = candidate.message
        nudge.why_it_matters = candidate.why_it_matters
        nudge.action_payload = action_payload
    db.commit()
    for nudge in existing.values():
        db.refresh(nudge)
    return existing


def _nudge_candidates(
    overview: ProjectOverviewRead,
    mission: ValidationMissionRead | None,
) -> list[_NudgeCandidate]:
    candidates = [
        candidate
        for candidate in [
            _no_validation_results_nudge(overview, mission),
            _research_enough_for_first_test_nudge(overview, mission),
            _weak_evidence_nudge(overview, mission),
            _too_broad_nudge(overview),
        ]
        if candidate is not None
    ]
    return candidates


def _too_broad_nudge(overview: ProjectOverviewRead) -> _NudgeCandidate | None:
    stage = overview.strategic_snapshot.current_stage
    if stage not in {
        "structured_intake",
        "brief_generated",
        "competitors_analyzed",
        "assumptions_identified",
    }:
        return None
    if overview.strategic_snapshot.proposed_wedge:
        return None
    target = overview.strategic_snapshot.target_user or "the first target user"
    return _NudgeCandidate(
        nudge_key="idea_too_broad",
        severity="warning",
        title="Your idea is still broad.",
        message=f"Choose a narrower wedge for {target} before running more research.",
        why_it_matters=(
            "A broad idea produces broad evidence. Comparing wedges keeps the next proof "
            "focused on one user, one painful moment, and one reason to switch."
        ),
        action=_guide_action(
            project_id=overview.project.id,
            action_id="compare_wedges",
            action_type="compare_wedges",
            label="Compare wedges",
            description="Compare possible strategic directions before choosing a proof.",
            why_it_matters="A narrow wedge is easier to test than a general product idea.",
            target_hash="wedge-explorer",
            target_modal="wedge-explorer",
            risk_level="medium",
        ),
    )


def _research_enough_for_first_test_nudge(
    overview: ProjectOverviewRead,
    mission: ValidationMissionRead | None,
) -> _NudgeCandidate | None:
    if mission is not None:
        return None
    if overview.strategic_snapshot.current_stage != "assumptions_identified":
        return None
    has_research_signal = (
        overview.evidence_health.source_count >= 2
        or overview.evidence_health.competitor_count > 0
        or overview.evidence_health.cited_claim_count > 0
    )
    if not has_research_signal or not overview.key_assumptions:
        return None
    blocker = overview.key_assumptions[0].text
    return _NudgeCandidate(
        nudge_key="research_enough_for_first_test",
        severity="action_required",
        title="You have enough research for a first validation test.",
        message="More research is less useful than real user evidence right now.",
        why_it_matters=(
            f"The next useful proof is whether this must-be-true belief holds: {blocker}"
        ),
        action=_guide_action(
            project_id=overview.project.id,
            action_id="create_validation_plan",
            action_type="run_workflow",
            label="Open validation mission",
            description="Turn the riskiest assumption into a concrete proof.",
            why_it_matters="Validation moves the project from researched opinion to real signal.",
            target_hash="validation-mission",
            target_modal="validation-mission",
            risk_level="medium",
        ),
    )


def _no_validation_results_nudge(
    overview: ProjectOverviewRead,
    mission: ValidationMissionRead | None,
) -> _NudgeCandidate | None:
    if mission is None:
        return None
    if mission.result_count > 0 or mission.status in {"results_logged", "interpreted", "closed"}:
        return None
    if overview.strategic_snapshot.current_stage not in {
        "validation_plan_created",
        "experiment_running",
    }:
        return None
    return _NudgeCandidate(
        nudge_key="validation_plan_no_results",
        severity="action_required",
        title="Your plan exists, but no results are logged.",
        message="Log real evidence before recording a proceed, pivot, pause, or kill decision.",
        why_it_matters=(
            "The project should not advance on a planned test. It needs interview notes, "
            "survey responses, metrics, or observations to change confidence."
        ),
        action=_guide_action(
            project_id=overview.project.id,
            action_id="log_results",
            action_type="log_result",
            label="Log results",
            description="Open the validation mission result form.",
            why_it_matters=(
                "Logged results are what change confidence and unlock decision coaching."
            ),
            target_hash="validation-mission",
            target_modal="log-result",
            risk_level="medium",
        ),
    )


def _weak_evidence_nudge(
    overview: ProjectOverviewRead,
    mission: ValidationMissionRead | None,
) -> _NudgeCandidate | None:
    weakest = overview.evidence_health.weakest_evidence_area.lower()
    if overview.strategic_snapshot.current_stage in {"draft_idea", "structured_intake"}:
        return None
    if mission is not None and mission.status in {"interpreted", "closed"}:
        return None
    if "willingness to pay" in weakest:
        title = "The weakest evidence area is willingness to pay."
        message = "Run a pricing-specific proof before building."
        why = (
            "Pain signals are useful, but a build decision needs evidence that the target "
            "user will pay, switch, or join a pilot."
        )
        label = "Create pricing test"
    elif (
        overview.evidence_health.unsupported_claim_count
        > overview.evidence_health.cited_claim_count
    ):
        title = "Several claims are still unsupported."
        message = "Ground the riskiest open claims before treating the verdict as durable."
        why = (
            "Unsupported claims keep the recommendation fragile. The next proof should "
            "replace guesses with evidence or mark them as assumptions."
        )
        label = "Review weak evidence"
    else:
        return None
    return _NudgeCandidate(
        nudge_key="weak_evidence_area",
        severity="warning",
        title=title,
        message=message,
        why_it_matters=why,
        action=_guide_action(
            project_id=overview.project.id,
            action_id="create_pricing_test",
            action_type="run_workflow",
            label=label,
            description="Open the validation mission area and focus the test on the weak evidence.",
            why_it_matters=why,
            target_hash="validation-mission",
            target_modal="validation-mission",
            risk_level="medium",
        ),
    )


def _guide_action(
    project_id: uuid.UUID,
    action_id: str,
    action_type: str,
    label: str,
    description: str,
    why_it_matters: str,
    target_hash: str,
    risk_level: str,
    target_modal: str | None = None,
) -> GuideActionRead:
    return GuideActionRead(
        id=action_id,
        type=action_type,  # type: ignore[arg-type]
        label=label,
        description=description,
        why_it_matters=why_it_matters,
        target_route=f"/projects/{project_id}#{target_hash}",
        target_modal=target_modal,
        payload={"source": "project_nudge"},
        risk_level=risk_level,  # type: ignore[arg-type]
        requires_confirmation=False,
    )


def _serialize_nudge(nudge: ProjectNudge) -> ProjectNudgeRead:
    return ProjectNudgeRead.model_validate(
        {
            **nudge.__dict__,
            "action": GuideActionRead.model_validate(nudge.action_payload),
        }
    )
