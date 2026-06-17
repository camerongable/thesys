import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.db.models import Artifact, Experiment, ResearchSprint, ValidationMission
from app.schemas.guide import (
    GuideActionRead,
    GuideChatResponseRead,
    GuideContextRead,
    GuideEvidenceSummaryRead,
    GuideRelatedEntityRead,
    GuideResponseRead,
)
from app.schemas.overview import NextBestActionRead, ProjectOverviewRead
from app.schemas.validation import DecisionCoachActionRead
from app.services import project_overview_service, thesis_service, validation_service, wedge_service


class GuideActionNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class _StageGuideCopy:
    focus: str
    why: str
    summary: str


_STAGE_GUIDE_COPY: dict[str, _StageGuideCopy] = {
    "draft_idea": _StageGuideCopy(
        focus="Shape the rough idea into a testable thesis.",
        why=(
            "The project does not yet have enough customer, problem, and proof context "
            "to make a strategic recommendation."
        ),
        summary=(
            "This idea is still rough. Start by clarifying who it is for and what must "
            "be true."
        ),
    ),
    "structured_intake": _StageGuideCopy(
        focus="Run the first research pass.",
        why=(
            "The thesis has structure, but it still needs evidence, substitutes, and "
            "competitor pressure before validation can be trusted."
        ),
        summary="The idea has a first shape. The next move is to ground it in research.",
    ),
    "brief_generated": _StageGuideCopy(
        focus="Pressure-test the thesis against competitors and substitutes.",
        why=(
            "A brief exists, but the wedge is not credible until the user understands "
            "what direct competitors, substitutes, and manual alternatives already solve."
        ),
        summary="Research exists. Now compare the opportunity against the market.",
    ),
    "competitors_analyzed": _StageGuideCopy(
        focus="Find the biggest unknown.",
        why=(
            "Competitor context is available. The leverage point is identifying the "
            "belief that could kill the idea before spending more time building."
        ),
        summary="The market has been mapped. Turn it into a clear validation blocker.",
    ),
    "assumptions_identified": _StageGuideCopy(
        focus="Turn the biggest unknown into a test.",
        why=(
            "Ranked assumptions are only useful when the riskiest one becomes a concrete "
            "validation plan with success and failure criteria."
        ),
        summary="The blocker is visible. Create the first proof to reduce uncertainty.",
    ),
    "validation_plan_created": _StageGuideCopy(
        focus="Run the blocker test.",
        why=(
            "A validation plan exists, but confidence should only change after real user "
            "evidence is logged."
        ),
        summary="The proof is planned. Run it and capture what happened.",
    ),
    "experiment_running": _StageGuideCopy(
        focus="Log real validation evidence.",
        why=(
            "The project is in validation. The next useful state change comes from "
            "recording outcomes, objections, and willingness-to-pay signals."
        ),
        summary="Validation is underway. Capture results before deciding.",
    ),
    "decision_ready": _StageGuideCopy(
        focus="Interpret the proof and record the decision.",
        why=(
            "Validation results exist. The app should help turn those results into a "
            "proceed, pivot, pause, kill, or continue-research decision."
        ),
        summary="There is enough signal to review the decision path.",
    ),
    "paused": _StageGuideCopy(
        focus="Decide whether this idea deserves another proof.",
        why="Paused ideas should stay parked unless there is a specific new learning goal.",
        summary="This idea is paused. Reopen it only around a concrete next proof.",
    ),
    "killed": _StageGuideCopy(
        focus="Preserve the learning trail.",
        why="Killed ideas are still useful when the evidence and rationale stay easy to revisit.",
        summary="This idea is closed unless new evidence changes the thesis.",
    ),
    "proceeding": _StageGuideCopy(
        focus="Set the next milestone from the validated wedge.",
        why=(
            "A proceed-style decision should stay tied to the evidence that justified it "
            "and the next proof that could change the plan."
        ),
        summary="A decision has been recorded. Use it to define the next milestone.",
    ),
}


def get_guide_context(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> GuideContextRead:
    overview = project_overview_service.get_project_overview(db, auth, project_id)
    return _guide_context_from_overview(db, auth, overview)


def recommend(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> GuideResponseRead:
    context = get_guide_context(db, auth, project_id)
    stage_copy = _STAGE_GUIDE_COPY.get(context.stage, _fallback_stage_copy(context.stage))
    recommended_action = context.available_actions[0]
    return GuideResponseRead(
        summary=stage_copy.summary,
        current_focus=stage_copy.focus,
        why_this_matters=stage_copy.why,
        after_that=_after_that_for_action(context, recommended_action),
        recommended_action=recommended_action,
        secondary_actions=context.available_actions[1:4],
        suggested_questions=_suggested_questions(context),
    )


def execute_action(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    action_id: str,
) -> GuideActionRead:
    context = get_guide_context(db, auth, project_id)
    for action in context.available_actions:
        if action.id == action_id:
            return action
    canonical_action_id = _canonical_action_id(action_id)
    for action in context.available_actions:
        if action.id == canonical_action_id:
            return action
    raise GuideActionNotFoundError(action_id)


def chat(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    message: str,
) -> GuideChatResponseRead:
    context = get_guide_context(db, auth, project_id)
    normalized = message.strip().lower()
    if not _is_in_scope(normalized):
        return GuideChatResponseRead(
            answer=(
                "I can help with this idea's thesis, evidence, blockers, validation, "
                "and decisions. Try asking what to validate next or why the current "
                "verdict is blocked."
            ),
            recommended_action=_action_by_id(context, "explain_current_focus"),
            action_cards=[_action_by_id(context, "explain_current_focus")],
            related_entities=_related_entities(context),
        )

    if any(
        term in normalized
        for term in (
            "what next",
            "next",
            "do now",
            "should i do",
            "open the right form",
            "right form",
            "open form",
        )
    ):
        action = context.available_actions[0]
        answer = (
            f"Do this next: {action.label}. {action.why_it_matters} "
            f"After that: {_after_that_for_action(context, action)}"
        )
        return _chat_response(answer, context, [action, *_support_actions(context)])

    if any(term in normalized for term in ("blocked", "blocker", "unknown", "risk", "missing")):
        unknown = context.biggest_unknown or "the strongest untested belief"
        missing_context = _join_list(context.missing_context) or (
            "none of the core context is missing"
        )
        answer = f"The idea is blocked by this: {unknown}. Missing context: {missing_context}."
        return _chat_response(answer, context, _support_actions(context))

    if any(term in normalized for term in ("evidence", "research", "sources", "findings")):
        evidence = context.evidence_summary
        answer = (
            f"The project has {evidence.sources} evidence sources, {evidence.competitors} "
            f"competitors or substitutes, {evidence.supported_findings} supported findings, "
            f"and {evidence.open_questions} open questions."
        )
        return _chat_response(
            answer,
            context,
            [_action_by_id(context, "show_blocker_evidence")],
        )

    if any(
        term in normalized
        for term in ("changed", "evolved", "evolution", "rejected", "directions", "history")
    ):
        detail = thesis_service.get_thesis_canvas(db, auth, project_id)
        rejected = _join_list(detail.canvas.rejected_directions) or "No rejected directions yet."
        latest = detail.evolution[-1] if detail.evolution else None
        latest_summary = latest.change_summary if latest else detail.canvas.current_thesis
        answer = (
            f"The idea started as: {detail.canvas.original_idea} "
            f"The current thesis is: {detail.canvas.current_thesis} "
            f"Latest change: {latest_summary} "
            f"Rejected directions: {rejected}"
        )
        return _chat_response(
            answer,
            context,
            [
                _action_by_id(context, "show_project_history"),
                _action_by_id(context, "rewrite_thesis_with_wedge"),
            ],
        )

    if any(term in normalized for term in ("thesis", "improve", "sharper", "shape")):
        thesis = context.current_thesis or "No thesis has been structured yet."
        answer = (
            f"Current thesis: {thesis} "
            "A sharper thesis should name one target user, one painful moment, the current "
            "workaround, and the proof that would change the decision."
        )
        return _chat_response(
            answer,
            context,
            [_action_by_id(context, "rewrite_thesis_with_wedge")],
        )

    if any(term in normalized for term in ("wedge", "compare", "alternative")):
        wedges = wedge_service.list_wedge_options(db, auth, project_id)
        recommended = next(
            (
                wedge
                for wedge in wedges.wedges
                if str(wedge.id) == str(wedges.recommended_wedge_id)
            ),
            None,
        )
        if recommended:
            answer = (
                f"Recommended wedge: {recommended.name}. "
                f"Why it might work: {recommended.why_it_might_work} "
                f"Main risk: {recommended.main_risk} "
                f"First test: {recommended.validation_test}"
            )
        else:
            wedge = context.current_wedge or "No clear wedge has been selected yet."
            answer = (
                f"Current wedge: {wedge} "
                "Open Wedge Explorer to compare possible directions before committing "
                "to a validation path."
            )
        return _chat_response(answer, context, [_action_by_id(context, "compare_wedge_options")])

    if any(term in normalized for term in ("outreach", "draft", "interview", "message")):
        target = context.target_user or "the target user"
        unknown = context.biggest_unknown or "the key assumption"
        answer = (
            f"Draft outreach: I am testing whether {target} has a painful enough problem "
            f"around {unknown}. Would you be open to a 20-minute conversation about how "
            "you handle this today?"
        )
        return _chat_response(
            answer,
            context,
            [_action_by_id(context, "draft_validation_outreach")],
        )

    if any(term in normalized for term in ("interpret", "result", "notes", "validate")):
        answer = (
            "Paste validation notes into the current mission, then compare the signal "
            "against the mission's success and failure criteria before changing confidence."
        )
        return _chat_response(
            answer,
            context,
            [_action_by_id(context, "interpret_validation_notes")],
        )

    if any(
        term in normalized
        for term in ("build", "decision", "proceed", "pivot", "pause", "kill")
    ):
        coach = validation_service.chat_decision_coach(db, auth, project_id, message)
        return GuideChatResponseRead(
            answer=coach.answer,
            recommended_action=_guide_action_from_decision_coach(
                project_id,
                coach.action_cards[0],
            )
            if coach.action_cards
            else context.available_actions[0],
            action_cards=[
                _guide_action_from_decision_coach(project_id, action)
                for action in coach.action_cards
            ],
            related_entities=_related_entities(context),
        )

    stage_copy = _STAGE_GUIDE_COPY.get(context.stage, _fallback_stage_copy(context.stage))
    return _chat_response(stage_copy.summary, context, context.available_actions[:3])


def _guide_context_from_overview(
    db: Session,
    auth: AuthContext,
    overview: ProjectOverviewRead,
) -> GuideContextRead:
    snapshot = overview.strategic_snapshot
    project = overview.project
    actions = _available_actions(overview)
    return GuideContextRead(
        project_id=project.id,
        project_name=project.name,
        stage=snapshot.current_stage,
        verdict=overview.current_recommendation.recommendation,
        next_action=overview.next_best_action.label,
        risk_level=_risk_level(overview),
        confidence_level=(
            "unknown"
            if snapshot.current_stage == "draft_idea" and overview.evidence_health.source_count == 0
            else snapshot.current_confidence
        ),
        current_thesis=snapshot.current_thesis,
        target_user=snapshot.target_user,
        primary_problem=snapshot.primary_problem,
        current_wedge=snapshot.proposed_wedge,
        biggest_unknown=_biggest_unknown(overview),
        active_validation_plan_id=_active_validation_plan_id(db, auth, project.id),
        latest_research_sprint_id=_latest_research_sprint_id(db, auth, project.id),
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


def _available_actions(overview: ProjectOverviewRead) -> list[GuideActionRead]:
    actions = [_guide_action_from_next_best(overview.next_best_action)]
    actions.extend(_guide_action_from_next_best(action) for action in overview.secondary_actions)
    actions.extend(_support_actions_for_overview(overview))

    deduped: list[GuideActionRead] = []
    seen: set[str] = set()
    for action in actions:
        if action.id in seen:
            continue
        seen.add(action.id)
        deduped.append(action)
    return deduped


def _guide_action_from_next_best(action: NextBestActionRead) -> GuideActionRead:
    label, description = _router_copy_for_next_best(action)
    return GuideActionRead(
        id=action.action_type,
        type=_action_type_for_next_best(action.action_type),
        label=label,
        description=description,
        why_it_matters=action.why_it_matters,
        target_route=action.target_route,
        target_modal=_target_modal_for_next_best(action.action_type),
        payload={"related_stage": action.related_stage},
        risk_level=_action_risk(action.action_type),
        requires_confirmation=action.action_type in {"use_suggested_decision", "resume_or_archive"},
    )


def _guide_action_from_decision_coach(
    project_id: uuid.UUID,
    action: DecisionCoachActionRead,
) -> GuideActionRead:
    return GuideActionRead(
        id=action.id,
        type="record_decision" if "record" in action.id else "navigate",
        label=action.label,
        description=action.description,
        why_it_matters=(
            "Decision actions keep the recommendation tied to evidence, missing proof, "
            "and a durable record."
        ),
        target_route=action.target_route or f"/projects/{project_id}#decisions",
        target_modal=action.target_modal,
        risk_level="high" if "record" in action.id else "low",
        requires_confirmation=False,
    )


def _support_actions_for_overview(overview: ProjectOverviewRead) -> list[GuideActionRead]:
    project_id = overview.project.id
    stage = overview.strategic_snapshot.current_stage
    actions = [
        GuideActionRead(
            id="explain_current_focus",
            type="explain",
            label="Explain why this is next",
            description="Show why this is the highest-leverage move right now.",
            why_it_matters=(
                "A clear reason helps the next step feel intentional instead of procedural."
            ),
            target_route=f"/projects/{project_id}#overview",
            risk_level="low",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="show_blocker_evidence",
            type="navigate",
            label="Show evidence behind the blocker",
            description="Open the research details that support the current blocker.",
            why_it_matters=(
                "The decision should stay tied to the evidence behind the current blocker."
            ),
            target_route=f"/projects/{project_id}#evidence",
            risk_level="low",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="rewrite_thesis_with_wedge",
            type="update_thesis",
            label="Rewrite thesis with current wedge",
            description="Open the thesis canvas to tighten the idea around the selected wedge.",
            why_it_matters=(
                "A sharper thesis makes research, validation, and decisions more useful."
            ),
            target_route=f"/projects/{project_id}#thesis-canvas",
            target_modal="thesis-canvas",
            risk_level="medium",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="show_project_history",
            type="navigate",
            label="Show project history",
            description="Open the idea evolution timeline and decision trail.",
            why_it_matters=(
                "The idea is easier to trust when you can see what changed and why."
            ),
            target_route=f"/projects/{project_id}#history",
            risk_level="low",
            requires_confirmation=False,
        ),
    ]
    if stage in {
        "structured_intake",
        "brief_generated",
        "competitors_analyzed",
        "assumptions_identified",
        "validation_plan_created",
        "experiment_running",
        "decision_ready",
        "proceeding",
    }:
        actions.append(
            GuideActionRead(
                id="compare_wedge_options",
                type="compare_wedges",
                label="Compare wedge options",
                description="Open Wedge Explorer to compare possible strategic directions.",
                why_it_matters="A narrow wedge is easier to validate than a broad product idea.",
                target_route=f"/projects/{project_id}#wedge-explorer",
                target_modal="wedge-explorer",
                risk_level="medium",
                requires_confirmation=False,
            )
        )
    if stage in {"assumptions_identified", "validation_plan_created", "experiment_running"}:
        actions.extend(
            [
                GuideActionRead(
                    id="open_validation_mission",
                    type="navigate",
                    label="Open current validation mission",
                    description="Open the current proof with steps, assets, and result logging.",
                    why_it_matters=(
                        "The mission keeps validation focused on the one proof that can "
                        "change the decision."
                    ),
                    target_route=f"/projects/{project_id}#validation-mission",
                    target_modal="validation-mission",
                    risk_level="low",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="draft_validation_outreach",
                    type="generate_draft",
                    label="Draft outreach for this proof",
                    description="Use the current blocker to draft validation outreach.",
                    why_it_matters="Outreach turns a plan into real user evidence.",
                    target_route=f"/projects/{project_id}#validation-mission",
                    target_modal="draft-outreach",
                    risk_level="low",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="open_validation_result_form",
                    type="log_result",
                    label="Open validation result form",
                    description="Open the mission result form.",
                    why_it_matters="Logged results are what should change confidence and verdicts.",
                    target_route=f"/projects/{project_id}#validation-mission",
                    target_modal="log-result",
                    risk_level="medium",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="interpret_validation_notes",
                    type="log_result",
                    label="Interpret validation notes",
                    description="Open the result area so pasted notes can be interpreted.",
                    why_it_matters=(
                        "Interpreting notes closes the loop from proof to confidence and decision."
                    ),
                    target_route=f"/projects/{project_id}#validation-mission",
                    target_modal="interpret-result",
                    risk_level="medium",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="explain_success_criteria",
                    type="explain",
                    label="Explain this proof's success criteria",
                    description="Explain what result would make the proof strong enough.",
                    why_it_matters=(
                        "Validation is only useful when success and failure are explicit "
                        "before results arrive."
                    ),
                    target_route=f"/projects/{project_id}#validation-mission",
                    risk_level="low",
                    requires_confirmation=False,
                ),
            ]
        )
    if stage in {"decision_ready", "proceeding", "paused", "killed"}:
        actions.append(
            GuideActionRead(
                id="prepare_decision_record",
                type="record_decision",
                label="Prepare decision record",
                description="Open the decision area with the recommendation context.",
                why_it_matters="Decision records preserve what changed and why.",
                target_route=f"/projects/{project_id}#record-decision-panel",
                target_modal="record-decision-panel",
                risk_level="high",
                requires_confirmation=False,
            )
        )
    return actions


def _action_type_for_next_best(action_type: str) -> str:
    if action_type in {"structure_idea"}:
        return "open_form"
    if action_type in {"generate_brief", "analyze_competitors", "create_validation_plan"}:
        return "run_workflow"
    if action_type in {"log_results", "add_results"}:
        return "log_result"
    if "decision" in action_type or action_type in {"resume_or_archive", "view_decision"}:
        return "record_decision"
    if "assumption" in action_type:
        return "explain"
    return "navigate"


def _router_copy_for_next_best(action: NextBestActionRead) -> tuple[str, str]:
    labels = {
        "structure_idea": (
            "Open thesis structure form",
            "Open the form that turns the rough idea into a testable thesis.",
        ),
        "generate_brief": (
            "Generate evidence-backed brief",
            "Run the brief workflow to ground the thesis in evidence and open questions.",
        ),
        "analyze_competitors": (
            "Run competitor analysis",
            "Open the research surface that maps direct competitors, substitutes, and wedges.",
        ),
        "review_assumptions": (
            "Open blocker assumptions",
            "Open the assumptions that explain what must be true before building.",
        ),
        "create_validation_plan": (
            "Create validation mission",
            "Open the test-planning surface for the riskiest assumption.",
        ),
        "start_experiment": (
            "Open current validation mission",
            "Open the proof that should produce the next real signal.",
        ),
        "log_results": (
            "Open validation result form",
            "Open the result form so real validation evidence can update confidence.",
        ),
        "add_results": (
            "Open validation result form",
            "Open the result form so real validation evidence can update confidence.",
        ),
        "use_suggested_decision": (
            "Prepare decision record",
            "Open the decision surface with the suggested proceed, pivot, pause, or kill path.",
        ),
        "record_decision": (
            "Prepare decision record",
            "Open the decision record form with the current evidence context.",
        ),
        "view_decision": (
            "Open recorded decision",
            "Open the decision trail that explains what was decided and why.",
        ),
        "resume_or_archive": (
            "Choose resume or archive path",
            "Open the decision area to decide whether this idea deserves another proof.",
        ),
    }
    return labels.get(action.action_type, (action.label, action.description))


def _target_modal_for_next_best(action_type: str) -> str | None:
    return {
        "structure_idea": "structured-intake",
        "log_results": "log-result",
        "add_results": "log-result",
        "record_decision": "record-decision-panel",
        "use_suggested_decision": "record-decision-panel",
    }.get(action_type)


def _action_risk(action_type: str) -> str:
    if action_type in {"use_suggested_decision", "resume_or_archive", "view_decision"}:
        return "high"
    if action_type in {"create_validation_plan", "log_results", "add_results"}:
        return "medium"
    return "low"


def _risk_level(overview: ProjectOverviewRead) -> str:
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


def _biggest_unknown(overview: ProjectOverviewRead) -> str | None:
    if overview.key_assumptions:
        return overview.key_assumptions[0].text
    if overview.key_risks:
        return overview.key_risks[0].text
    if overview.idea_readiness.weakest_area:
        return overview.idea_readiness.weakest_area
    return None


def _active_validation_plan_id(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> uuid.UUID | None:
    mission_id = db.scalar(
        select(ValidationMission.id)
        .where(
            ValidationMission.workspace_id == auth.workspace_id,
            ValidationMission.project_id == project_id,
            ValidationMission.status != "closed",
        )
        .order_by(ValidationMission.updated_at.desc())
        .limit(1)
    )
    if mission_id:
        return mission_id
    experiment_id = db.scalar(
        select(Experiment.id)
        .where(
            Experiment.workspace_id == auth.workspace_id,
            Experiment.project_id == project_id,
            Experiment.status.in_(["planned", "running"]),
        )
        .order_by(Experiment.updated_at.desc())
        .limit(1)
    )
    if experiment_id:
        return experiment_id
    return db.scalar(
        select(Artifact.id)
        .where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
            Artifact.artifact_type == "validation_plan",
        )
        .order_by(Artifact.updated_at.desc())
        .limit(1)
    )


def _latest_research_sprint_id(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> uuid.UUID | None:
    return db.scalar(
        select(ResearchSprint.id)
        .where(
            ResearchSprint.workspace_id == auth.workspace_id,
            ResearchSprint.project_id == project_id,
        )
        .order_by(ResearchSprint.created_at.desc())
        .limit(1)
    )


def _suggested_questions(context: GuideContextRead) -> list[str]:
    default_questions = [
        "What should I do next?",
        "Why is this blocked?",
        "Open the right form.",
        "What evidence is missing?",
        "Rewrite the thesis.",
        "Compare wedges.",
        "Draft outreach.",
        "Interpret notes.",
        "What would make this worth building?",
    ]
    stage_questions = {
        "draft_idea": [
            "What should I do next?",
            "Open the right form.",
            "Rewrite the thesis.",
            "What evidence is missing?",
        ],
        "structured_intake": [
            "What should I do next?",
            "Why is this blocked?",
            "What evidence is missing?",
            "Compare wedges.",
        ],
        "validation_plan_created": [
            "Why is this the blocker?",
            "Open the right form.",
            "Draft outreach.",
            "What results would change the decision?",
        ],
        "experiment_running": [
            "Open the right form.",
            "Interpret notes.",
            "What would make this worth building?",
        ],
        "decision_ready": [
            "What would make this worth building?",
            "What evidence is missing?",
            "Summarize the decision for my notes.",
        ],
    }
    return stage_questions.get(context.stage, default_questions)


def _is_in_scope(message: str) -> bool:
    allowed_terms = {
        "action",
        "assumption",
        "blocker",
        "build",
        "decision",
        "evidence",
        "experiment",
        "focus",
        "form",
        "idea",
        "changed",
        "directions",
        "interview",
        "kill",
        "evolution",
        "evolved",
        "missing",
        "mission",
        "next",
        "notes",
        "outreach",
        "pause",
        "pivot",
        "proceed",
        "proof",
        "rejected",
        "research",
        "result",
        "right",
        "risk",
        "source",
        "stage",
        "test",
        "criteria",
        "thesis",
        "validate",
        "validation",
        "verdict",
        "wedge",
        "worth",
    }
    return any(term in message for term in allowed_terms)


def _chat_response(
    answer: str,
    context: GuideContextRead,
    actions: list[GuideActionRead],
) -> GuideChatResponseRead:
    recommended_action = actions[0] if actions else context.available_actions[0]
    return GuideChatResponseRead(
        answer=answer,
        recommended_action=recommended_action,
        action_cards=actions[:4],
        related_entities=_related_entities(context),
    )


def _related_entities(context: GuideContextRead) -> list[GuideRelatedEntityRead]:
    entities = [
        GuideRelatedEntityRead(type="thesis", id=str(context.project_id), label="Current thesis"),
    ]
    if context.latest_research_sprint_id:
        entities.append(
            GuideRelatedEntityRead(
                type="research",
                id=str(context.latest_research_sprint_id),
                label="Latest research sprint",
            )
        )
    if context.active_validation_plan_id:
        entities.append(
            GuideRelatedEntityRead(
                type="validation_plan",
                id=str(context.active_validation_plan_id),
                label="Current validation mission",
            )
        )
    return entities


def _support_actions(context: GuideContextRead) -> list[GuideActionRead]:
    preferred = [
        "explain_current_focus",
        "show_blocker_evidence",
        "rewrite_thesis_with_wedge",
        "compare_wedge_options",
        "open_validation_mission",
        "draft_validation_outreach",
        "open_validation_result_form",
        "interpret_validation_notes",
        "explain_success_criteria",
        "prepare_decision_record",
        "show_project_history",
    ]
    return [
        action
        for action_id in preferred
        for action in context.available_actions
        if action.id == action_id
    ]


def _action_by_id(context: GuideContextRead, action_id: str) -> GuideActionRead:
    for action in context.available_actions:
        if action.id == action_id:
            return action
    canonical_action_id = _canonical_action_id(action_id)
    for action in context.available_actions:
        if action.id == canonical_action_id:
            return action
    return context.available_actions[0]


def _canonical_action_id(action_id: str) -> str:
    return {
        "show_evidence": "show_blocker_evidence",
        "update_thesis": "rewrite_thesis_with_wedge",
        "show_evolution": "show_project_history",
        "compare_wedges": "compare_wedge_options",
        "draft_outreach": "draft_validation_outreach",
        "log_results": "open_validation_result_form",
        "record_decision": "prepare_decision_record",
    }.get(action_id, action_id)


def _fallback_stage_copy(stage: str) -> _StageGuideCopy:
    return _StageGuideCopy(
        focus="Choose the next strategic step.",
        why=(
            f"The project is in {stage}, so the guide should route the user to the "
            "highest-leverage action."
        ),
        summary="Use the next recommended action to keep the idea moving.",
    )


def _after_that_for_action(context: GuideContextRead, action: GuideActionRead) -> str:
    if action.type == "open_form" or "thesis" in action.id:
        return (
            "I will use the sharper thesis to route you toward research, wedge choice, "
            "or a proof."
        )
    if action.type == "compare_wedges" or "wedge" in action.id:
        return "The selected wedge becomes the basis for the current thesis and validation mission."
    if action.type == "run_workflow" or "research" in action.id or "evidence" in action.id:
        return "I will use the evidence to update the blocker, recommendation, and next proof."
    if action.type == "log_result" or "result" in action.id or "validation" in action.id:
        return "I will interpret the signal and recommend continue, pivot, pause, kill, or proceed."
    if action.type == "record_decision" or "decision" in action.id:
        return (
            "The decision trail will preserve what changed, what evidence mattered, "
            "and what to revisit."
        )
    if context.stage == "decision_ready":
        return "I will help translate the current proof into a decision record."
    return (
        "I will route you to the next focused step and keep the project history tied "
        "to the action."
    )


def _join_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f", and {items[-1]}"
