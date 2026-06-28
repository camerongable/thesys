import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

GuideActionType = Literal[
    "navigate",
    "open_form",
    "run_workflow",
    "generate_draft",
    "explain",
    "compare_wedges",
    "update_thesis",
    "log_result",
    "record_decision",
]
GuideRiskLevel = Literal["none", "low", "medium", "high"]
GuideConfidenceLevel = Literal["unknown", "low", "medium", "high"]
GuideRelatedEntityType = Literal[
    "evidence",
    "assumption",
    "validation_plan",
    "decision",
    "research",
    "thesis",
]
GuideCitationVerifierStatus = Literal["supported", "weak", "missing", "filtered"]


class GuideActionRead(BaseModel):
    id: str
    type: GuideActionType
    label: str
    description: str
    why_it_matters: str
    target_route: str | None = None
    target_modal: str | None = None
    payload: dict[str, Any] | None = None
    risk_level: Literal["low", "medium", "high"]
    requires_confirmation: bool


class GuideEvidenceSummaryRead(BaseModel):
    sources: int
    competitors: int
    supported_findings: int
    open_questions: int
    validated_assumptions: int


class GuideContextRead(BaseModel):
    project_id: uuid.UUID
    project_name: str
    stage: str
    verdict: str
    next_action: str
    risk_level: GuideRiskLevel
    confidence_level: GuideConfidenceLevel
    current_thesis: str | None = None
    target_user: str | None = None
    primary_problem: str | None = None
    current_wedge: str | None = None
    biggest_unknown: str | None = None
    active_validation_plan_id: uuid.UUID | None = None
    latest_research_sprint_id: uuid.UUID | None = None
    evidence_summary: GuideEvidenceSummaryRead
    missing_context: list[str] = Field(default_factory=list)
    available_actions: list[GuideActionRead] = Field(default_factory=list)


class GuideResponseRead(BaseModel):
    summary: str
    current_focus: str
    why_this_matters: str
    after_that: str
    recommended_action: GuideActionRead
    secondary_actions: list[GuideActionRead] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class GuideChatTurnRead(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class GuideChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    recent_turns: list[GuideChatTurnRead] = Field(default_factory=list, max_length=6)


class GuideRelatedEntityRead(BaseModel):
    type: GuideRelatedEntityType
    id: str
    label: str


class GuideCitationDetailRead(BaseModel):
    source_id: str
    chunk_id: str | None = None
    title: str | None = None
    url: str | None = None
    source_type: str | None = None
    excerpt: str | None = None
    score: float | None = None
    verifier_status: GuideCitationVerifierStatus = "supported"
    context_item_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    source_quality: dict[str, Any] = Field(default_factory=dict)
    extraction: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(default_factory=dict)
    page_number: int | None = None
    section_heading: str | None = None
    table_id: str | None = None
    region: dict[str, Any] | None = None
    quote_offsets: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class GuideChatResponseRead(BaseModel):
    answer: str
    recommended_action: GuideActionRead | None = None
    action_cards: list[GuideActionRead] = Field(default_factory=list)
    related_entities: list[GuideRelatedEntityRead] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    citation_details: list[GuideCitationDetailRead] = Field(default_factory=list)
    assumption_ids: list[str] = Field(default_factory=list)
    confidence_level: GuideConfidenceLevel = "unknown"
    unsupported_or_missing_evidence: list[str] = Field(default_factory=list)
    used_llm: bool = False
    retrieval_diagnostics: dict[str, Any] | None = None
    context_pack: dict[str, Any] | None = None
    proposal_invocation_id: uuid.UUID | None = None
    approval_request_id: uuid.UUID | None = None
    ai_run_id: uuid.UUID | None = None
