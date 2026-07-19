"""Normalized, redacted security-event persistence and query helpers."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_workspace_security_admin
from app.core.config import Settings, get_settings
from app.core.redaction import redact_payload, redact_text
from app.db.models import AuditEvent, SecurityAlert, SecurityEvent
from app.services import project_service, security_metrics_service

SecurityEventSeverity = Literal["info", "low", "medium", "high", "critical"]
SecurityEventSource = Literal[
    "api", "guardrail", "retrieval", "tool", "memory", "workflow", "auth", "mcp"
]

_REPEATED_GUARDRAIL_ESCALATIONS = {
    "prompt_injection_detected": "repeated_prompt_injection_attempts",
    "jailbreak_detected": "repeated_jailbreak_attempts",
    "system_prompt_extraction_attempt": "repeated_system_prompt_extraction_attempts",
}
_AUTHORIZATION_DENIAL_EVENTS = {
    "security_policy_denied",
    "tool_invocation_denied",
    "memory_write_denied",
    "evidence_source_content_access_denied",
    "signed_url_denied",
}


def record_from_audit_event(
    db: Session,
    audit_event: AuditEvent,
    *,
    settings: Settings | None = None,
) -> SecurityEvent:
    """Project one high-risk audit record into the normalized security-event stream."""
    metadata = audit_event.event_metadata or {}
    attributes = {
        **metadata,
        "audit_event_id": str(audit_event.id),
        "risk_level": audit_event.risk_level,
        "entity_type": audit_event.entity_type,
        "entity_id": str(audit_event.entity_id) if audit_event.entity_id else None,
    }
    return record_security_event(
        db,
        workspace_id=audit_event.workspace_id,
        project_id=audit_event.project_id,
        user_id=audit_event.user_id,
        audit_event_id=audit_event.id,
        ai_run_id=_metadata_uuid(metadata, "ai_run_id"),
        tool_invocation_id=(
            audit_event.entity_id
            if audit_event.entity_type == "tool_invocation"
            else _metadata_uuid(metadata, "tool_invocation_id")
        ),
        approval_request_id=_metadata_uuid(metadata, "approval_request_id"),
        session_id=_metadata_string(metadata, "session_id", maximum_length=255),
        request_id=_metadata_string(metadata, "request_id", maximum_length=255),
        langsmith_trace_id=_metadata_string(metadata, "langsmith_trace_id", maximum_length=100),
        temporal_workflow_id=_metadata_string(metadata, "temporal_workflow_id", maximum_length=255),
        event_type=audit_event.event_type,
        severity=_severity_from_risk(audit_event.risk_level),
        source=_source_for_audit_event(audit_event.event_type),
        summary=audit_event.summary,
        attributes=attributes,
        settings=settings,
    )


def record_security_event(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    audit_event_id: uuid.UUID | None = None,
    ai_run_id: uuid.UUID | None = None,
    tool_invocation_id: uuid.UUID | None = None,
    approval_request_id: uuid.UUID | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    langsmith_trace_id: str | None = None,
    temporal_workflow_id: str | None = None,
    event_type: str,
    severity: SecurityEventSeverity,
    source: SecurityEventSource,
    summary: str,
    attributes: dict[str, Any] | None = None,
    containment_status: str | None = None,
    settings: Settings | None = None,
) -> SecurityEvent:
    """Persist bounded correlation data without retaining sensitive security payloads."""
    event = SecurityEvent(
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        audit_event_id=audit_event_id,
        ai_run_id=ai_run_id,
        tool_invocation_id=tool_invocation_id,
        approval_request_id=approval_request_id,
        session_id=_bounded(session_id, 255),
        request_id=_bounded(request_id, 255),
        langsmith_trace_id=_bounded(langsmith_trace_id, 100),
        temporal_workflow_id=_bounded(temporal_workflow_id, 255),
        event_type=_bounded(event_type, 120) or "security_event",
        severity=severity,
        source=source,
        summary=redact_text(summary, redact_emails=True),
        attributes=redact_payload(attributes or {}, redact_emails=True),
        detected_at=datetime.now(UTC),
        containment_status=_bounded(containment_status, 80),
    )
    db.add(event)
    db.flush()
    security_metrics_service.record_security_event(event.event_type, event.source)
    _open_alert_for_high_severity_event(db, event)
    _detect_repeated_guardrail_attack(db, event, settings or get_settings())
    _detect_authorization_denial_spike(db, event, settings or get_settings())
    _detect_provider_failure_spike(db, event, settings or get_settings())
    _detect_memory_contradiction_spike(db, event, settings or get_settings())
    return event


def record_artifact_claim_verification_failure(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID,
    ai_run_id: uuid.UUID,
    artifact_type: str,
    unverified_claim_count: int,
    temporal_workflow_id: str | None = None,
) -> SecurityEvent | None:
    """Record verified claim failures without retaining claim text or citations."""
    if (
        isinstance(unverified_claim_count, bool)
        or not isinstance(unverified_claim_count, int)
        or unverified_claim_count < 1
    ):
        return None
    event = record_security_event(
        db,
        workspace_id=auth.workspace_id,
        project_id=project_id,
        user_id=auth.user_id,
        ai_run_id=ai_run_id,
        temporal_workflow_id=temporal_workflow_id,
        event_type="artifact_claim_verification_failed",
        severity="medium",
        source="workflow",
        summary="Citation verification identified unverified claims before artifact persistence.",
        attributes={
            "artifact_type": artifact_type,
            "unverified_claim_count": unverified_claim_count,
        },
    )
    security_metrics_service.record_unverified_claims(unverified_claim_count)
    return event


def list_project_security_events(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[SecurityEvent]:
    require_workspace_security_admin(auth)
    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(SecurityEvent)
            .where(
                SecurityEvent.workspace_id == auth.workspace_id,
                SecurityEvent.project_id == project_id,
            )
            .order_by(SecurityEvent.detected_at.desc())
            .limit(min(limit, 100))
        )
    )


def list_project_security_alerts(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[SecurityAlert]:
    require_workspace_security_admin(auth)
    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(SecurityAlert)
            .where(
                SecurityAlert.workspace_id == auth.workspace_id,
                SecurityAlert.project_id == project_id,
            )
            .order_by(SecurityAlert.created_at.desc())
            .limit(min(limit, 100))
        )
    )


def acknowledge_project_security_alert(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    alert_id: uuid.UUID,
) -> SecurityAlert:
    alert = _get_project_security_alert(db, auth, project_id, alert_id)
    if alert.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alert is not open.")
    alert.status = "acknowledged"
    alert.acknowledged_by_user_id = auth.user_id
    alert.acknowledged_at = datetime.now(UTC)
    db.flush()
    _record_alert_disposition_audit(db, auth, alert, event_type="security_alert_acknowledged")
    return alert


def resolve_project_security_alert(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    alert_id: uuid.UUID,
) -> SecurityAlert:
    alert = _get_project_security_alert(db, auth, project_id, alert_id)
    if alert.status not in {"open", "acknowledged"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alert is already resolved.",
        )
    alert.status = "resolved"
    alert.resolved_by_user_id = auth.user_id
    alert.resolved_at = datetime.now(UTC)
    db.flush()
    _record_alert_disposition_audit(db, auth, alert, event_type="security_alert_resolved")
    return alert


def _open_alert_for_high_severity_event(db: Session, event: SecurityEvent) -> None:
    if event.severity not in {"high", "critical"}:
        return
    db.add(
        SecurityAlert(
            workspace_id=event.workspace_id,
            project_id=event.project_id,
            security_event_id=event.id,
            severity=event.severity,
            alert_type=event.event_type,
            summary=event.summary,
        )
    )
    db.flush()


def _get_project_security_alert(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    alert_id: uuid.UUID,
) -> SecurityAlert:
    require_workspace_security_admin(auth)
    project_service.get_project(db, auth, project_id)
    alert = db.scalar(
        select(SecurityAlert).where(
            SecurityAlert.id == alert_id,
            SecurityAlert.workspace_id == auth.workspace_id,
            SecurityAlert.project_id == project_id,
        )
    )
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Security alert not found.",
        )
    return alert


def _record_alert_disposition_audit(
    db: Session,
    auth: AuthContext,
    alert: SecurityAlert,
    *,
    event_type: str,
) -> None:
    from app.services import governance_service

    governance_service.record_audit_event(
        db,
        auth,
        event_type=event_type,
        actor_type="user",
        project_id=alert.project_id,
        entity_type="security_alert",
        entity_id=alert.id,
        risk_level="medium",
        summary=f"Security alert {alert.alert_type} was {alert.status}.",
        metadata={"alert_type": alert.alert_type, "severity": alert.severity},
    )


def _detect_repeated_guardrail_attack(
    db: Session,
    event: SecurityEvent,
    settings: Settings,
) -> None:
    escalation_type = _REPEATED_GUARDRAIL_ESCALATIONS.get(event.event_type)
    if escalation_type is None or event.source != "guardrail" or event.severity != "high":
        return

    window_start = event.detected_at - timedelta(
        seconds=settings.security_alert_detection_window_seconds
    )
    matching_events = [
        SecurityEvent.workspace_id == event.workspace_id,
        SecurityEvent.event_type == event.event_type,
        SecurityEvent.source == "guardrail",
        SecurityEvent.severity == "high",
        SecurityEvent.detected_at >= window_start,
        SecurityEvent.detected_at <= event.detected_at,
    ]
    if event.user_id is not None:
        matching_events.append(SecurityEvent.user_id == event.user_id)

    observed_count = db.scalar(
        select(func.count()).select_from(SecurityEvent).where(*matching_events)
    )
    if observed_count is None or observed_count < settings.security_repeated_guardrail_threshold:
        return

    escalation_filters = [
        SecurityEvent.workspace_id == event.workspace_id,
        SecurityEvent.event_type == escalation_type,
        SecurityEvent.detected_at >= window_start,
    ]
    if event.user_id is not None:
        escalation_filters.append(SecurityEvent.user_id == event.user_id)
    if db.scalar(select(SecurityEvent.id).where(*escalation_filters).limit(1)) is not None:
        return

    record_security_event(
        db,
        workspace_id=event.workspace_id,
        project_id=event.project_id,
        user_id=event.user_id,
        session_id=event.session_id,
        request_id=event.request_id,
        langsmith_trace_id=event.langsmith_trace_id,
        temporal_workflow_id=event.temporal_workflow_id,
        event_type=escalation_type,
        severity="critical",
        source="guardrail",
        summary="Repeated blocked guardrail attacks exceeded the configured threshold.",
        attributes={
            "trigger_event_type": event.event_type,
            "observed_count": observed_count,
            "window_seconds": settings.security_alert_detection_window_seconds,
        },
        containment_status="alert_open",
        settings=settings,
    )


def _detect_authorization_denial_spike(
    db: Session,
    event: SecurityEvent,
    settings: Settings,
) -> None:
    if event.event_type not in _AUTHORIZATION_DENIAL_EVENTS:
        return

    window_start = event.detected_at - timedelta(
        seconds=settings.security_alert_detection_window_seconds
    )
    matching_events = [
        SecurityEvent.workspace_id == event.workspace_id,
        SecurityEvent.event_type.in_(_AUTHORIZATION_DENIAL_EVENTS),
        SecurityEvent.detected_at >= window_start,
        SecurityEvent.detected_at <= event.detected_at,
    ]
    if event.user_id is not None:
        matching_events.append(SecurityEvent.user_id == event.user_id)

    observed_count = db.scalar(
        select(func.count()).select_from(SecurityEvent).where(*matching_events)
    )
    if (
        observed_count is None
        or observed_count < settings.security_authorization_denial_spike_threshold
    ):
        return

    escalation_filters = [
        SecurityEvent.workspace_id == event.workspace_id,
        SecurityEvent.event_type == "authorization_denial_spike",
        SecurityEvent.detected_at >= window_start,
    ]
    if event.user_id is not None:
        escalation_filters.append(SecurityEvent.user_id == event.user_id)
    if db.scalar(select(SecurityEvent.id).where(*escalation_filters).limit(1)) is not None:
        return

    record_security_event(
        db,
        workspace_id=event.workspace_id,
        project_id=event.project_id,
        user_id=event.user_id,
        session_id=event.session_id,
        request_id=event.request_id,
        langsmith_trace_id=event.langsmith_trace_id,
        temporal_workflow_id=event.temporal_workflow_id,
        event_type="authorization_denial_spike",
        severity="high",
        source=event.source,
        summary="Authorization denials exceeded the configured threshold.",
        attributes={
            "observed_count": observed_count,
            "window_seconds": settings.security_alert_detection_window_seconds,
        },
        containment_status="alert_open",
        settings=settings,
    )


def _detect_provider_failure_spike(
    db: Session,
    event: SecurityEvent,
    settings: Settings,
) -> None:
    if event.event_type != "provider_failure":
        return

    window_start = event.detected_at - timedelta(
        seconds=settings.security_alert_detection_window_seconds
    )
    matching_events = [
        SecurityEvent.workspace_id == event.workspace_id,
        SecurityEvent.event_type == "provider_failure",
        SecurityEvent.detected_at >= window_start,
        SecurityEvent.detected_at <= event.detected_at,
    ]
    if event.project_id is not None:
        matching_events.append(SecurityEvent.project_id == event.project_id)
    observed_count = db.scalar(
        select(func.count()).select_from(SecurityEvent).where(*matching_events)
    )
    if (
        observed_count is None
        or observed_count < settings.security_provider_failure_spike_threshold
    ):
        return

    escalation_filters = [
        SecurityEvent.workspace_id == event.workspace_id,
        SecurityEvent.event_type == "provider_failure_spike",
        SecurityEvent.detected_at >= window_start,
    ]
    if event.project_id is not None:
        escalation_filters.append(SecurityEvent.project_id == event.project_id)
    if db.scalar(select(SecurityEvent.id).where(*escalation_filters).limit(1)) is not None:
        return

    record_security_event(
        db,
        workspace_id=event.workspace_id,
        project_id=event.project_id,
        user_id=event.user_id,
        session_id=event.session_id,
        request_id=event.request_id,
        langsmith_trace_id=event.langsmith_trace_id,
        temporal_workflow_id=event.temporal_workflow_id,
        event_type="provider_failure_spike",
        severity="high",
        source="workflow",
        summary="Provider failures exceeded the configured threshold.",
        attributes={
            "provider": "litellm",
            "observed_count": observed_count,
            "window_seconds": settings.security_alert_detection_window_seconds,
        },
        containment_status="alert_open",
        settings=settings,
    )


def _detect_memory_contradiction_spike(
    db: Session,
    event: SecurityEvent,
    settings: Settings,
) -> None:
    if event.event_type != "memory_contradiction_detected":
        return

    window_start = event.detected_at - timedelta(
        seconds=settings.security_alert_detection_window_seconds
    )
    matching_events = [
        SecurityEvent.workspace_id == event.workspace_id,
        SecurityEvent.project_id == event.project_id,
        SecurityEvent.event_type == "memory_contradiction_detected",
        SecurityEvent.detected_at >= window_start,
        SecurityEvent.detected_at <= event.detected_at,
    ]
    observed_count = db.scalar(
        select(func.count()).select_from(SecurityEvent).where(*matching_events)
    )
    if (
        observed_count is None
        or observed_count < settings.security_memory_contradiction_spike_threshold
    ):
        return

    escalation_filters = [
        SecurityEvent.workspace_id == event.workspace_id,
        SecurityEvent.project_id == event.project_id,
        SecurityEvent.event_type == "memory_contradiction_spike",
        SecurityEvent.detected_at >= window_start,
    ]
    if db.scalar(select(SecurityEvent.id).where(*escalation_filters).limit(1)) is not None:
        return

    record_security_event(
        db,
        workspace_id=event.workspace_id,
        project_id=event.project_id,
        user_id=event.user_id,
        event_type="memory_contradiction_spike",
        severity="high",
        source="memory",
        summary="Memory contradictions exceeded the configured threshold.",
        attributes={
            "observed_count": observed_count,
            "window_seconds": settings.security_alert_detection_window_seconds,
        },
        containment_status="alert_open",
        settings=settings,
    )


def _severity_from_risk(risk_level: str | None) -> SecurityEventSeverity:
    if risk_level == "high":
        return "high"
    if risk_level == "medium":
        return "medium"
    if risk_level == "low":
        return "low"
    return "info"


def _source_for_audit_event(event_type: str) -> SecurityEventSource:
    if event_type.startswith("mcp_"):
        return "mcp"
    if event_type.startswith(
        (
            "prompt_",
            "jailbreak_",
            "system_prompt_",
            "guardrail_",
            "tool_manipulation_",
            "data_exfiltration_",
        )
    ):
        return "guardrail"
    if event_type.startswith("memory_"):
        return "memory"
    if event_type.startswith(("tool_", "high_risk_action_")):
        return "tool"
    if event_type.startswith(("temporal_", "workflow_")):
        return "workflow"
    return "api"


def _metadata_uuid(metadata: dict[str, Any], name: str) -> uuid.UUID | None:
    value = metadata.get(name)
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _metadata_string(metadata: dict[str, Any], name: str, *, maximum_length: int) -> str | None:
    value = metadata.get(name)
    return _bounded(value if isinstance(value, str) else None, maximum_length)


def _bounded(value: str | None, maximum_length: int) -> str | None:
    if not value:
        return None
    return value[:maximum_length]
