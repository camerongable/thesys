import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.db.models import Artifact, Experiment, ResearchSprint
from app.schemas.guide import (
    GuideActionRead,
    GuideChatResponseRead,
    GuideContextRead,
    GuideEvidenceSummaryRead,
    GuideRelatedEntityRead,
    GuideResponseRead,
)
from app.schemas.overview import NextBestActionRead, ProjectOverviewRead
from app.services import project_overview_service


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
        recommended_action=recommended_action,
        secondary_actions=context.available_actions[1:5],
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
            action_cards=[_action_by_id(context, "explain_current_focus")],
            related_entities=_related_entities(context),
        )

    if any(term in normalized for term in ("what next", "next", "do now", "should i do")):
        action = context.available_actions[0]
        answer = (
            f"You should {action.label.lower()}. {action.why_it_matters} "
            f"The current focus is: {context.next_action}."
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
        return _chat_response(answer, context, [_action_by_id(context, "show_evidence")])

    if any(term in normalized for term in ("thesis", "improve", "sharper", "shape")):
        thesis = context.current_thesis or "No thesis has been structured yet."
        answer = (
            f"Current thesis: {thesis} "
            "A sharper thesis should name one target user, one painful moment, the current "
            "workaround, and the proof that would change the decision."
        )
        return _chat_response(answer, context, [_action_by_id(context, "update_thesis")])

    if any(term in normalized for term in ("wedge", "compare", "alternative")):
        wedge = context.current_wedge or "No clear wedge has been selected yet."
        answer = (
            f"Current wedge: {wedge} "
            "The best wedge is usually the narrowest direction with strong pain, reachable "
            "users, and lower competitor pressure."
        )
        return _chat_response(answer, context, [_action_by_id(context, "compare_wedges")])

    if any(term in normalized for term in ("outreach", "draft", "interview", "message")):
        target = context.target_user or "the target user"
        unknown = context.biggest_unknown or "the key assumption"
        answer = (
            f"Draft outreach: I am testing whether {target} has a painful enough problem "
            f"around {unknown}. Would you be open to a 20-minute conversation about how "
            "you handle this today?"
        )
        return _chat_response(answer, context, [_action_by_id(context, "draft_outreach")])

    if any(term in normalized for term in ("interpret", "result", "notes", "validate")):
        answer = (
            "Paste validation notes into the test area, then compare the signal against "
            "the mission's success and failure criteria before changing confidence."
        )
        return _chat_response(answer, context, [_action_by_id(context, "log_results")])

    if any(term in normalized for term in ("decision", "proceed", "pivot", "pause", "kill")):
        answer = (
            f"Current verdict: {context.verdict} "
            "A durable decision should cite the evidence, name what is still missing, "
            "and define what would cause you to revisit it."
        )
        return _chat_response(answer, context, [_action_by_id(context, "record_decision")])

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
    return GuideActionRead(
        id=action.action_type,
        type=_action_type_for_next_best(action.action_type),
        label=action.label,
        description=action.description,
        why_it_matters=action.why_it_matters,
        target_route=action.target_route,
        target_modal=_target_modal_for_next_best(action.action_type),
        payload={"related_stage": action.related_stage},
        risk_level=_action_risk(action.action_type),
        requires_confirmation=action.action_type in {"use_suggested_decision", "resume_or_archive"},
    )


def _support_actions_for_overview(overview: ProjectOverviewRead) -> list[GuideActionRead]:
    project_id = overview.project.id
    stage = overview.strategic_snapshot.current_stage
    actions = [
        GuideActionRead(
            id="explain_current_focus",
            type="explain",
            label="Explain focus",
            description="Explain why this is the right thing to focus on now.",
            why_it_matters=(
                "A clear reason helps the next step feel intentional instead of procedural."
            ),
            target_route=f"/projects/{project_id}#overview",
            risk_level="low",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="show_evidence",
            type="navigate",
            label="Show evidence",
            description="Open the research and evidence trail.",
            why_it_matters="Evidence is what keeps the recommendation grounded.",
            target_route=f"/projects/{project_id}#evidence",
            risk_level="low",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="update_thesis",
            type="update_thesis",
            label="Improve thesis",
            description="Open the thesis intake area to sharpen the idea.",
            why_it_matters=(
                "A sharper thesis makes research, validation, and decisions more useful."
            ),
            target_route=f"/projects/{project_id}#structured-intake",
            target_modal="structured-intake",
            risk_level="medium",
            requires_confirmation=False,
        ),
    ]
    if stage in {
        "brief_generated",
        "competitors_analyzed",
        "assumptions_identified",
        "validation_plan_created",
        "experiment_running",
    }:
        actions.append(
            GuideActionRead(
                id="compare_wedges",
                type="compare_wedges",
                label="Compare wedges",
                description="Review competitors, substitutes, and the current positioning gap.",
                why_it_matters="A narrow wedge is easier to validate than a broad product idea.",
                target_route=f"/projects/{project_id}#competitors",
                risk_level="medium",
                requires_confirmation=False,
            )
        )
    if stage in {"assumptions_identified", "validation_plan_created", "experiment_running"}:
        actions.extend(
            [
                GuideActionRead(
                    id="draft_outreach",
                    type="generate_draft",
                    label="Draft outreach",
                    description="Use the current blocker to draft validation outreach.",
                    why_it_matters="Outreach turns a plan into real user evidence.",
                    target_route=f"/projects/{project_id}#validation-tests",
                    target_modal="draft-outreach",
                    risk_level="low",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="log_results",
                    type="log_result",
                    label="Log results",
                    description="Open the validation result form.",
                    why_it_matters="Logged results are what should change confidence and verdicts.",
                    target_route=f"/projects/{project_id}#validation-tests",
                    target_modal="log-result",
                    risk_level="medium",
                    requires_confirmation=False,
                ),
            ]
        )
    if stage in {"decision_ready", "proceeding", "paused", "killed"}:
        actions.append(
            GuideActionRead(
                id="record_decision",
                type="record_decision",
                label="Review decision",
                description="Open the decision record area.",
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


def _target_modal_for_next_best(action_type: str) -> str | None:
    return {
        "structure_idea": "structured-intake",
        "log_results": "log-result",
        "add_results": "log-result",
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
    stage_questions = {
        "draft_idea": [
            "What context is missing?",
            "How should I sharpen the thesis?",
            "What should I do next?",
        ],
        "structured_intake": [
            "What should the first research pass look for?",
            "What evidence is missing?",
            "Why not build yet?",
        ],
        "validation_plan_created": [
            "Why is this the blocker?",
            "Draft outreach for this test.",
            "What results would change the decision?",
        ],
        "experiment_running": [
            "How should I log these results?",
            "What signal would be strong enough?",
            "What happens after validation?",
        ],
        "decision_ready": [
            "Should I proceed?",
            "What evidence is missing?",
            "Summarize the decision for my notes.",
        ],
    }
    return stage_questions.get(
        context.stage,
        ["What should I do next?", "Why does this matter?", "What evidence is missing?"],
    )


def _is_in_scope(message: str) -> bool:
    allowed_terms = {
        "action",
        "assumption",
        "blocker",
        "decision",
        "evidence",
        "experiment",
        "focus",
        "idea",
        "interview",
        "missing",
        "next",
        "notes",
        "outreach",
        "pivot",
        "proceed",
        "proof",
        "research",
        "result",
        "risk",
        "source",
        "stage",
        "test",
        "thesis",
        "validate",
        "validation",
        "verdict",
        "wedge",
    }
    return any(term in message for term in allowed_terms)


def _chat_response(
    answer: str,
    context: GuideContextRead,
    actions: list[GuideActionRead],
) -> GuideChatResponseRead:
    return GuideChatResponseRead(
        answer=answer,
        action_cards=actions[:5],
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
                label="Active validation plan",
            )
        )
    return entities


def _support_actions(context: GuideContextRead) -> list[GuideActionRead]:
    preferred = [
        "explain_current_focus",
        "show_evidence",
        "update_thesis",
        "compare_wedges",
        "draft_outreach",
        "log_results",
        "record_decision",
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
    return context.available_actions[0]


def _fallback_stage_copy(stage: str) -> _StageGuideCopy:
    return _StageGuideCopy(
        focus="Choose the next strategic step.",
        why=(
            f"The project is in {stage}, so the guide should route the user to the "
            "highest-leverage action."
        ),
        summary="Use the next recommended action to keep the idea moving.",
    )


def _join_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f", and {items[-1]}"
