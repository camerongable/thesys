import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ToolRiskLevel = Literal["low", "medium", "high"]
ToolAccessMode = Literal["read", "write", "proposal"]
ApprovalPolicy = Literal["never_required", "required_for_write", "always_required"]
ToolInvocationStatus = Literal["requested", "approved", "rejected", "executed", "failed"]
ToolRequestedBy = Literal["agent", "user", "system"]


class AgentToolDefinitionRead(BaseModel):
    name: str
    title: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    access_mode: ToolAccessMode
    risk_level: ToolRiskLevel
    approval_policy: ApprovalPolicy
    allowed_project_roles: list[str]


class ToolRegistryRead(BaseModel):
    tools: list[AgentToolDefinitionRead]


class ToolInvocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    research_sprint_id: uuid.UUID | None
    tool_name: str
    access_mode: ToolAccessMode
    risk_level: ToolRiskLevel
    input_json: dict[str, object]
    output_json: dict[str, object] | None
    output_summary: str | None
    status: ToolInvocationStatus
    requested_by: ToolRequestedBy
    approved_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None


class ToolInvocationListRead(BaseModel):
    invocations: list[ToolInvocationRead]


class ToolInvocationActionRead(BaseModel):
    invocation: ToolInvocationRead
