import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProjectStatus = Literal["active", "paused", "killed", "launched", "archived"]
BuyerType = Literal["consumer", "prosumer", "smb", "midmarket", "enterprise", "unknown"]
SegmentPriority = Literal["primary", "secondary", "rejected", "unknown"]
ProblemSeverity = Literal["low", "medium", "high", "critical", "unknown"]


class ProjectThesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    thesis_text: str
    rationale: str | None
    confidence_score: Decimal | None
    created_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    short_description: str | None = Field(default=None, max_length=5000)
    initial_thesis: str | None = Field(default=None, min_length=1, max_length=10000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    short_description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None


class CustomerSegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    buyer_type: BuyerType | None
    priority: SegmentPriority | None
    confidence_score: Decimal | None
    created_at: datetime
    updated_at: datetime


class ProblemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    segment_id: uuid.UUID | None
    description: str
    severity: ProblemSeverity | None
    frequency: str | None
    current_alternatives: str | None
    confidence_score: Decimal | None
    created_at: datetime
    updated_at: datetime


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    short_description: str | None
    status: ProjectStatus
    current_thesis_id: uuid.UUID | None
    confidence_score: Decimal | None
    created_at: datetime
    updated_at: datetime
    current_thesis: ProjectThesisRead | None = None
    customer_segments: list[CustomerSegmentRead] = Field(default_factory=list)
    problems: list[ProblemRead] = Field(default_factory=list)


class ProjectListRead(BaseModel):
    projects: list[ProjectRead]
