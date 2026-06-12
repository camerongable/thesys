import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

WorkflowStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "waiting_for_human",
]


class WorkflowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ai_run_id: uuid.UUID
    step_name: str
    status: str
    output_json: dict[str, Any] | None
    latency_ms: int | None
    tokens: int | None
    cost: Decimal | None
    langsmith_trace_id: str | None = None
    langsmith_run_id: str | None = None
    langsmith_trace_url: str | None = None
    error: str | None
    created_at: datetime


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    workflow_type: str
    status: WorkflowStatus
    model_provider: str | None
    model_name: str | None
    prompt_version: str | None
    input_summary: str | None
    output_summary: str | None
    total_tokens: int | None
    total_cost: Decimal | None
    langsmith_trace_id: str | None = None
    langsmith_trace_url: str | None = None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    steps: list[WorkflowStepRead] = Field(default_factory=list)


class WorkflowRunListRead(BaseModel):
    runs: list[WorkflowRunRead]
