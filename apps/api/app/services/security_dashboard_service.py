"""Redacted project security-overview aggregation for workspace security admins."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_workspace_security_admin
from app.core.config import Settings
from app.db.models import (
    ApprovalRequest,
    MCPServerRegistration,
    ResearchSprint,
    SecurityAlert,
    SecurityEvent,
)
from app.schemas.security import MCPServerSecurityStatusRead, SecurityOverviewRead
from app.services import kill_switch_service, project_service

_PROMPT_ATTACK_EVENTS = (
    "prompt_injection_detected",
    "jailbreak_detected",
    "system_prompt_extraction_attempt",
    "repeated_prompt_injection_attempts",
    "repeated_jailbreak_attempts",
    "repeated_system_prompt_extraction_attempts",
)


def read_project_security_overview(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
) -> SecurityOverviewRead:
    """Aggregate security-operational state without returning sensitive event content."""
    require_workspace_security_admin(auth)
    project_service.get_project(db, auth, project_id)
    event_filters = (
        SecurityEvent.workspace_id == auth.workspace_id,
        SecurityEvent.project_id == project_id,
    )
    alert_filters = (
        SecurityAlert.workspace_id == auth.workspace_id,
        SecurityAlert.project_id == project_id,
    )
    switches = kill_switch_service.read_state(db, auth, settings).switches
    registrations = list(
        db.scalars(
            select(MCPServerRegistration)
            .where(MCPServerRegistration.workspace_id == auth.workspace_id)
            .order_by(MCPServerRegistration.name.asc())
        )
    )
    return SecurityOverviewRead(
        project_id=project_id,
        generated_at=datetime.now(UTC),
        high_or_critical_event_count=_count(
            db,
            SecurityEvent,
            *event_filters,
            SecurityEvent.severity.in_(("high", "critical")),
        ),
        blocked_prompt_attack_count=_count(
            db,
            SecurityEvent,
            *event_filters,
            SecurityEvent.event_type.in_(_PROMPT_ATTACK_EVENTS),
        ),
        denied_tool_count=_count(
            db,
            SecurityEvent,
            *event_filters,
            SecurityEvent.event_type == "tool_invocation_denied",
        ),
        pending_high_risk_approval_count=_count(
            db,
            ApprovalRequest,
            ApprovalRequest.workspace_id == auth.workspace_id,
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.status == "pending",
            ApprovalRequest.risk_level == "high",
        ),
        pii_redaction_count=_count(
            db,
            SecurityEvent,
            *event_filters,
            SecurityEvent.event_type.contains("pii"),
            SecurityEvent.event_type.contains("redact"),
        ),
        memory_quarantine_count=_count(
            db,
            SecurityEvent,
            *event_filters,
            SecurityEvent.event_type.contains("quarantin"),
        ),
        anomalous_retrieval_count=_count(
            db,
            SecurityEvent,
            *event_filters,
            SecurityEvent.source == "retrieval",
            SecurityEvent.event_type.contains("anomal"),
        ),
        budget_alert_count=_count(
            db,
            SecurityAlert,
            *alert_filters,
            SecurityAlert.status.in_(("open", "acknowledged")),
            SecurityAlert.alert_type.endswith("_budget_exceeded"),
        ),
        active_workflow_count=_count(
            db,
            ResearchSprint,
            ResearchSprint.workspace_id == auth.workspace_id,
            ResearchSprint.project_id == project_id,
            ResearchSprint.status == "running",
        ),
        active_kill_switches=[switch for switch in switches if switch.enabled],
        mcp_servers=[
            MCPServerSecurityStatusRead(
                name=registration.name,
                enabled=registration.enabled,
                approved_version=registration.approved_version,
                reviewed_at=registration.reviewed_at,
            )
            for registration in registrations
        ],
    )


def _count(
    db: Session,
    model: type[SecurityEvent] | type[SecurityAlert] | type[ApprovalRequest] | type[ResearchSprint],
    *filters: object,
) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*filters)) or 0)
