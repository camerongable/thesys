"""Prompt, fallback, and proposal helpers for validation result interpretation."""

import json
from decimal import Decimal
from typing import Any

from app.ai.litellm_client import ChatMessage
from app.ai.prompts import UNTRUSTED_RETRIEVED_CONTENT_RULE
from app.schemas.validation import ExperimentResultCreate, ValidationResultInterpretationDraft


def validation_mission_context(mission: object) -> dict[str, Any]:
    """Project the mission fields needed by the interpretation prompt."""
    return {
        "id": str(mission.id),
        "mission_title": mission.mission_title,
        "why_it_matters": mission.why_it_matters,
        "target_user": mission.target_user,
        "test_type": mission.test_type,
        "success_criteria": mission.success_criteria,
        "failure_criteria": mission.failure_criteria,
    }


def validation_result_interpretation_messages(
    *,
    project_state: dict[str, Any],
    mission_context: dict[str, Any],
    raw_notes: str,
) -> list[ChatMessage]:
    """Build the prompt payload for skeptical validation-result interpretation."""
    payload = {
        "project_state": project_state,
        "validation_mission": mission_context,
        "raw_validation_notes": raw_notes,
    }
    return [
        ChatMessage(
            role="system",
            content=(
                "Interpret founder validation results skeptically. Extract only signals "
                "supported by the notes. Focus on pain severity, current workaround, urgency, "
                "willingness to pay, switching intent, objections, confidence change, and the "
                "next decision. Do not overstate weak evidence. Recommend proceed only when "
                "pain, urgency, and willingness-to-pay or switching signals are all strong. "
                "Return JSON only. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE}"
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Return a validation result interpretation as JSON only.\n\n"
                f"{json.dumps(payload, indent=2, sort_keys=True)}"
            ),
        ),
    ]


def fallback_validation_interpretation(
    mission: object,
    raw_notes: str,
) -> ValidationResultInterpretationDraft:
    lowered = raw_notes.casefold()
    positive_terms = (
        "pay",
        "paid",
        "pilot",
        "urgent",
        "pain",
        "painful",
        "switch",
        "trial",
        "yes",
        "interested",
    )
    negative_terms = (
        "free",
        "not pay",
        "no budget",
        "not urgent",
        "happy with",
        "declined",
        "wouldn't",
        "would not",
    )
    positive_count = sum(1 for term in positive_terms if term in lowered)
    negative_count = sum(1 for term in negative_terms if term in lowered)

    if positive_count >= negative_count + 3:
        pain = "high"
        urgency = "high"
        willingness = "strong" if "pay" in lowered or "paid" in lowered else "medium"
        switching = "strong" if "switch" in lowered or "pilot" in lowered else "medium"
        confidence_change = "increase"
        confidence_delta = 0.18
        status_value = "validated"
        decision = "continue_research" if willingness != "strong" else "proceed"
        signal_summary = "Strong validation signal with meaningful pain and action intent."
        strengthened = [
            "Target users appear to experience the problem with enough urgency to keep testing.",
            "The notes contain a concrete signal that the mission assumption may be true.",
        ]
        weakened = [
            "The result still needs more evidence before expanding beyond this wedge.",
        ]
        next_action = (
            "If willingness-to-pay was explicit, prepare a narrow pilot. Otherwise run a "
            "pricing-specific follow-up test before building."
        )
    elif negative_count > positive_count:
        pain = "low"
        urgency = "low"
        willingness = "weak"
        switching = "weak"
        confidence_change = "decrease"
        confidence_delta = -0.18
        status_value = "invalidated"
        decision = "pivot"
        signal_summary = "Weak validation signal; the notes do not support the current mission."
        strengthened = ["The test clarified where the current thesis is weak."]
        weakened = [
            "The notes suggest low urgency, weak willingness to pay, or satisfaction "
            "with existing alternatives.",
        ]
        next_action = (
            "Do not build the current version. Revisit the wedge or run a sharper test with "
            "a better-qualified respondent profile."
        )
    else:
        pain = "medium" if positive_count > 0 else "low"
        urgency = "medium" if positive_count > 0 else "low"
        willingness = "weak"
        switching = "weak"
        confidence_change = "no_change"
        confidence_delta = 0.0
        status_value = "inconclusive"
        decision = "continue_research"
        signal_summary = "Mixed or incomplete validation signal."
        strengthened = [
            "The notes contain some useful learning about the target user or current workaround.",
        ]
        weakened = [
            "The result does not yet prove willingness to pay or a strong switching trigger.",
        ]
        next_action = (
            "Run a tighter follow-up test focused on willingness to pay, switching behavior, "
            "or the clearest objection."
        )

    quotes = extract_quotes(raw_notes)
    objections = extract_objections(raw_notes)
    return ValidationResultInterpretationDraft(
        signal_summary=signal_summary,
        what_strengthened=strengthened,
        what_weakened=weakened,
        signal={
            "pain_severity": pain,
            "current_workaround": fallback_current_workaround(raw_notes),
            "urgency": urgency,
            "willingness_to_pay": willingness,
            "switching_signal": switching,
            "objections": objections,
            "quotes": quotes,
            "confidence_change": confidence_change,
            "recommended_next_action": next_action,
        },
        confidence_rationale=(
            "This interpretation is based on the validation notes and mission criteria, not "
            "on general market assumptions."
        ),
        proposed_confidence_delta=confidence_delta,
        proposed_assumption_status=status_value,
        decision_recommendation=decision,
    )


def result_delta(payload: ExperimentResultCreate) -> Decimal:
    if payload.confidence_delta is not None:
        return Decimal(str(round(payload.confidence_delta, 4)))
    defaults = {
        "positive": Decimal("0.15"),
        "negative": Decimal("-0.20"),
        "mixed": Decimal("0.05"),
        "inconclusive": Decimal("0.00"),
    }
    return defaults[payload.outcome]


def extract_quotes(raw_notes: str) -> list[str]:
    quoted: list[str] = []
    fragments = raw_notes.replace("“", '"').replace("”", '"').split('"')
    for index, fragment in enumerate(fragments):
        if index % 2 == 1:
            stripped = fragment.strip()
            if stripped:
                quoted.append(_shorten(stripped, 240))
    if quoted:
        return quoted[:5]
    lines = [
        _shorten(line.strip("-• \t"), 240)
        for line in raw_notes.splitlines()
        if len(line.strip()) >= 20
    ]
    return lines[:3]


def extract_objections(raw_notes: str) -> list[str]:
    objections: list[str] = []
    for line in raw_notes.splitlines():
        lowered = line.casefold()
        if any(term in lowered for term in ("objection", "concern", "worried", "but ", "however")):
            objections.append(_shorten(line.strip("-• \t"), 240))
    if objections:
        return objections[:5]
    lowered = raw_notes.casefold()
    defaults: list[str] = []
    if "free" in lowered:
        defaults.append("Existing free alternatives may cap willingness to pay.")
    if "budget" in lowered:
        defaults.append("Budget ownership or willingness to pay is unclear.")
    if "switch" in lowered and "not" in lowered:
        defaults.append("Switching from the current workaround may be difficult.")
    return defaults[:5]


def fallback_current_workaround(raw_notes: str) -> str:
    for line in raw_notes.splitlines():
        lowered = line.casefold()
        if "workaround" in lowered or "today" in lowered or "currently" in lowered:
            return _shorten(line.strip("-• \t"), 500)
    return "The current workaround was not clearly isolated in the notes."


def assumption_status_for_outcome(outcome: str) -> str:
    if outcome == "positive":
        return "validated"
    if outcome == "negative":
        return "invalidated"
    return "inconclusive"


def validation_interpretation_proposed_updates(
    mission: object,
    draft: ValidationResultInterpretationDraft,
) -> dict[str, Any]:
    """Build the approval proposal payload for applying interpreted validation results."""
    experiment_id = getattr(mission, "experiment_id", None)
    assumption_id = getattr(mission, "assumption_id", None)
    return {
        "validation_mission_id": str(mission.id),
        "experiment_id": str(experiment_id) if experiment_id else None,
        "assumption_id": str(assumption_id),
        "confidence_change": draft.signal.confidence_change,
        "proposed_confidence_delta": round(draft.proposed_confidence_delta, 4),
        "proposed_assumption_status": draft.proposed_assumption_status,
        "decision_recommendation": draft.decision_recommendation,
        "recommended_next_action": draft.signal.recommended_next_action,
        "signal_summary": draft.signal_summary,
        "thesis_evolution_event": {
            "event_type": "validation_blocker",
            "title": "Validation results interpreted",
            "change_summary": draft.signal_summary,
            "reason": draft.confidence_rationale,
        },
    }


def _shorten(value: str, max_length: int) -> str:
    stripped = " ".join(value.split())
    return stripped if len(stripped) <= max_length else f"{stripped[: max_length - 3]}..."


_validation_mission_context = validation_mission_context
_validation_result_interpretation_messages = validation_result_interpretation_messages
_fallback_validation_interpretation = fallback_validation_interpretation
_result_delta = result_delta
_extract_quotes = extract_quotes
_extract_objections = extract_objections
_fallback_current_workaround = fallback_current_workaround
_assumption_status_for_outcome = assumption_status_for_outcome
_validation_interpretation_proposed_updates = validation_interpretation_proposed_updates
