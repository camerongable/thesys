import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CompetitorPressure = Literal["low", "medium", "high"]
EvidenceStrength = Literal["none", "weak", "partial", "strong"]
WedgeRecommendation = Literal[
    "recommended",
    "promising",
    "research_later",
    "avoid_for_now",
    "rejected",
]


class WedgeOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str
    target_user: str
    problem_focus: str
    why_it_might_work: str
    main_risk: str
    competitor_pressure: CompetitorPressure
    evidence_strength: EvidenceStrength
    validation_test: str
    recommendation: WedgeRecommendation
    source_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WedgeOptionListRead(BaseModel):
    wedges: list[WedgeOptionRead] = Field(default_factory=list)
    recommended_wedge_id: uuid.UUID | None = None
    recommendation_summary: str


class WedgeActionRead(BaseModel):
    wedge: WedgeOptionRead
    message: str
