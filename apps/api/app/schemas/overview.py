import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.artifacts import AssumptionRead, RiskRead
from app.schemas.projects import ProjectRead

ProjectStage = Literal[
    "draft_idea",
    "structured_intake",
    "brief_generated",
    "competitors_analyzed",
    "assumptions_identified",
    "validation_plan_created",
    "experiment_running",
    "decision_ready",
    "paused",
    "killed",
    "proceeding",
]
RecommendationConfidence = Literal["low", "medium", "high"]
ReadinessStatus = Literal[
    "not_ready",
    "partially_ready",
    "ready_for_validation",
    "decision_ready",
]
ReadinessItemStatus = Literal["complete", "missing", "needs_work"]
PlaybookStepStatus = Literal["available", "blocked", "complete", "current"]
StrategicUpdateEntityType = Literal[
    "artifact",
    "evidence",
    "competitor",
    "assumption",
    "experiment",
    "decision",
    "workflow",
]


class StrategicRecommendationRead(BaseModel):
    id: str
    project_id: uuid.UUID
    recommendation: str
    rationale: str
    confidence: RecommendationConfidence
    next_action_type: str
    next_action_label: str
    source_artifact_ids: list[uuid.UUID] = Field(default_factory=list)
    source_evidence_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime


class NextBestActionRead(BaseModel):
    action_type: str
    label: str
    description: str
    why_it_matters: str
    primary: bool
    related_stage: ProjectStage
    target_route: str | None = None


class PlaybookStepRead(BaseModel):
    key: str
    label: str
    purpose: str
    status: PlaybookStepStatus
    is_current_stage: bool
    target_route: str


class ReadinessItemRead(BaseModel):
    key: str
    label: str
    status: ReadinessItemStatus
    related_action: str | None = None


class IdeaReadinessRead(BaseModel):
    project_id: uuid.UUID
    score: int = Field(ge=0, le=100)
    status: ReadinessStatus
    completed_items: list[ReadinessItemRead]
    missing_items: list[ReadinessItemRead]
    weakest_area: str
    recommended_next_action: str


class StrategicSnapshotRead(BaseModel):
    current_thesis: str | None = None
    target_user: str | None = None
    primary_problem: str | None = None
    proposed_wedge: str | None = None
    main_risk: str | None = None
    current_confidence: RecommendationConfidence
    current_stage: ProjectStage


class EvidenceHealthRead(BaseModel):
    source_count: int
    competitor_count: int
    cited_claim_count: int
    unsupported_claim_count: int
    validated_assumption_count: int
    weakest_evidence_area: str
    last_evidence_update: datetime | None = None


class StrategicUpdateRead(BaseModel):
    id: str
    project_id: uuid.UUID
    title: str
    summary: str
    why_it_matters: str
    related_entity_type: StrategicUpdateEntityType
    related_entity_id: uuid.UUID
    created_at: datetime


class ProjectOverviewRead(BaseModel):
    project: ProjectRead
    current_recommendation: StrategicRecommendationRead
    next_best_action: NextBestActionRead
    secondary_actions: list[NextBestActionRead] = Field(default_factory=list, max_length=2)
    playbook_steps: list[PlaybookStepRead] = Field(default_factory=list)
    idea_readiness: IdeaReadinessRead
    strategic_snapshot: StrategicSnapshotRead
    evidence_health: EvidenceHealthRead
    recent_strategic_updates: list[StrategicUpdateRead] = Field(default_factory=list)
    key_assumptions: list[AssumptionRead] = Field(default_factory=list)
    key_risks: list[RiskRead] = Field(default_factory=list)
