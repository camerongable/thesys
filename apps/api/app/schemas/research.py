import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ResearchPlanStatus = Literal["draft", "approved", "rejected", "completed"]
ResearchSprintStatus = Literal[
    "planned",
    "approved",
    "running",
    "needs_review",
    "completed",
    "failed",
    "rejected",
]


class ResearchPlanDraft(BaseModel):
    objective: str = Field(min_length=1, max_length=2000)
    target_customer_hypotheses: list[str] = Field(default_factory=list, max_length=8)
    research_questions: list[str] = Field(default_factory=list, max_length=12)
    competitor_queries: list[str] = Field(default_factory=list, max_length=10)
    market_queries: list[str] = Field(default_factory=list, max_length=10)
    substitute_queries: list[str] = Field(default_factory=list, max_length=10)
    source_types: list[str] = Field(default_factory=list, max_length=12)
    assumptions_to_test: list[str] = Field(default_factory=list, max_length=12)
    expected_outputs: list[str] = Field(default_factory=list, max_length=8)


class ResearchSprintPlanCreate(BaseModel):
    objective: str | None = Field(default=None, max_length=2000)


class ResearchPlanUpdate(BaseModel):
    objective: str | None = Field(default=None, min_length=1, max_length=2000)
    target_customer_hypotheses: list[str] | None = Field(default=None, max_length=8)
    research_questions: list[str] | None = Field(default=None, max_length=12)
    competitor_queries: list[str] | None = Field(default=None, max_length=10)
    market_queries: list[str] | None = Field(default=None, max_length=10)
    substitute_queries: list[str] | None = Field(default=None, max_length=10)
    source_types: list[str] | None = Field(default=None, max_length=12)
    assumptions_to_test: list[str] | None = Field(default=None, max_length=12)
    expected_outputs: list[str] | None = Field(default=None, max_length=8)


class ResearchPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    ai_run_id: uuid.UUID | None
    objective: str
    target_customer_hypotheses: list[str]
    research_questions: list[str]
    competitor_queries: list[str]
    market_queries: list[str]
    substitute_queries: list[str]
    source_types: list[str]
    assumptions_to_test: list[str]
    expected_outputs: list[str]
    status: ResearchPlanStatus
    approved_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ResearchSprintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    research_plan_id: uuid.UUID
    ai_run_id: uuid.UUID | None
    status: ResearchSprintStatus
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    plan: ResearchPlanRead


class ResearchSprintListRead(BaseModel):
    sprints: list[ResearchSprintRead]


class ResearchSprintPlanRunRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    sprint: ResearchSprintRead


class ResearchSprintApprovalRead(BaseModel):
    ai_run_id: uuid.UUID | None
    sprint: ResearchSprintRead
