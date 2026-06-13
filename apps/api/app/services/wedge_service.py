import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_permission
from app.db.models import (
    Assumption,
    Claim,
    Competitor,
    EvidenceSource,
    Project,
    ThesisCanvas,
    ThesisEvolutionEvent,
    WedgeOption,
)
from app.schemas.wedges import WedgeActionRead, WedgeOptionListRead, WedgeOptionRead
from app.services import project_service, thesis_service


class WedgeOptionNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class _WedgeSpec:
    name: str
    description: str
    target_user: str
    problem_focus: str
    why_it_might_work: str
    main_risk: str
    competitor_pressure: str
    evidence_strength: str
    validation_test: str
    recommendation: str
    source_ids: list[str]


def list_wedge_options(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> WedgeOptionListRead:
    project_service.get_project(db, auth, project_id)
    wedges = _query_wedges(db, auth, project_id)
    return _list_read(wedges)


def generate_wedge_options(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> WedgeOptionListRead:
    require_permission(auth, "write_project")
    project = project_service.get_project(db, auth, project_id)
    canvas = thesis_service._ensure_canvas(db, auth, project_id)  # noqa: SLF001
    specs = _generate_specs(db, auth, project, canvas)
    existing = {
        _key(option.name): option
        for option in _query_wedges(db, auth, project_id)
        if option.recommendation != "rejected"
    }

    for spec in specs:
        option = existing.get(_key(spec.name))
        if option is None:
            db.add(
                WedgeOption(
                    workspace_id=auth.workspace_id,
                    project_id=project.id,
                    name=spec.name,
                    description=spec.description,
                    target_user=spec.target_user,
                    problem_focus=spec.problem_focus,
                    why_it_might_work=spec.why_it_might_work,
                    main_risk=spec.main_risk,
                    competitor_pressure=spec.competitor_pressure,
                    evidence_strength=spec.evidence_strength,
                    validation_test=spec.validation_test,
                    recommendation=spec.recommendation,
                    source_ids=spec.source_ids,
                    created_by=auth.user_id,
                )
            )
            continue
        option.description = spec.description
        option.target_user = spec.target_user
        option.problem_focus = spec.problem_focus
        option.why_it_might_work = spec.why_it_might_work
        option.main_risk = spec.main_risk
        option.competitor_pressure = spec.competitor_pressure
        option.evidence_strength = spec.evidence_strength
        option.validation_test = spec.validation_test
        option.source_ids = spec.source_ids
        if option.recommendation != "recommended":
            option.recommendation = spec.recommendation

    db.flush()
    _ensure_single_recommended(db, auth, project_id, preferred_name=canvas.wedge)
    db.commit()
    return list_wedge_options(db, auth, project_id)


def select_wedge(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    wedge_id: uuid.UUID,
) -> WedgeActionRead:
    require_permission(auth, "write_project")
    project = project_service.get_project(db, auth, project_id)
    option = _get_wedge(db, auth, project_id, wedge_id)
    _ensure_single_recommended(db, auth, project_id, preferred_wedge_id=option.id)
    canvas = thesis_service._ensure_canvas(db, auth, project_id)  # noqa: SLF001
    _apply_wedge_to_canvas(canvas, option)
    _add_wedge_event(
        db,
        auth,
        project,
        option,
        title="Wedge selected",
        reason=(
            "The selected wedge became the current strategic direction so validation can "
            "focus on one testable path."
        ),
    )
    db.commit()
    db.refresh(option)
    return WedgeActionRead(
        wedge=WedgeOptionRead.model_validate(option),
        message=f"{option.name} is now the selected wedge on the Thesis Canvas.",
    )


def reject_wedge(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    wedge_id: uuid.UUID,
) -> WedgeActionRead:
    require_permission(auth, "write_project")
    project = project_service.get_project(db, auth, project_id)
    option = _get_wedge(db, auth, project_id, wedge_id)
    option.recommendation = "rejected"
    _ensure_single_recommended(db, auth, project_id)
    canvas = thesis_service._ensure_canvas(db, auth, project_id)  # noqa: SLF001
    canvas.rejected_directions = _append_unique(canvas.rejected_directions, option.name)
    _add_wedge_event(
        db,
        auth,
        project,
        option,
        title="Wedge rejected",
        reason=(
            "This direction was rejected for now and preserved so the idea evolution "
            "trail shows what was considered."
        ),
    )
    db.commit()
    db.refresh(option)
    return WedgeActionRead(
        wedge=WedgeOptionRead.model_validate(option),
        message=f"{option.name} was moved to rejected directions.",
    )


def test_wedge(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    wedge_id: uuid.UUID,
) -> WedgeActionRead:
    require_permission(auth, "write_project")
    project = project_service.get_project(db, auth, project_id)
    option = _get_wedge(db, auth, project_id, wedge_id)
    _ensure_single_recommended(db, auth, project_id, preferred_wedge_id=option.id)
    canvas = thesis_service._ensure_canvas(db, auth, project_id)  # noqa: SLF001
    _apply_wedge_to_canvas(canvas, option)
    canvas.biggest_unknown = option.main_risk
    canvas.proof_needed = option.validation_test
    _add_wedge_event(
        db,
        auth,
        project,
        option,
        title="Wedge moved to validation",
        reason=(
            "The wedge was converted into a proof target. The next useful step is to run "
            "the validation test and log results."
        ),
    )
    db.commit()
    db.refresh(option)
    return WedgeActionRead(
        wedge=WedgeOptionRead.model_validate(option),
        message=f"{option.name} is ready to test: {option.validation_test}",
    )


def mark_research_later(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    wedge_id: uuid.UUID,
) -> WedgeActionRead:
    require_permission(auth, "write_project")
    project_service.get_project(db, auth, project_id)
    option = _get_wedge(db, auth, project_id, wedge_id)
    option.recommendation = "research_later"
    canvas = thesis_service._ensure_canvas(db, auth, project_id)  # noqa: SLF001
    canvas.open_questions = _append_unique(
        canvas.open_questions,
        f"What evidence would make {option.name} worth testing?",
    )
    db.commit()
    db.refresh(option)
    return WedgeActionRead(
        wedge=WedgeOptionRead.model_validate(option),
        message=f"{option.name} was marked for more research.",
    )


def _query_wedges(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[WedgeOption]:
    return list(
        db.scalars(
            select(WedgeOption)
            .where(
                WedgeOption.workspace_id == auth.workspace_id,
                WedgeOption.project_id == project_id,
            )
            .order_by(
                WedgeOption.recommendation == "rejected",
                WedgeOption.recommendation != "recommended",
                WedgeOption.updated_at.desc(),
            )
        )
    )


def _ensure_single_recommended(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    preferred_wedge_id: uuid.UUID | None = None,
    preferred_name: str | None = None,
) -> None:
    wedges = _query_wedges(db, auth, project_id)
    selectable = [wedge for wedge in wedges if wedge.recommendation != "rejected"]
    if not selectable:
        return

    preferred = None
    if preferred_wedge_id is not None:
        preferred = next((wedge for wedge in selectable if wedge.id == preferred_wedge_id), None)
    if preferred is None and preferred_name:
        preferred_key = _key(preferred_name)
        preferred = next((wedge for wedge in selectable if _key(wedge.name) == preferred_key), None)
    if preferred is None:
        preferred = next(
            (wedge for wedge in selectable if wedge.recommendation == "recommended"),
            selectable[0],
        )

    for wedge in selectable:
        if wedge.id == preferred.id:
            wedge.recommendation = "recommended"
        elif wedge.recommendation == "recommended":
            wedge.recommendation = "promising"


def _get_wedge(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    wedge_id: uuid.UUID,
) -> WedgeOption:
    option = db.scalar(
        select(WedgeOption).where(
            WedgeOption.id == wedge_id,
            WedgeOption.workspace_id == auth.workspace_id,
            WedgeOption.project_id == project_id,
        )
    )
    if option is None:
        raise WedgeOptionNotFoundError(str(wedge_id))
    return option


def _list_read(wedges: list[WedgeOption]) -> WedgeOptionListRead:
    recommended = next((wedge for wedge in wedges if wedge.recommendation == "recommended"), None)
    if recommended:
        summary = (
            f"Recommended wedge: {recommended.name}. "
            f"Why: {recommended.why_it_might_work}"
        )
    elif wedges:
        summary = "Review the wedge options and choose the narrowest path worth testing first."
    else:
        summary = "Generate wedge options to compare what this idea could become."
    return WedgeOptionListRead(
        wedges=[WedgeOptionRead.model_validate(wedge) for wedge in wedges],
        recommended_wedge_id=recommended.id if recommended else None,
        recommendation_summary=summary,
    )


def _generate_specs(
    db: Session,
    auth: AuthContext,
    project: Project,
    canvas: ThesisCanvas,
) -> list[_WedgeSpec]:
    source_ids = [
        str(source_id)
        for source_id in db.scalars(
            select(EvidenceSource.id)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project.id,
            )
            .order_by(EvidenceSource.created_at.desc())
            .limit(5)
        )
    ]
    competitor_count = int(
        db.scalar(
            select(func.count(Competitor.id)).where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project.id,
            )
        )
        or 0
    )
    high_threat_count = int(
        db.scalar(
            select(func.count(Competitor.id)).where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project.id,
                Competitor.threat_level == "high",
            )
        )
        or 0
    )
    supported_claims = int(
        db.scalar(
            select(func.count(Claim.id)).where(
                Claim.workspace_id == auth.workspace_id,
                Claim.project_id == project.id,
                Claim.support_level.in_(["supported", "partial"]),
            )
        )
        or 0
    )
    source_count = len(source_ids)
    target_user = _fallback(canvas.target_user, "the first target customer segment")
    problem = _fallback(canvas.problem, "the most urgent problem in the current thesis")
    workaround = _fallback(canvas.current_workaround, "their current workaround")
    current_wedge = _fallback(canvas.wedge, _short_phrase(canvas.proposed_solution), project.name)
    biggest_unknown = _fallback(
        canvas.biggest_unknown,
        _top_assumption_text(db, auth, project.id),
        "Whether this is painful enough to create switching or willingness-to-pay signal.",
    )
    proof_needed = _fallback(
        canvas.proof_needed,
        "Interview five target users and look for a clear willingness-to-pay or pilot signal.",
    )
    competitor_pressure = _competitor_pressure(competitor_count, high_threat_count)
    evidence_strength = _evidence_strength(source_count, supported_claims)

    broad_name = f"Broad {project.name} concept"
    if project.name.lower().endswith("idea"):
        broad_name = "Broad original concept"

    return [
        _WedgeSpec(
            name=_title(current_wedge) or "Focused workflow wedge",
            description=(
                f"Narrow the idea around {current_wedge} for {target_user}, instead of "
                "trying to validate the whole product at once."
            ),
            target_user=target_user,
            problem_focus=problem,
            why_it_might_work=(
                "It is closest to the current thesis and can be tested with a small number "
                "of specific user conversations."
            ),
            main_risk=biggest_unknown,
            competitor_pressure=competitor_pressure,
            evidence_strength=evidence_strength,
            validation_test=proof_needed,
            recommendation="recommended",
            source_ids=source_ids,
        ),
        _WedgeSpec(
            name="Manual workaround replacement",
            description=(
                f"Focus on replacing the painful parts of {workaround} before proposing a "
                "full new product category."
            ),
            target_user=target_user,
            problem_focus=f"Time, error, or coordination pain in {workaround}",
            why_it_might_work=(
                "It tests a concrete before/after workflow and can reveal whether the "
                "existing workaround is painful enough to switch from."
            ),
            main_risk=(
                "Users may tolerate the current workaround or solve it with lightweight habits."
            ),
            competitor_pressure="low" if competitor_pressure == "low" else "medium",
            evidence_strength=evidence_strength,
            validation_test=(
                "Ask five target users to walk through the last time this workaround failed, "
                "then test whether they would pay for a narrower replacement."
            ),
            recommendation="promising",
            source_ids=source_ids,
        ),
        _WedgeSpec(
            name="High-urgency segment wedge",
            description=(
                f"Find the subset of {target_user} with the most frequent or expensive "
                "version of the problem."
            ),
            target_user=f"High-urgency subset of {target_user}",
            problem_focus=f"The most expensive or frequent form of {problem}",
            why_it_might_work=(
                "A smaller segment with stronger pain is usually easier to validate than a "
                "broad audience with weak urgency."
            ),
            main_risk="The high-urgency segment may be too small or hard to reach.",
            competitor_pressure=competitor_pressure,
            evidence_strength="weak" if evidence_strength == "none" else evidence_strength,
            validation_test=(
                "Recruit five users who experienced this problem in the last 30 days and "
                "compare urgency against the broader segment."
            ),
            recommendation="promising",
            source_ids=source_ids,
        ),
        _WedgeSpec(
            name=broad_name,
            description=(
                "Keep the original broad product concept as the strategy and validate it as "
                "one general-purpose offer."
            ),
            target_user=target_user,
            problem_focus=problem,
            why_it_might_work=(
                "The broad concept may still be useful if users already describe the full "
                "bundle as a must-have."
            ),
            main_risk="Broad ideas are harder to validate and often collide with free substitutes.",
            competitor_pressure="high" if competitor_count else "medium",
            evidence_strength=evidence_strength,
            validation_test=(
                "Run a landing page or interview test that measures whether users understand "
                "and want the whole concept without narrowing."
            ),
            recommendation="avoid_for_now",
            source_ids=source_ids,
        ),
        _WedgeSpec(
            name="Research-later adjacent wedge",
            description=(
                "Hold an adjacent use case as a backup path until the first proof produces "
                "stronger evidence."
            ),
            target_user=target_user,
            problem_focus="Adjacent problem discovered during research",
            why_it_might_work=(
                "It preserves optionality without distracting from the first validation mission."
            ),
            main_risk="Researching adjacent paths too early can diffuse the thesis.",
            competitor_pressure="medium",
            evidence_strength="weak" if evidence_strength == "none" else evidence_strength,
            validation_test=(
                "Only test this path if the recommended wedge fails or exposes stronger pain."
            ),
            recommendation="research_later",
            source_ids=source_ids,
        ),
    ]


def _apply_wedge_to_canvas(canvas: ThesisCanvas, option: WedgeOption) -> None:
    canvas.wedge = option.name
    canvas.target_user = option.target_user
    canvas.problem = option.problem_focus
    canvas.proof_needed = option.validation_test
    if not canvas.current_thesis or "not been structured" in canvas.current_thesis.lower():
        canvas.current_thesis = f"{option.target_user} need {option.problem_focus}."


def _add_wedge_event(
    db: Session,
    auth: AuthContext,
    project: Project,
    option: WedgeOption,
    *,
    title: str,
    reason: str,
) -> None:
    db.add(
        ThesisEvolutionEvent(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            event_type="wedge_change",
            title=title,
            change_summary=f"{option.name}: {option.description}",
            reason=reason,
            source_entity_type="wedge_option",
            source_entity_id=option.id,
            origin="user",
            created_by=auth.user_id,
        )
    )


def _top_assumption_text(db: Session, auth: AuthContext, project_id: uuid.UUID) -> str:
    assumption = db.scalar(
        select(Assumption)
        .where(Assumption.workspace_id == auth.workspace_id, Assumption.project_id == project_id)
        .order_by(
            Assumption.kill_risk.desc(),
            Assumption.importance.desc(),
            Assumption.uncertainty.desc(),
            Assumption.updated_at.desc(),
        )
        .limit(1)
    )
    return assumption.text if assumption else ""


def _competitor_pressure(competitor_count: int, high_threat_count: int) -> str:
    if high_threat_count > 0 or competitor_count >= 5:
        return "high"
    if competitor_count >= 2:
        return "medium"
    return "low"


def _evidence_strength(source_count: int, supported_claims: int) -> str:
    if source_count == 0 and supported_claims == 0:
        return "none"
    if source_count < 3 and supported_claims < 3:
        return "weak"
    if source_count >= 5 and supported_claims >= 8:
        return "strong"
    return "partial"


def _append_unique(values: list[str], value: str) -> list[str]:
    normalized = value.strip()
    if not normalized:
        return values
    seen = {item.casefold() for item in values}
    if normalized.casefold() in seen:
        return values
    return [*values, normalized]


def _fallback(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _short_phrase(value: str) -> str:
    return value.split(".")[0].strip() if value else ""


def _title(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return value[0].upper() + value[1:]


def _key(value: str) -> str:
    return " ".join(value.casefold().split())
