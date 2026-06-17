import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.projects import BuyerType, CustomerSegmentRead, ProblemRead, ProjectRead

InvestigationMode = Literal["quick_orientation", "evidence_review", "validation_sprint"]


class ClarifyingAnswer(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)


class StructuredProjectIntake(BaseModel):
    project_name: str = Field(min_length=1, max_length=255)
    one_sentence_summary: str = Field(min_length=1, max_length=1000)
    target_users: list[str] = Field(default_factory=list, max_length=10)
    buyer_type: BuyerType = "unknown"
    problem_hypotheses: list[str] = Field(default_factory=list, max_length=10)
    proposed_solution: str = Field(min_length=1, max_length=5000)
    market_category: str | None = Field(default=None, max_length=255)
    business_model_guess: str | None = Field(default=None, max_length=255)
    suspected_competitors: list[str] = Field(default_factory=list, max_length=10)
    key_uncertainties: list[str] = Field(default_factory=list, max_length=10)
    clarifying_questions: list[str] = Field(default_factory=list, max_length=7)


class StructuredIntakeAnalyzeCreate(BaseModel):
    raw_idea: str = Field(min_length=1, max_length=10000)
    user_background: str | None = Field(default=None, max_length=5000)
    target_market_guess: str | None = Field(default=None, max_length=1000)
    constraints: str | None = Field(default=None, max_length=5000)


class StructuredIntakeAnswerCreate(BaseModel):
    raw_idea: str = Field(min_length=1, max_length=10000)
    initial_intake: StructuredProjectIntake | None = None
    answers: list[ClarifyingAnswer] = Field(min_length=1, max_length=10)


class StructuredIntakeFinalizeCreate(BaseModel):
    structured_intake: StructuredProjectIntake
    raw_idea: str | None = Field(default=None, max_length=10000)
    answers: list[ClarifyingAnswer] = Field(default_factory=list, max_length=10)


class ConversationalInvestigationPreviewCreate(BaseModel):
    raw_idea: str = Field(min_length=1, max_length=10000)
    answers: list[ClarifyingAnswer] = Field(default_factory=list, max_length=10)
    continue_with_assumptions: bool = False
    mode_preference: InvestigationMode | None = None


class ThesisDraft(BaseModel):
    target_user: str
    problem: str
    current_workaround: str
    proposed_solution: str
    possible_wedge: str
    biggest_unknown: str
    proof_needed: str
    open_questions: list[str] = Field(default_factory=list)


class InvestigationModeOption(BaseModel):
    mode: InvestigationMode
    label: str
    description: str
    why_recommended: str | None = None


class ConversationalInvestigationPreviewRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    raw_idea: str
    structured_intake: StructuredProjectIntake
    thesis_draft: ThesisDraft
    missing_context: list[str]
    clarifying_questions: list[str]
    assumptions_made: list[str]
    recommended_mode: InvestigationModeOption
    modes: list[InvestigationModeOption]
    ready_to_create: bool
    next_action_label: str
    next_action_description: str


class ProjectIntakeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    ai_run_id: uuid.UUID | None
    project_name: str
    one_sentence_summary: str
    target_users: list[str]
    buyer_type: BuyerType
    problem_hypotheses: list[str]
    proposed_solution: str
    market_category: str | None
    business_model_guess: str | None
    suspected_competitors: list[str]
    key_uncertainties: list[str]
    clarifying_questions: list[str]
    user_answers: list[dict[str, str]]
    raw_idea: str | None
    created_at: datetime


class StructuredIntakeRunRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    intake: StructuredProjectIntake


class StructuredIntakeFinalizeRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    project: ProjectRead
    intake_record: ProjectIntakeRead
    customer_segments: list[CustomerSegmentRead]
    problems: list[ProblemRead]
