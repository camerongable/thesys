import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ArtifactType = Literal[
    "opportunity_brief",
    "competitor_landscape",
    "validation_plan",
    "decision_memo",
    "research_memo",
    "customer_discovery_summary",
    "other",
]
ClaimSupportLevel = Literal["supported", "partial", "unsupported", "inference"]
AssumptionImportance = Literal["low", "medium", "high", "critical"]
AssumptionUncertainty = Literal["low", "medium", "high"]
AssumptionStatus = Literal["untested", "testing", "validated", "invalidated", "inconclusive"]
RiskSeverity = Literal["low", "medium", "high", "critical"]
RiskLikelihood = Literal["low", "medium", "high", "unknown"]
RiskStatus = Literal["open", "mitigated", "accepted", "closed"]


class Citation(BaseModel):
    source_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    title: str | None = None
    url: str | None = None
    quote: str | None = None
    retrieved_at: datetime | None = None
    relevance_score: float | None = Field(default=None, ge=0)


class ClaimDraft(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    claim_type: str | None = Field(default=None, max_length=80)
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    support_level: ClaimSupportLevel
    citations: list[Citation] = Field(default_factory=list)


class AssumptionDraft(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    category: str | None = Field(default=None, max_length=100)
    importance: AssumptionImportance
    uncertainty: AssumptionUncertainty
    kill_risk: bool = False
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    recommended_test: str | None = Field(default=None, max_length=5000)


class RiskDraft(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    category: str | None = Field(default=None, max_length=100)
    severity: RiskSeverity
    likelihood: RiskLikelihood
    mitigation: str | None = Field(default=None, max_length=5000)


class OpportunityBriefDraft(BaseModel):
    executive_summary: str
    product_hypothesis: str
    target_user: str
    problem_analysis: str
    current_alternatives: list[str] = Field(default_factory=list)
    market_context: str
    competitor_landscape: str
    differentiation_and_wedge: str
    risks_and_kill_assumptions: str
    validation_plan: str
    recommendation: str
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    claims: list[ClaimDraft] = Field(default_factory=list)
    assumptions: list[AssumptionDraft] = Field(default_factory=list)
    risks: list[RiskDraft] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


class ClaimEvidenceLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_source_id: uuid.UUID
    evidence_chunk_id: uuid.UUID | None
    relevance_score: Decimal | None
    quote: str | None
    created_at: datetime


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    artifact_version_id: uuid.UUID | None
    text: str
    claim_type: str | None
    confidence_score: Decimal | None
    support_level: ClaimSupportLevel
    created_at: datetime
    evidence_links: list[ClaimEvidenceLinkRead] = Field(default_factory=list)


class AssumptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    text: str
    category: str | None
    importance: AssumptionImportance
    uncertainty: AssumptionUncertainty
    kill_risk: bool
    confidence_score: Decimal | None
    status: AssumptionStatus
    recommended_test: str | None
    created_at: datetime
    updated_at: datetime


class RiskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    text: str
    category: str | None
    severity: RiskSeverity
    likelihood: RiskLikelihood
    mitigation: str | None
    status: RiskStatus
    created_at: datetime
    updated_at: datetime


class ArtifactVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    artifact_id: uuid.UUID
    version: int
    markdown_content: str
    structured_content: dict[str, object]
    generated_by_ai_run_id: uuid.UUID | None
    created_at: datetime
    claims: list[ClaimRead] = Field(default_factory=list)


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    artifact_type: ArtifactType
    title: str
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    current_version: ArtifactVersionRead | None = None
    versions: list[ArtifactVersionRead] = Field(default_factory=list)


class ArtifactListRead(BaseModel):
    artifacts: list[ArtifactRead]


class ArtifactVersionListRead(BaseModel):
    versions: list[ArtifactVersionRead]


class OpportunityBriefGenerateRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    retrieval_result_count: int
    artifact: ArtifactRead
    version: ArtifactVersionRead
    claims: list[ClaimRead]
    assumptions: list[AssumptionRead]
    risks: list[RiskRead]
    citations: list[Citation]
    unsupported_claims: list[str]
