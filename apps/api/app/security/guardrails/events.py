"""Stable guardrail event names for workflow audit integration."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.security.guardrails.classifiers import DetectionResult
from app.security.guardrails.policies import GuardrailDecision
from app.services import governance_service

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
    if detection.detector_unavailable:
        return "guardrail_service_unavailable"
    return _EVENT_BY_CATEGORY.get(detection.category)


def detection_metadata(decision: GuardrailDecision) -> dict[str, Any]:
    """Return durable, non-content-bearing evidence for a guardrail decision."""
    return {
        **detection_result_metadata(decision.detection),
        "tools_allowed": decision.tools_allowed,
        "memory_writes_allowed": decision.memory_writes_allowed,
    }


def detection_result_metadata(detection: DetectionResult) -> dict[str, Any]:
    """Return non-content-bearing metadata for output-only detector results."""
    return {
        "category": detection.category,
        "score": detection.score,
        "action": detection.action,
        "detector": detection.detector,
        "detector_version": detection.detector_version,
        "detector_unavailable": detection.detector_unavailable,
        "reasons": list(detection.reasons),
    }


def record_detection(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID,
    decision: GuardrailDecision,
) -> str | None:
    """Write an attributable audit event without persisting the untrusted payload."""
    event_type = security_event_type(decision.detection)
    if event_type is None:
        return None
    governance_service.record_audit_event(
        db,
        auth,
        event_type=event_type,
        actor_type="user",
        project_id=project_id,
        entity_type="guardrail_detection",
        risk_level="high" if decision.should_block else "medium",
        summary=f"Guardrail detected {decision.detection.category.replace('_', ' ')}.",
        metadata=detection_metadata(decision),
    )
    return event_type
