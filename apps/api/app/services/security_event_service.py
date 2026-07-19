"""Normalized, redacted security-event persistence and query helpers."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_workspace_security_admin
from app.core.redaction import redact_payload, redact_text
from app.db.models import AuditEvent, SecurityEvent
from app.services import project_service

SecurityEventSeverity = Literal["info", "low", "medium", "high", "critical"]
SecurityEventSource = Literal[
    "api", "guardrail", "retrieval", "tool", "memory", "workflow", "auth", "mcp"
]


def record_from_audit_event(db: Session, audit_event: AuditEvent) -> SecurityEvent:
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
