"""Action-card DTO shaping for Ask Thesys guide surfaces."""

import uuid
from typing import Literal

from app.schemas.guide import GuideActionRead, GuideActionType
from app.schemas.overview import NextBestActionRead, ProjectOverviewRead
from app.schemas.validation import DecisionCoachActionRead


def available_actions(overview: ProjectOverviewRead) -> list[GuideActionRead]:
    actions = [guide_action_from_next_best(overview.next_best_action)]
    actions.extend(
        guide_action_from_next_best(action) for action in overview.secondary_actions
    )
    actions.extend(support_actions_for_overview(overview))

    deduped: list[GuideActionRead] = []
    seen: set[str] = set()
    for action in actions:
        if action.id in seen:
            continue
        seen.add(action.id)
        deduped.append(action)
    return deduped


def guide_action_from_next_best(action: NextBestActionRead) -> GuideActionRead:
    label, description = router_copy_for_next_best(action)
    return GuideActionRead(
        id=action.action_type,
        type=action_type_for_next_best(action.action_type),
        label=label,
        description=description,
        why_it_matters=action.why_it_matters,
        target_route=action.target_route,
        target_modal=target_modal_for_next_best(action.action_type),
        payload={"related_stage": action.related_stage},
        risk_level=action_risk(action.action_type),
        requires_confirmation=action.action_type
        in {"use_suggested_decision", "resume_or_archive"},
    )


def guide_action_from_decision_coach(
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


def nudge_action(
    *,
    project_id: uuid.UUID,
    action_id: str,
    action_type: GuideActionType,
    label: str,
    description: str,
    why_it_matters: str,
    target_hash: str,
    risk_level: Literal["low", "medium", "high"],
    target_modal: str | None = None,
) -> GuideActionRead:
    return GuideActionRead(
        id=action_id,
        type=action_type,
        label=label,
        description=description,
        why_it_matters=why_it_matters,
        target_route=f"/projects/{project_id}#{target_hash}",
        target_modal=target_modal,
        payload={"source": "project_nudge"},
        risk_level=risk_level,
        requires_confirmation=False,
    )


def support_actions_for_overview(overview: ProjectOverviewRead) -> list[GuideActionRead]:
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
            id="show_idea_story",
            type="navigate",
            label="Show idea story",
            description="Open the compact story from original idea to current proof.",
            why_it_matters=(
                "Seeing the original idea, selected wedge, rejected directions, blocker, "
                "and next proof makes the validation path easier to trust."
            ),
            target_route=f"/projects/{project_id}#current-step",
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
            id="plan_research_sprint",
            type="run_workflow",
            label="Plan evidence review",
            description=(
                "Open the research area to draft a scoped evidence review before running it."
            ),
            why_it_matters=(
                "Research plans keep investigation bounded and require approval before broader "
                "evidence work starts."
            ),
            target_route=f"/projects/{project_id}#research-sprint",
            target_modal="research-sprint",
            risk_level="medium",
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
            why_it_matters=("The idea is easier to trust when you can see what changed and why."),
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


def action_type_for_next_best(action_type: str) -> str:
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


def router_copy_for_next_best(action: NextBestActionRead) -> tuple[str, str]:
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


def target_modal_for_next_best(action_type: str) -> str | None:
    return {
        "structure_idea": "structured-intake",
        "log_results": "log-result",
        "add_results": "log-result",
        "record_decision": "record-decision-panel",
        "use_suggested_decision": "record-decision-panel",
    }.get(action_type)


def action_risk(action_type: str) -> str:
    if action_type in {"use_suggested_decision", "resume_or_archive", "view_decision"}:
        return "high"
    if action_type in {"create_validation_plan", "log_results", "add_results"}:
        return "medium"
    return "low"
