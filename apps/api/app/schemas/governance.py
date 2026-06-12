import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

AuditActorType = Literal["user", "agent", "system"]
GovernanceRiskLevel = Literal["low", "medium", "high"]
ApprovalRequestType = Literal[
    "research_plan",
    "memory_update",
    "tool_invocation",
    "validation_plan",
    "decision",
]
ApprovalRequestStatus = Literal["pending", "approved", "rejected", "expired"]
ApprovalRequestedBy = Literal["agent", "user", "system"]


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    user_id: uuid.UUID | None
    event_type: str
    actor_type: AuditActorType
    entity_type: str | None
    entity_id: uuid.UUID | None
    summary: str
    risk_level: GovernanceRiskLevel | None
    event_metadata: dict[str, object]
    created_at: datetime


class AuditEventListRead(BaseModel):
    events: list[AuditEventRead]


class ApprovalRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    request_type: ApprovalRequestType
    status: ApprovalRequestStatus
    requested_by: ApprovalRequestedBy
    approved_by_user_id: uuid.UUID | None
    risk_level: GovernanceRiskLevel
    summary: str
    proposed_change: dict[str, object]
    entity_type: str | None
    entity_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class ApprovalRequestListRead(BaseModel):
    approvals: list[ApprovalRequestRead]


class ApprovalRequestActionRead(BaseModel):
    approval: ApprovalRequestRead
