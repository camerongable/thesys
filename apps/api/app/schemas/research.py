import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.artifacts import (
    ArtifactRead,
    ArtifactVersionRead,
    AssumptionDraft,
    Citation,
    ClaimDraft,
    ClaimRead,
    RiskDraft,
)

ResearchPlanStatus = Literal["draft", "approved", "rejected", "completed"]
ResearchSprintStatus = Literal[
    "planned",
    "waiting_for_approval",
    "approved",
    "running",
    "needs_review",
    "waiting_for_memory_approval",
    "completed",
    "failed",
    "cancelled",
    "rejected",
]
DiscoveredSourceType = Literal[
    "company_site",
    "pricing_page",
    "product_page",
    "review",
    "forum",
    "blog",
    "market_report",
    "directory",
    "docs",
    "unknown",
]
DiscoveredSourceStatus = Literal["candidate", "approved", "rejected", "ingested", "failed"]
CompetitorCandidateCategory = Literal[
    "direct_competitor",
    "indirect_competitor",
    "substitute_behavior",
    "incumbent_platform",
    "adjacent_solution",
    "irrelevant",
]
CompetitorCandidateStatus = Literal["candidate", "approved", "rejected", "merged"]
CompetitorCandidateThreatLevel = Literal["low", "medium", "high"]


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
    temporal_workflow_id: str | None = None
    temporal_run_id: str | None = None
    current_step: str | None = None
    failed_step: str | None = None
    failure_message: str | None = None
    started_at: datetime | None
    completed_at: datetime | None
    langsmith_trace_id: str | None = None
    langsmith_trace_url: str | None = None
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


class ResearchSprintExecutionRead(BaseModel):
    sprint: ResearchSprintRead
    temporal_enabled: bool
    temporal_workflow_id: str | None
    temporal_run_id: str | None
    status: ResearchSprintStatus
    current_step: str | None
    failed_step: str | None
    failure_message: str | None
    action_required: str | None = None


class ResearchSprintExecutionActionRead(BaseModel):
    sprint: ResearchSprintRead
    action: Literal["started", "cancelled", "retried", "signaled"]
    temporal_workflow_id: str | None


class DiscoveredSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    research_sprint_id: uuid.UUID
    evidence_source_id: uuid.UUID | None
    url: str
    title: str | None
    snippet: str | None
    source_type: DiscoveredSourceType
    search_provider: str | None = None
    search_query: str | None = None
    search_result_rank: int | None = None
    retrieved_at: datetime | None = None
    risk_level: Literal["low", "medium", "high"] = "medium"
    provenance_metadata: dict[str, object] = Field(default_factory=dict)
    relevance_score: Decimal
    reason_selected: str
    associated_research_question: str | None
    status: DiscoveredSourceStatus
    ingestion_error: str | None
    ingested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DiscoveredSourceListRead(BaseModel):
    sources: list[DiscoveredSourceRead]


class SourceDiscoveryCandidateDraft(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=500)
    snippet: str | None = Field(default=None, max_length=2000)
    source_type: DiscoveredSourceType = "unknown"
    relevance_score: Decimal = Field(ge=0, le=1)
    reason_selected: str = Field(min_length=1, max_length=5000)
    associated_research_question: str | None = Field(default=None, max_length=2000)


class SourceDiscoveryDraft(BaseModel):
    sources: list[SourceDiscoveryCandidateDraft] = Field(default_factory=list, max_length=12)


class SourceDiscoveryRunRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    generated_count: int
    candidate_count: int
    search_diagnostics: dict[str, object] = Field(default_factory=dict)
    sources: list[DiscoveredSourceRead]


class DiscoveredSourceActionRead(BaseModel):
    source: DiscoveredSourceRead


class CompetitorCandidateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    category: CompetitorCandidateCategory | None = None
    target_user: str | None = Field(default=None, max_length=5000)
    positioning: str | None = Field(default=None, max_length=5000)
    pricing_signal: str | None = Field(default=None, max_length=5000)
    core_features: list[str] | None = Field(default=None, max_length=25)
    why_it_matters: str | None = Field(default=None, min_length=1, max_length=5000)
    threat_level: CompetitorCandidateThreatLevel | None = None
    relevance_score: Decimal | None = Field(default=None, ge=0, le=1)


class CompetitorCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    research_sprint_id: uuid.UUID
    competitor_id: uuid.UUID | None
    evidence_source_id: uuid.UUID | None
    name: str
    url: str | None
    category: CompetitorCandidateCategory
    target_user: str | None
    positioning: str | None
    pricing_signal: str | None
    core_features: list[str]
    why_it_matters: str
    threat_level: CompetitorCandidateThreatLevel
    relevance_score: Decimal
    source_ids: list[str]
    status: CompetitorCandidateStatus
    ingestion_error: str | None
    ingested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CompetitorCandidateListRead(BaseModel):
    candidates: list[CompetitorCandidateRead]


class CompetitorDiscoveryCandidateDraft(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str | None = Field(default=None, max_length=2000)
    category: CompetitorCandidateCategory
    target_user: str | None = Field(default=None, max_length=5000)
    positioning: str | None = Field(default=None, max_length=5000)
    pricing_signal: str | None = Field(default=None, max_length=5000)
    core_features: list[str] = Field(default_factory=list, max_length=25)
    why_it_matters: str = Field(min_length=1, max_length=5000)
    threat_level: CompetitorCandidateThreatLevel
    relevance_score: Decimal = Field(ge=0, le=1)
    source_ids: list[str] = Field(default_factory=list, max_length=12)


class CompetitorDiscoveryDraft(BaseModel):
    candidates: list[CompetitorDiscoveryCandidateDraft] = Field(
        default_factory=list,
        max_length=12,
    )


class CompetitorDiscoveryRunRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    generated_count: int
    candidate_count: int
    candidates: list[CompetitorCandidateRead]


class CompetitorCandidateActionRead(BaseModel):
    candidate: CompetitorCandidateRead


class ResearchFindingDraft(BaseModel):
    subquestion: str = Field(min_length=1, max_length=1000)
    finding: str = Field(min_length=1, max_length=2000)
    evidence_strength: Literal["weak", "medium", "strong"]
    citations: list[Citation] = Field(default_factory=list, max_length=5)


class ResearchAssumptionDraft(AssumptionDraft):
    evidence_strength: Literal["weak", "medium", "strong"] = "weak"
    citations: list[Citation] = Field(default_factory=list, max_length=5)


class ResearchRiskDraft(RiskDraft):
    citations: list[Citation] = Field(default_factory=list, max_length=5)


class AgenticResearchMemoDraft(BaseModel):
    executive_verdict: str = Field(min_length=1, max_length=2000)
    best_wedge: str = Field(min_length=1, max_length=2000)
    market_landscape: str = Field(default="", max_length=3000)
    customer_pain_signals: str = Field(default="", max_length=3000)
    competitor_landscape: str = Field(default="", max_length=3000)
    substitute_behaviors: str = Field(default="", max_length=3000)
    pricing_business_model_signals: str = Field(default="", max_length=3000)
    findings: list[ResearchFindingDraft] = Field(default_factory=list, max_length=10)
    key_risks: list[ResearchRiskDraft] = Field(default_factory=list, max_length=8)
    riskiest_assumptions: list[ResearchAssumptionDraft] = Field(default_factory=list, max_length=8)
    evidence_summary: str = Field(default="", max_length=3000)
    evidence_gaps: list[str] = Field(default_factory=list, max_length=10)
    what_we_still_do_not_know: list[str] = Field(default_factory=list, max_length=10)
    recommended_validation_actions: list[str] = Field(default_factory=list, max_length=8)
    decision_recommendation: str = Field(min_length=1, max_length=2000)
    comparison_to_mvp_brief: str | None = Field(default=None, max_length=2000)
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=12)
    citations: list[Citation] = Field(default_factory=list, max_length=20)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=12)


class AgenticResearchRunRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    retrieval_tool_call_count: int
    additional_retrieval_passes: int
    evidence_gap_count: int
    artifact: ArtifactRead
    version: ArtifactVersionRead
    claims: list[ClaimRead]
    citations: list[Citation]
    unsupported_claims: list[str]


class AgenticResearchApprovalRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    sprint: ResearchSprintRead
    artifact: ArtifactRead
    version: ArtifactVersionRead


ResearchHistoryEventType = Literal[
    "plan_created",
    "plan_approved",
    "plan_rejected",
    "source_discovery",
    "source_ingestion",
    "competitor_discovery",
    "competitor_merge",
    "memo_generated",
    "memory_update_approved",
    "memory_update_rejected",
    "sprint_completed",
    "sprint_failed",
]
ResearchHistoryEntityType = Literal[
    "research_sprint",
    "research_plan",
    "artifact",
    "artifact_version",
    "evidence",
    "competitor",
    "assumption",
    "risk",
    "workflow",
]


class ResearchHistoryEventRead(BaseModel):
    id: str
    research_sprint_id: uuid.UUID
    event_type: ResearchHistoryEventType
    title: str
    summary: str
    why_it_matters: str
    related_entity_type: ResearchHistoryEntityType
    related_entity_id: uuid.UUID
    created_at: datetime


class ResearchSprintHistoryRead(BaseModel):
    sprint: ResearchSprintRead
    source_candidate_count: int
    ingested_source_count: int
    competitor_candidate_count: int
    merged_competitor_count: int
    memo_artifact_id: uuid.UUID | None = None
    memo_version_id: uuid.UUID | None = None
    memory_update_status: str | None = None
    memory_update_summary: dict[str, object] | None = None
    recommendation_change: str | None = None
    events: list[ResearchHistoryEventRead] = Field(default_factory=list)


class ProjectResearchHistoryRead(BaseModel):
    project_id: uuid.UUID
    sprint_count: int
    completed_sprint_count: int
    pending_review_sprint_count: int
    latest_recommendation_change: str | None = None
    sprints: list[ResearchSprintHistoryRead] = Field(default_factory=list)
