import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.artifacts import ArtifactRead, Citation, ClaimDraft, ClaimRead

CompetitorCategory = Literal[
    "direct",
    "adjacent",
    "incumbent",
    "substitute",
    "manual_alternative",
    "unknown",
]
CompetitorThreatLevel = Literal["low", "medium", "high", "unknown"]


class CompetitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    category: CompetitorCategory = "unknown"

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        return normalize_competitor_url(value)


class CompetitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    category: CompetitorCategory | None = None
    target_user: str | None = Field(default=None, max_length=5000)
    positioning: str | None = Field(default=None, max_length=5000)
    pricing_summary: str | None = Field(default=None, max_length=5000)
    key_features: list[str] | None = Field(default=None, max_length=25)
    strengths: str | None = Field(default=None, max_length=5000)
    weaknesses: str | None = Field(default=None, max_length=5000)
    differentiation_notes: str | None = Field(default=None, max_length=5000)
    threat_level: CompetitorThreatLevel | None = None
    watchlist_status: str | None = Field(default=None, max_length=30)

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        return normalize_competitor_url(value)


def normalize_competitor_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    if "://" in stripped:
        return stripped
    return f"https://{stripped}"


class CompetitorAnalyzeCreate(BaseModel):
    seed_competitors: list[CompetitorCreate] = Field(default_factory=list, max_length=10)
    ingest_urls: bool = True


class CompetitorProfileDraft(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    category: CompetitorCategory
    target_user: str | None = Field(default=None, max_length=5000)
    positioning: str | None = Field(default=None, max_length=5000)
    pricing_summary: str | None = Field(default=None, max_length=5000)
    key_features: list[str] = Field(default_factory=list, max_length=25)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    weaknesses: list[str] = Field(default_factory=list, max_length=20)
    differentiation_notes: str | None = Field(default=None, max_length=5000)
    threat_level: CompetitorThreatLevel
    citations: list[Citation] = Field(default_factory=list)


class CompetitorClusterDraft(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    competitors: list[str] = Field(default_factory=list, max_length=25)
    positioning_summary: str = Field(min_length=1, max_length=5000)


class CompetitorAnalysisDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=5000)
    competitors: list[CompetitorProfileDraft] = Field(default_factory=list)
    clusters: list[CompetitorClusterDraft] = Field(default_factory=list)
    positioning_gaps: list[str] = Field(default_factory=list, max_length=20)
    wedge_recommendations: list[str] = Field(default_factory=list, max_length=20)
    where_not_to_compete: list[str] = Field(default_factory=list, max_length=20)
    claims: list[ClaimDraft] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


class CompetitorEvidenceLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_source_id: uuid.UUID
    evidence_chunk_id: uuid.UUID | None
    created_at: datetime


class CompetitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    url: str | None
    category: CompetitorCategory
    target_user: str | None
    positioning: str | None
    pricing_summary: str | None
    key_features: list[str]
    strengths: str | None
    weaknesses: str | None
    differentiation_notes: str | None
    threat_level: CompetitorThreatLevel
    watchlist_status: str
    last_analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    evidence_links: list[CompetitorEvidenceLinkRead] = Field(default_factory=list)


class CompetitorListRead(BaseModel):
    competitors: list[CompetitorRead]


class CompetitorAnalysisRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    retrieval_result_count: int
    ingested_source_count: int
    artifact: ArtifactRead
    competitors: list[CompetitorRead]
    claims: list[ClaimRead]
    citations: list[Citation]
    unsupported_claims: list[str]
