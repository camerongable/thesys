import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.artifacts import (
    ArtifactRead,
    AssumptionDraft,
    AssumptionImportance,
    AssumptionRead,
    AssumptionStatus,
    AssumptionUncertainty,
    RiskDraft,
    RiskRead,
)

ExperimentStatus = Literal["planned", "running", "completed", "cancelled"]
ExperimentOutcome = Literal["positive", "negative", "mixed", "inconclusive"]
ExpectedSignalStrength = Literal["weak", "medium", "strong"]
ValidationMissionStatus = Literal[
    "planned",
    "running",
    "results_logged",
    "interpreted",
    "closed",
]
ValidationSignalStrength = Literal["none", "weak", "medium", "strong"]
ValidationSignalLevel = Literal["none", "low", "medium", "high"]
ValidationConfidenceChange = Literal["decrease", "no_change", "increase"]
DecisionRecommendation = Literal["proceed", "pivot", "pause", "kill", "continue_research"]
DecisionType = Literal[
    "build",
    "pivot",
    "pause",
    "kill",
    "change_icp",
    "change_positioning",
    "run_experiment",
    "other",
]
DecisionLinkedType = Literal[
    "evidence",
    "assumption",
    "risk",
    "artifact",
    "competitor",
    "experiment",
]


class AssumptionListRead(BaseModel):
    assumptions: list[AssumptionRead]


class AssumptionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    category: str | None = Field(default=None, max_length=100)
    importance: AssumptionImportance | None = None
    uncertainty: AssumptionUncertainty | None = None
    kill_risk: bool | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    status: AssumptionStatus | None = None
    recommended_test: str | None = Field(default=None, max_length=5000)


class RiskListRead(BaseModel):
    risks: list[RiskRead]


class AssumptionExtractionDraft(BaseModel):
    assumptions: list[AssumptionDraft] = Field(default_factory=list)
    risks: list[RiskDraft] = Field(default_factory=list)


class AssumptionExtractionRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    assumptions: list[AssumptionRead]
    risks: list[RiskRead]


class ValidationPlanDraft(BaseModel):
    assumption_id: uuid.UUID
    assumption_text: str = Field(min_length=1, max_length=2000)
    method: str = Field(min_length=1, max_length=120)
    target_respondent: str = Field(min_length=1, max_length=1000)
    screener_questions: list[str] = Field(default_factory=list, max_length=10)
    steps: list[str] = Field(default_factory=list, max_length=12)
    interview_questions: list[str] = Field(default_factory=list, max_length=12)
    survey_questions: list[str] = Field(default_factory=list, max_length=12)
    landing_page_copy: str | None = Field(default=None, max_length=2000)
    outreach_message: str | None = Field(default=None, max_length=2000)
    note_taking_template: str | None = Field(default=None, max_length=3000)
    result_interpretation_rubric: str | None = Field(default=None, max_length=3000)
    success_criteria: str = Field(min_length=1, max_length=5000)
    failure_threshold: str = Field(min_length=1, max_length=5000)
    expected_signal_strength: ExpectedSignalStrength


class ValidationPlanSetDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=5000)
    plans: list[ValidationPlanDraft] = Field(default_factory=list, max_length=10)


class ValidationPlanGenerateCreate(BaseModel):
    assumption_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    max_plans: int = Field(default=3, ge=1, le=10)


class ExperimentResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    experiment_id: uuid.UUID
    result_summary: str
    outcome: ExperimentOutcome
    confidence_delta: Decimal | None
    raw_notes: str | None
    created_by: uuid.UUID | None
    created_at: datetime


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    assumption_id: uuid.UUID | None
    name: str
    method: str | None
    plan: str | None
    success_criteria: str | None
    failure_threshold: str | None
    status: ExperimentStatus
    created_at: datetime
    updated_at: datetime
    results: list[ExperimentResultRead] = Field(default_factory=list)


class ExperimentListRead(BaseModel):
    experiments: list[ExperimentRead]


class ExperimentResultCreate(BaseModel):
    result_summary: str = Field(min_length=1, max_length=5000)
    outcome: ExperimentOutcome
    confidence_delta: float | None = Field(default=None, ge=-1, le=1)
    raw_notes: str | None = Field(default=None, max_length=10000)


class ExperimentResultCreateRead(BaseModel):
    result: ExperimentResultRead
    experiment: ExperimentRead
    assumption: AssumptionRead | None
    project_confidence_score: Decimal | None


class ValidationSignalDraft(BaseModel):
    pain_severity: ValidationSignalLevel
    current_workaround: str = Field(min_length=1, max_length=2000)
    urgency: Literal["low", "medium", "high"]
    willingness_to_pay: ValidationSignalStrength
    switching_signal: ValidationSignalStrength
    objections: list[str] = Field(default_factory=list, max_length=10)
    quotes: list[str] = Field(default_factory=list, max_length=10)
    confidence_change: ValidationConfidenceChange
    recommended_next_action: str = Field(min_length=1, max_length=2000)


class ValidationResultInterpretationDraft(BaseModel):
    signal_summary: str = Field(min_length=1, max_length=3000)
    what_strengthened: list[str] = Field(default_factory=list, max_length=10)
    what_weakened: list[str] = Field(default_factory=list, max_length=10)
    signal: ValidationSignalDraft
    confidence_rationale: str = Field(min_length=1, max_length=3000)
    proposed_confidence_delta: float = Field(ge=-1, le=1)
    proposed_assumption_status: AssumptionStatus | None = None
    decision_recommendation: DecisionRecommendation


class ValidationResultInterpretationCreate(BaseModel):
    raw_notes: str | None = Field(default=None, max_length=20000)
    include_logged_results: bool = True


class ValidationResultInterpretationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    mission_id: uuid.UUID
    experiment_id: uuid.UUID | None
    assumption_id: uuid.UUID | None
    ai_run_id: uuid.UUID | None
    approval_request_id: uuid.UUID | None
    raw_notes: str
    signal_summary: str
    what_strengthened: list[str] = Field(default_factory=list)
    what_weakened: list[str] = Field(default_factory=list)
    pain_severity: ValidationSignalLevel
    current_workaround: str
    urgency: Literal["low", "medium", "high"]
    willingness_to_pay: ValidationSignalStrength
    switching_signal: ValidationSignalStrength
    objections: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    confidence_change: ValidationConfidenceChange
    confidence_rationale: str
    recommended_next_action: str
    decision_recommendation: DecisionRecommendation
    proposed_confidence_delta: Decimal
    proposed_assumption_status: AssumptionStatus | None
    proposed_updates: dict[str, object]
    created_by: uuid.UUID | None
    created_at: datetime


class ValidationAssetRead(BaseModel):
    type: str
    title: str
    content: str


class ValidationMissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    assumption_id: uuid.UUID
    experiment_id: uuid.UUID | None
    mission_title: str
    why_it_matters: str
    target_user: str
    test_type: str
    steps: list[str] = Field(default_factory=list)
    success_criteria: str
    failure_criteria: str
    assets: list[ValidationAssetRead] = Field(default_factory=list)
    result_count: int
    status: ValidationMissionStatus
    created_at: datetime
    updated_at: datetime
    latest_interpretation: ValidationResultInterpretationRead | None = None


class ValidationMissionListRead(BaseModel):
    missions: list[ValidationMissionRead]


class CurrentValidationMissionRead(BaseModel):
    mission: ValidationMissionRead | None


class ValidationPlanGenerateRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    artifact: ArtifactRead
    experiments: list[ExperimentRead]
    missions: list[ValidationMissionRead] = Field(default_factory=list)


class ValidationResultInterpretationRunRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    mission: ValidationMissionRead
    interpretation: ValidationResultInterpretationRead
    approval_request_id: uuid.UUID | None


class DecisionLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    decision_id: uuid.UUID
    linked_type: DecisionLinkedType
    linked_id: uuid.UUID
    created_at: datetime


class DecisionCreate(BaseModel):
    decision_type: DecisionType
    title: str = Field(min_length=1, max_length=255)
    rationale: str | None = Field(default=None, max_length=10000)
    expected_outcome: str | None = Field(default=None, max_length=5000)
    review_date: date | None = None
    linked_assumption_ids: list[uuid.UUID] = Field(default_factory=list, max_length=25)
    linked_risk_ids: list[uuid.UUID] = Field(default_factory=list, max_length=25)
    linked_evidence_source_ids: list[uuid.UUID] = Field(default_factory=list, max_length=25)
    linked_artifact_ids: list[uuid.UUID] = Field(default_factory=list, max_length=25)
    linked_competitor_ids: list[uuid.UUID] = Field(default_factory=list, max_length=25)
    linked_experiment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=25)


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    decision_type: DecisionType
    title: str
    rationale: str | None
    expected_outcome: str | None
    review_date: date | None
    created_by: uuid.UUID | None
    created_at: datetime
    links: list[DecisionLinkRead] = Field(default_factory=list)


class DecisionListRead(BaseModel):
    decisions: list[DecisionRead]
