import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

AuditActorType = Literal["user", "agent", "system"]
GovernanceRiskLevel = Literal["low", "medium", "high"]
SecurityEventSeverity = Literal["info", "low", "medium", "high", "critical"]
SecurityEventSource = Literal[
    "api", "guardrail", "retrieval", "tool", "memory", "workflow", "auth", "mcp"
]
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


class SecurityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    user_id: uuid.UUID | None
    audit_event_id: uuid.UUID | None
    ai_run_id: uuid.UUID | None
    tool_invocation_id: uuid.UUID | None
    approval_request_id: uuid.UUID | None
    session_id: str | None
    request_id: str | None
    langsmith_trace_id: str | None
    temporal_workflow_id: str | None
    event_type: str
    severity: SecurityEventSeverity
    source: SecurityEventSource
    summary: str
    attributes: dict[str, object]
    detected_at: datetime
    containment_status: str | None


class SecurityEventListRead(BaseModel):
    events: list[SecurityEventRead]


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
