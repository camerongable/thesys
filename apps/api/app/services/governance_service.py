"""Audit and approval services for human-in-the-loop AI workflows."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_permission
from app.core.redaction import redact_payload, redact_text
from app.db.models import ApprovalRequest, AuditEvent
from app.services import project_service

ActorType = Literal["user", "agent", "system"]
RiskLevel = Literal["low", "medium", "high"]
ApprovalRequestType = Literal[
    "research_plan",
    "memory_update",
    "tool_invocation",
    "validation_plan",
    "decision",
]
ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]


def record_audit_event(
    db: Session,
    auth: AuthContext,
    *,
    event_type: str,
    actor_type: ActorType,
    summary: str,
    project_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    risk_level: RiskLevel | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Record a redacted audit event without committing the surrounding transaction."""
    event = AuditEvent(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        user_id=auth.user_id if actor_type == "user" else None,
        event_type=event_type,
        actor_type=actor_type,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=redact_text(summary, redact_emails=True),
        risk_level=risk_level,
        event_metadata=redact_payload(metadata or {}, redact_emails=True),
        created_at=datetime.now(UTC),
    )
    db.add(event)
    db.flush()
    return event


def list_audit_events(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[AuditEvent]:
    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.workspace_id == auth.workspace_id,
                AuditEvent.project_id == project_id,
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(min(limit, 100))
        )
    )


def create_approval_request(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID,
    request_type: ApprovalRequestType,
    requested_by: ActorType,
    risk_level: RiskLevel,
    summary: str,
    proposed_change: dict[str, Any],
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> ApprovalRequest:
    """Create or refresh a pending approval request for a proposed state change."""
    project_service.get_project(db, auth, project_id)
    existing = _pending_approval_for_entity(
        db,
        auth,
        project_id,
        request_type,
        entity_type,
        entity_id,
    )
    if existing is not None:
        existing.summary = redact_text(summary, redact_emails=True)
        existing.proposed_change = redact_payload(proposed_change, redact_emails=True)
        existing.risk_level = risk_level
        db.flush()
        return existing

    approval = ApprovalRequest(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        request_type=request_type,
        status="pending",
        requested_by=requested_by,
        risk_level=risk_level,
        summary=redact_text(summary, redact_emails=True),
        proposed_change=redact_payload(proposed_change, redact_emails=True),
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(approval)
    db.flush()
    if risk_level == "high":
        record_audit_event(
            db,
            auth,
            event_type="high_risk_action_requested",
            actor_type=requested_by,
            project_id=project_id,
            entity_type=entity_type or "approval_request",
            entity_id=entity_id or approval.id,
            risk_level=risk_level,
            summary=summary,
            metadata={"request_type": request_type, "approval_request_id": str(approval.id)},
        )
    return approval


def list_approval_requests(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    status_filter: ApprovalStatus | None = None,
    limit: int = 50,
) -> list[ApprovalRequest]:
    project_service.get_project(db, auth, project_id)
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.workspace_id == auth.workspace_id,
        ApprovalRequest.project_id == project_id,
    )
    if status_filter is not None:
        stmt = stmt.where(ApprovalRequest.status == status_filter)
    return list(db.scalars(stmt.order_by(ApprovalRequest.created_at.desc()).limit(min(limit, 100))))


def approve_approval_request(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
) -> ApprovalRequest:
    """Approve a pending request and write the matching audit event."""
    approval = _get_approval_request(db, auth, project_id, approval_id)
    _require_approval_permission(auth, approval)
    _resolve_approval(db, auth, approval, "approved")
    record_audit_event(
        db,
        auth,
        event_type=_approved_event_type(approval.request_type),
        actor_type="user",
        project_id=project_id,
        entity_type=approval.entity_type or "approval_request",
        entity_id=approval.entity_id or approval.id,
        risk_level=approval.risk_level,
        summary=f"Approved {approval.request_type.replace('_', ' ')} request.",
        metadata={"approval_request_id": str(approval.id)},
    )
    db.commit()
    db.refresh(approval)
    return approval


def reject_approval_request(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
) -> ApprovalRequest:
    """Reject a pending request and write the matching audit event."""
    approval = _get_approval_request(db, auth, project_id, approval_id)
    _require_approval_permission(auth, approval)
    _resolve_approval(db, auth, approval, "rejected")
    record_audit_event(
        db,
        auth,
        event_type=_rejected_event_type(approval.request_type),
        actor_type="user",
        project_id=project_id,
        entity_type=approval.entity_type or "approval_request",
        entity_id=approval.entity_id or approval.id,
        risk_level=approval.risk_level,
        summary=f"Rejected {approval.request_type.replace('_', ' ')} request.",
        metadata={"approval_request_id": str(approval.id)},
    )
    db.commit()
    db.refresh(approval)
    return approval


def resolve_pending_approvals_for_entity(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    status_value: Literal["approved", "rejected"],
    request_types: set[str] | None = None,
) -> list[ApprovalRequest]:
    """Resolve any pending approvals attached to a domain entity."""
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.workspace_id == auth.workspace_id,
        ApprovalRequest.project_id == project_id,
        ApprovalRequest.entity_type == entity_type,
        ApprovalRequest.entity_id == entity_id,
        ApprovalRequest.status == "pending",
    )
    if request_types:
        stmt = stmt.where(ApprovalRequest.request_type.in_(request_types))
    approvals = list(db.scalars(stmt))
    for approval in approvals:
        _resolve_approval(db, auth, approval, status_value)
    db.flush()
    return approvals


def _pending_approval_for_entity(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    request_type: str,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
) -> ApprovalRequest | None:
    if entity_type is None or entity_id is None:
        return None
    return db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.workspace_id == auth.workspace_id,
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.request_type == request_type,
            ApprovalRequest.entity_type == entity_type,
            ApprovalRequest.entity_id == entity_id,
            ApprovalRequest.status == "pending",
        )
    )


def _get_approval_request(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
) -> ApprovalRequest:
    approval = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.workspace_id == auth.workspace_id,
            ApprovalRequest.project_id == project_id,
        )
    )
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found.",
        )
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending approval requests can be resolved.",
        )
    return approval


def _resolve_approval(
    db: Session,
    auth: AuthContext,
    approval: ApprovalRequest,
    status_value: Literal["approved", "rejected"],
) -> None:
    approval.status = status_value
    approval.approved_by_user_id = auth.user_id if status_value == "approved" else None
    approval.resolved_at = datetime.now(UTC)
    db.flush()


def _require_approval_permission(auth: AuthContext, approval: ApprovalRequest) -> None:
    if approval.risk_level == "high":
        require_permission(auth, "approve_high_risk_tools")
        return
    if approval.request_type in {"research_plan", "memory_update", "validation_plan"}:
        require_permission(auth, "approve_memory_updates")
        return
    if approval.request_type == "decision":
        require_permission(auth, "record_decision")
        return
    require_permission(auth, "run_research")


def _approved_event_type(request_type: str) -> str:
    if request_type == "research_plan":
        return "research_plan_approved"
    if request_type == "memory_update":
        return "memory_update_approved"
    if request_type == "validation_plan":
        return "validation_plan_created"
    if request_type == "decision":
        return "decision_recorded"
    return "tool_invocation_executed"


def _rejected_event_type(request_type: str) -> str:
    if request_type == "memory_update":
        return "memory_update_rejected"
    if request_type == "research_plan":
        return "research_plan_rejected"
    return f"{request_type}_rejected"
