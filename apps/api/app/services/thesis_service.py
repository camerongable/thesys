import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_permission
from app.db.models import (
    Artifact,
    Assumption,
    Decision,
    Experiment,
    ExperimentResult,
    Project,
    ProjectIntake,
    ProjectThesis,
    ThesisCanvas,
    ThesisEvolutionEvent,
    WedgeOption,
)
from app.schemas.thesis import (
    IdeaStoryRead,
    ThesisCanvasDetailRead,
    ThesisCanvasRead,
    ThesisCanvasUpdate,
    ThesisEvolutionEventRead,
)
from app.services import project_service


@dataclass(frozen=True)
class _CanvasSeed:
    original_idea: str
    current_thesis: str
    target_user: str
    problem: str
    current_workaround: str
    proposed_solution: str
    wedge: str
    biggest_unknown: str
    proof_needed: str
    rejected_directions: list[str]
    open_questions: list[str]


def get_thesis_canvas(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> ThesisCanvasDetailRead:
    canvas = _ensure_canvas(db, auth, project_id)
    return ThesisCanvasDetailRead(
        canvas=ThesisCanvasRead.model_validate(canvas),
        evolution=list_thesis_evolution(db, auth, project_id),
    )


def get_idea_story(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> IdeaStoryRead:
    detail = get_thesis_canvas(db, auth, project_id)
    canvas = detail.canvas
    latest_change = _latest_story_event(detail.evolution)
    selected_wedge = _selected_wedge(db, auth, project_id)
    rejected_directions = _story_rejected_directions(
        db,
        auth,
        project_id,
        canvas.rejected_directions,
    )
    why_it_changed = _story_change_reason(
        canvas=canvas,
        latest_change=latest_change,
        selected_wedge=selected_wedge,
        rejected_directions=rejected_directions,
    )
    return IdeaStoryRead(
        project_id=project_id,
        original_idea=canvas.original_idea,
        current_thesis=canvas.current_thesis,
        selected_wedge=selected_wedge or canvas.wedge or "No wedge has been selected yet.",
        rejected_directions=rejected_directions,
        why_it_changed=why_it_changed,
        current_blocker=canvas.biggest_unknown or "The biggest unknown has not been named yet.",
        next_proof=canvas.proof_needed or "Define the next proof that would change the decision.",
        latest_change_title=latest_change.title if latest_change else None,
        latest_change_reason=latest_change.reason if latest_change else None,
    )


def update_thesis_canvas(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: ThesisCanvasUpdate,
) -> ThesisCanvasDetailRead:
    require_permission(auth, "write_project")
    canvas = _ensure_canvas(db, auth, project_id)
    project = project_service.get_project(db, auth, project_id)
    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("change_reason", None)

    changed_fields: list[str] = []
    for field, value in update_data.items():
        if value is None:
            continue
        normalized = _normalize_value(value)
        current = getattr(canvas, field)
        if normalized == current:
            continue
        setattr(canvas, field, normalized)
        changed_fields.append(field)

    if "current_thesis" in changed_fields:
        thesis = ProjectThesis(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            version=_next_thesis_version(db, project.id),
            thesis_text=canvas.current_thesis,
            rationale=payload.change_reason
            or "Updated from the Thesis Canvas to keep the current idea versioned.",
            created_by=auth.user_id,
        )
        db.add(thesis)
        db.flush()
        project.current_thesis_id = thesis.id

    if changed_fields:
        _add_event(
            db,
            auth,
            project,
            event_type="manual_update",
            title="Thesis canvas updated",
            change_summary=(
                f"Updated {', '.join(_change_label(field) for field in changed_fields)}."
            ),
            reason=payload.change_reason
            or "The user refined the working thesis canvas.",
            source_entity_type="thesis_canvas",
            source_entity_id=canvas.id,
            origin="user",
        )

    db.commit()
    db.refresh(canvas)
    return get_thesis_canvas(db, auth, project_id)


def list_thesis_evolution(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[ThesisEvolutionEventRead]:
    project_service.get_project(db, auth, project_id)
    persisted = list(
        db.scalars(
            select(ThesisEvolutionEvent)
            .where(
                ThesisEvolutionEvent.workspace_id == auth.workspace_id,
                ThesisEvolutionEvent.project_id == project_id,
            )
            .order_by(ThesisEvolutionEvent.created_at)
        )
    )
    events = [ThesisEvolutionEventRead.model_validate(event) for event in persisted]
    events.extend(_derived_events(db, auth, project_id, events))
    return sorted(events, key=lambda event: event.created_at)


def _ensure_canvas(db: Session, auth: AuthContext, project_id: uuid.UUID) -> ThesisCanvas:
    project = project_service.get_project(db, auth, project_id)
    canvas = db.scalar(
        select(ThesisCanvas).where(
            ThesisCanvas.workspace_id == auth.workspace_id,
            ThesisCanvas.project_id == project_id,
        )
    )
    if canvas is not None:
        return canvas

    seed = _seed_from_project(db, auth, project)
    canvas = ThesisCanvas(
        workspace_id=auth.workspace_id,
        project_id=project.id,
        original_idea=seed.original_idea,
        current_thesis=seed.current_thesis,
        target_user=seed.target_user,
        problem=seed.problem,
        current_workaround=seed.current_workaround,
        proposed_solution=seed.proposed_solution,
        wedge=seed.wedge,
        biggest_unknown=seed.biggest_unknown,
        proof_needed=seed.proof_needed,
        rejected_directions=seed.rejected_directions,
        open_questions=seed.open_questions,
        created_by=auth.user_id,
    )
    db.add(canvas)
    db.flush()
    _seed_events(db, auth, project, canvas, seed)
    db.commit()
    db.refresh(canvas)
    return canvas


def _seed_from_project(db: Session, auth: AuthContext, project: Project) -> _CanvasSeed:
    intakes = list(
        db.scalars(
            select(ProjectIntake)
            .where(
                ProjectIntake.workspace_id == auth.workspace_id,
                ProjectIntake.project_id == project.id,
            )
            .order_by(ProjectIntake.created_at)
        )
    )
    first_intake = intakes[0] if intakes else None
    latest_intake = intakes[-1] if intakes else None
    thesis = project_service.current_thesis(project)
    assumptions = _top_assumptions(db, auth, project.id)
    active_experiment = _latest_experiment(db, auth, project.id)

    current_thesis = (
        thesis.thesis_text
        if thesis
        else project.short_description
        or "The current thesis has not been structured yet."
    )
    target_user = _first_nonempty(
        latest_intake.target_users[0] if latest_intake and latest_intake.target_users else None,
        project.customer_segments[0].name if project.customer_segments else None,
    )
    problem = _first_nonempty(
        project.problems[0].description if project.problems else None,
        latest_intake.problem_hypotheses[0]
        if latest_intake and latest_intake.problem_hypotheses
        else None,
    )
    current_workaround = _first_nonempty(
        project.problems[0].current_alternatives if project.problems else None,
        _workaround_from_problem(problem),
    )
    proposed_solution = _first_nonempty(
        latest_intake.proposed_solution if latest_intake else None,
        project.short_description,
    )
    biggest_unknown = _first_nonempty(
        assumptions[0].text if assumptions else None,
        latest_intake.key_uncertainties[0]
        if latest_intake and latest_intake.key_uncertainties
        else None,
    )
    proof_needed = _first_nonempty(
        active_experiment.success_criteria if active_experiment else None,
        assumptions[0].recommended_test if assumptions else None,
        "Define the proof that would change the decision.",
    )
    return _CanvasSeed(
        original_idea=_first_nonempty(
            first_intake.raw_idea if first_intake else None,
            project.short_description,
            current_thesis,
            project.name,
        ),
        current_thesis=current_thesis,
        target_user=target_user,
        problem=problem,
        current_workaround=current_workaround,
        proposed_solution=proposed_solution,
        wedge=_first_nonempty(_wedge_from_solution(proposed_solution, target_user)),
        biggest_unknown=biggest_unknown,
        proof_needed=proof_needed,
        rejected_directions=[],
        open_questions=_unique(
            [
                *(latest_intake.key_uncertainties if latest_intake else []),
                *(latest_intake.clarifying_questions if latest_intake else []),
            ]
        )[:8],
    )


def _seed_events(
    db: Session,
    auth: AuthContext,
    project: Project,
    canvas: ThesisCanvas,
    seed: _CanvasSeed,
) -> None:
    _add_event(
        db,
        auth,
        project,
        event_type="original_idea",
        title="Original idea captured",
        change_summary=seed.original_idea,
        reason="This is the earliest rough idea Thesys has for the project.",
        source_entity_type="project",
        source_entity_id=project.id,
        origin="system",
    )
    if seed.current_thesis:
        _add_event(
            db,
            auth,
            project,
            event_type="structured_thesis",
            title="Structured thesis created",
            change_summary=seed.current_thesis,
            reason="The rough idea was shaped into a working thesis for research and validation.",
            source_entity_type="thesis_canvas",
            source_entity_id=canvas.id,
            origin="system",
        )


def _add_event(
    db: Session,
    auth: AuthContext,
    project: Project,
    *,
    event_type: str,
    title: str,
    change_summary: str,
    reason: str,
    source_entity_type: str | None = None,
    source_entity_id: uuid.UUID | None = None,
    origin: str,
) -> ThesisEvolutionEvent:
    event = ThesisEvolutionEvent(
        workspace_id=auth.workspace_id,
        project_id=project.id,
        event_type=event_type,
        title=title,
        change_summary=_truncate(change_summary, 5000),
        reason=_truncate(reason, 5000),
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        origin=origin,
        created_by=auth.user_id if origin == "user" else None,
    )
    db.add(event)
    db.flush()
    return event


def _derived_events(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    persisted: list[ThesisEvolutionEventRead],
) -> list[ThesisEvolutionEventRead]:
    existing_keys = {
        (event.event_type, event.source_entity_type, str(event.source_entity_id))
        for event in persisted
        if event.source_entity_id
    }
    derived: list[ThesisEvolutionEventRead] = []
    research = _latest_artifact(db, auth, project_id, ["research_memo", "opportunity_brief"])
    if research and ("research_update", "artifact", str(research.id)) not in existing_keys:
        derived.append(
            _derived_event(
                project_id,
                source_id=research.id,
                created_at=research.updated_at,
                event_type="research_update",
                title="Research-informed thesis",
                change_summary=f"{research.title} added evidence to the thesis.",
                reason=(
                    "Research artifacts can sharpen the target user, problem, wedge, and "
                    "open questions."
                ),
                source_entity_type="artifact",
            )
        )

    assumption = _top_assumptions(db, auth, project_id, limit=1)
    if (
        assumption
        and ("validation_blocker", "assumption", str(assumption[0].id)) not in existing_keys
    ):
        derived.append(
            _derived_event(
                project_id,
                source_id=assumption[0].id,
                created_at=assumption[0].updated_at,
                event_type="validation_blocker",
                title="Biggest unknown identified",
                change_summary=assumption[0].text,
                reason="The highest-risk assumption became the proof the idea needs next.",
                source_entity_type="assumption",
            )
        )

    result = db.scalar(
        select(ExperimentResult)
        .where(
            ExperimentResult.workspace_id == auth.workspace_id,
            ExperimentResult.project_id == project_id,
        )
        .order_by(ExperimentResult.created_at.desc())
        .limit(1)
    )
    if result and ("validation_blocker", "experiment_result", str(result.id)) not in existing_keys:
        derived.append(
            _derived_event(
                project_id,
                source_id=result.id,
                created_at=result.created_at,
                event_type="validation_blocker",
                title="Validation result logged",
                change_summary=result.result_summary,
                reason="Real validation evidence can change confidence and the next decision.",
                source_entity_type="experiment_result",
            )
        )

    decision = db.scalar(
        select(Decision)
        .where(Decision.workspace_id == auth.workspace_id, Decision.project_id == project_id)
        .order_by(Decision.created_at.desc())
        .limit(1)
    )
    if decision and ("decision", "decision", str(decision.id)) not in existing_keys:
        derived.append(
            _derived_event(
                project_id,
                source_id=decision.id,
                created_at=decision.created_at,
                event_type="decision",
                title="Decision recorded",
                change_summary=decision.title,
                reason=decision.rationale or "The project decision trail captured this choice.",
                source_entity_type="decision",
            )
        )
    return derived


def _derived_event(
    project_id: uuid.UUID,
    *,
    source_id: uuid.UUID,
    created_at: datetime,
    event_type: str,
    title: str,
    change_summary: str,
    reason: str,
    source_entity_type: str,
) -> ThesisEvolutionEventRead:
    event_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"thesys:thesis-evolution:{project_id}:{event_type}:{source_entity_type}:{source_id}",
    )
    return ThesisEvolutionEventRead.model_validate(
        {
            "id": event_id,
            "project_id": project_id,
            "event_type": event_type,
            "title": title,
            "change_summary": change_summary,
            "reason": reason,
            "source_entity_type": source_entity_type,
            "source_entity_id": source_id,
            "origin": "agent",
            "created_at": created_at,
        }
    )


def _latest_artifact(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    artifact_types: list[str],
) -> Artifact | None:
    return db.scalar(
        select(Artifact)
        .where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
            Artifact.artifact_type.in_(artifact_types),
        )
        .order_by(Artifact.updated_at.desc())
        .limit(1)
    )


def _top_assumptions(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    limit: int = 5,
) -> list[Assumption]:
    return list(
        db.scalars(
            select(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
            )
            .order_by(
                Assumption.kill_risk.desc(),
                Assumption.importance.desc(),
                Assumption.uncertainty.desc(),
                Assumption.updated_at.desc(),
            )
            .limit(limit)
        )
    )


def _latest_experiment(db: Session, auth: AuthContext, project_id: uuid.UUID) -> Experiment | None:
    return db.scalar(
        select(Experiment)
        .where(Experiment.workspace_id == auth.workspace_id, Experiment.project_id == project_id)
        .order_by(Experiment.updated_at.desc())
        .limit(1)
    )


def _latest_story_event(
    events: list[ThesisEvolutionEventRead],
) -> ThesisEvolutionEventRead | None:
    priority = {
        "decision": 5,
        "validation_blocker": 4,
        "wedge_change": 3,
        "research_update": 2,
        "manual_update": 2,
        "structured_thesis": 1,
        "original_idea": 0,
    }
    ranked = sorted(
        events,
        key=lambda event: (priority.get(event.event_type, 0), event.created_at),
        reverse=True,
    )
    return ranked[0] if ranked else None


def _selected_wedge(db: Session, auth: AuthContext, project_id: uuid.UUID) -> str:
    wedge = db.scalar(
        select(WedgeOption)
        .where(
            WedgeOption.workspace_id == auth.workspace_id,
            WedgeOption.project_id == project_id,
            WedgeOption.recommendation == "recommended",
        )
        .order_by(WedgeOption.updated_at.desc())
        .limit(1)
    )
    return wedge.name if wedge else ""


def _story_rejected_directions(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    canvas_rejected: list[str],
) -> list[str]:
    wedge_directions = list(
        db.scalars(
            select(WedgeOption.name)
            .where(
                WedgeOption.workspace_id == auth.workspace_id,
                WedgeOption.project_id == project_id,
                WedgeOption.recommendation.in_(["rejected", "avoid_for_now"]),
            )
            .order_by(WedgeOption.updated_at.desc())
            .limit(3)
        )
    )
    return _unique([*canvas_rejected, *wedge_directions])[:4]


def _story_change_reason(
    *,
    canvas: ThesisCanvasRead,
    latest_change: ThesisEvolutionEventRead | None,
    selected_wedge: str,
    rejected_directions: list[str],
) -> str:
    if latest_change and latest_change.reason:
        return latest_change.reason
    if selected_wedge and rejected_directions:
        return (
            f"The idea narrowed toward {selected_wedge} while keeping "
            f"{rejected_directions[0]} out of the default path for now."
        )
    if selected_wedge:
        return (
            f"The current story centers on {selected_wedge} because a narrower wedge is "
            "easier to validate than the broad original idea."
        )
    return "The idea has been captured, but it still needs a clearer wedge and proof path."


def _next_thesis_version(db: Session, project_id: uuid.UUID) -> int:
    version = db.scalar(
        select(func.max(ProjectThesis.version)).where(ProjectThesis.project_id == project_id)
    )
    return int(version or 0) + 1


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return _unique([str(item).strip() for item in value if str(item).strip()])
    return value


def _change_label(field: str) -> str:
    return field.replace("_", " ")


def _first_nonempty(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        normalized = value.strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)
    return cleaned


def _workaround_from_problem(problem: str) -> str:
    if not problem:
        return "Current workaround has not been captured yet."
    return "The current workaround still needs to be captured from users."


def _wedge_from_solution(solution: str, target_user: str) -> str:
    if not solution:
        return ""
    first_sentence = solution.split(".")[0].strip()
    if target_user:
        return f"{first_sentence} for {target_user}"
    return first_sentence


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else f"{value[: limit - 1].rstrip()}…"
