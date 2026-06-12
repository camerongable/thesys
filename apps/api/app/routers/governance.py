import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, AuthContextDep
from app.db.models import ApprovalRequest, AuditEvent
from app.db.session import get_db
from app.schemas.governance import (
    ApprovalRequestActionRead,
    ApprovalRequestListRead,
    ApprovalRequestRead,
    ApprovalRequestStatus,
    AuditEventListRead,
    AuditEventRead,
)
from app.services import governance_service, tool_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["governance"])
DbDep = Annotated[Session, Depends(get_db)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
ApprovalStatusQuery = Annotated[ApprovalRequestStatus | None, Query()]


def serialize_approval(approval: ApprovalRequest) -> ApprovalRequestRead:
    return ApprovalRequestRead.model_validate(approval)


def serialize_audit_event(event: AuditEvent) -> AuditEventRead:
    return AuditEventRead.model_validate(event)


@router.get("/approvals", response_model=ApprovalRequestListRead)
def list_project_approvals(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    status_filter: ApprovalStatusQuery = None,
    limit: LimitQuery = 50,
) -> ApprovalRequestListRead:
    approvals = governance_service.list_approval_requests(
        db,
        auth,
        project_id,
        status_filter=status_filter,
        limit=limit,
    )
    return ApprovalRequestListRead(approvals=[serialize_approval(item) for item in approvals])


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRequestActionRead)
def approve_project_approval(
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ApprovalRequestActionRead:
    approval = _get_project_approval(db, auth, project_id, approval_id)
    if approval.entity_type == "tool_invocation" and approval.entity_id is not None:
        tool_service.approve_tool_invocation(db, auth, project_id, approval.entity_id)
        db.refresh(approval)
    else:
        approval = governance_service.approve_approval_request(db, auth, project_id, approval_id)
    return ApprovalRequestActionRead(approval=serialize_approval(approval))


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRequestActionRead)
def reject_project_approval(
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ApprovalRequestActionRead:
    approval = _get_project_approval(db, auth, project_id, approval_id)
    if approval.entity_type == "tool_invocation" and approval.entity_id is not None:
        tool_service.reject_tool_invocation(db, auth, project_id, approval.entity_id)
        db.refresh(approval)
    else:
        approval = governance_service.reject_approval_request(db, auth, project_id, approval_id)
    return ApprovalRequestActionRead(approval=serialize_approval(approval))


@router.get("/audit-events", response_model=AuditEventListRead)
def list_project_audit_events(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    limit: LimitQuery = 50,
) -> AuditEventListRead:
    events = governance_service.list_audit_events(db, auth, project_id, limit=limit)
    return AuditEventListRead(events=[serialize_audit_event(event) for event in events])


def _get_project_approval(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
) -> ApprovalRequest:
    governance_service.list_approval_requests(db, auth, project_id, limit=1)
    approval = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.workspace_id == auth.workspace_id,
            ApprovalRequest.project_id == project_id,
        )
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
    return approval
