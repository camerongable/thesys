"""Stable guardrail event names for workflow audit integration."""

from app.security.guardrails.classifiers import DetectionResult

_EVENT_BY_CATEGORY = {
    "direct_prompt_injection": "prompt_injection_detected",
    "indirect_prompt_injection": "prompt_injection_detected",
    "jailbreak": "jailbreak_detected",
    "system_prompt_extraction": "system_prompt_extraction_attempt",
    "tool_manipulation": "tool_manipulation_attempt",
    "data_exfiltration_attempt": "data_exfiltration_attempt",
}


def security_event_type(detection: DetectionResult) -> str | None:
    """Return the event name only for actionable, non-benign detections."""
    return _EVENT_BY_CATEGORY.get(detection.category)
