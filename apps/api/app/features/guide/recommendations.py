"""Stage-aware guide recommendation copy and follow-up helpers."""

from dataclasses import dataclass

from app.schemas.guide import GuideActionRead, GuideContextRead


@dataclass(frozen=True)
class StageGuideCopy:
    focus: str
    why: str
    summary: str


STAGE_GUIDE_COPY: dict[str, StageGuideCopy] = {
    "draft_idea": StageGuideCopy(
        focus="Shape the rough idea into a testable thesis.",
        why=(
            "The project does not yet have enough customer, problem, and proof context "
            "to make a strategic recommendation."
        ),
        summary=(
            "This idea is still rough. Start by clarifying who it is for and what must be true."
        ),
    ),
    "structured_intake": StageGuideCopy(
        focus="Run the first research pass.",
        why=(
            "The thesis has structure, but it still needs evidence, substitutes, and "
            "competitor pressure before validation can be trusted."
        ),
        summary="The idea has a first shape. The next move is to ground it in research.",
    ),
    "brief_generated": StageGuideCopy(
        focus="Pressure-test the thesis against competitors and substitutes.",
        why=(
            "A brief exists, but the wedge is not credible until the user understands "
            "what direct competitors, substitutes, and manual alternatives already solve."
        ),
        summary="Research exists. Now compare the opportunity against the market.",
    ),
    "competitors_analyzed": StageGuideCopy(
        focus="Find the biggest unknown.",
        why=(
            "Competitor context is available. The leverage point is identifying the "
            "belief that could kill the idea before spending more time building."
        ),
        summary="The market has been mapped. Turn it into a clear validation blocker.",
    ),
    "assumptions_identified": StageGuideCopy(
        focus="Turn the biggest unknown into a test.",
        why=(
            "Ranked assumptions are only useful when the riskiest one becomes a concrete "
            "validation plan with success and failure criteria."
        ),
        summary="The blocker is visible. Create the first proof to reduce uncertainty.",
    ),
    "validation_plan_created": StageGuideCopy(
        focus="Run the blocker test.",
        why=(
            "A validation plan exists, but confidence should only change after real user "
            "evidence is logged."
        ),
        summary="The proof is planned. Run it and capture what happened.",
    ),
    "experiment_running": StageGuideCopy(
        focus="Log real validation evidence.",
        why=(
            "The project is in validation. The next useful state change comes from "
            "recording outcomes, objections, and willingness-to-pay signals."
        ),
        summary="Validation is underway. Capture results before deciding.",
    ),
    "decision_ready": StageGuideCopy(
        focus="Interpret the proof and record the decision.",
        why=(
            "Validation results exist. The app should help turn those results into a "
            "proceed, pivot, pause, kill, or continue-research decision."
        ),
        summary="There is enough signal to review the decision path.",
    ),
    "paused": StageGuideCopy(
        focus="Decide whether this idea deserves another proof.",
        why="Paused ideas should stay parked unless there is a specific new learning goal.",
        summary="This idea is paused. Reopen it only around a concrete next proof.",
    ),
    "killed": StageGuideCopy(
        focus="Preserve the learning trail.",
        why="Killed ideas are still useful when the evidence and rationale stay easy to revisit.",
        summary="This idea is closed unless new evidence changes the thesis.",
    ),
    "proceeding": StageGuideCopy(
        focus="Set the next milestone from the validated wedge.",
        why=(
            "A proceed-style decision should stay tied to the evidence that justified it "
            "and the next proof that could change the plan."
        ),
        summary="A decision has been recorded. Use it to define the next milestone.",
    ),
}


def suggested_questions(context: GuideContextRead) -> list[str]:
    default_questions = [
        "What should I do next?",
        "How has this idea changed?",
        "Why is this blocked?",
        "Open the right form.",
        "What evidence is missing?",
        "Rewrite the thesis.",
        "Compare wedges.",
        "What is the next proof?",
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


def fallback_stage_copy(stage: str) -> StageGuideCopy:
    return StageGuideCopy(
        focus="Choose the next strategic step.",
        why=(
            f"The project is in {stage}, so the guide should route the user to the "
            "highest-leverage action."
        ),
        summary="Use the next recommended action to keep the idea moving.",
    )


def after_that_for_action(context: GuideContextRead, action: GuideActionRead) -> str:
    if action.type == "open_form" or "thesis" in action.id:
        return (
            "I will use the sharper thesis to route you toward research, wedge choice, or a proof."
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
        "I will route you to the next focused step and keep the project history tied to the action."
    )


def join_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f", and {items[-1]}"
