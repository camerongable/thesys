import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ThesisEvolutionEventType = Literal[
    "original_idea",
    "structured_thesis",
    "research_update",
    "wedge_change",
    "validation_blocker",
    "decision",
    "manual_update",
]
ThesisEvolutionOrigin = Literal["user", "agent", "system"]


class ThesisCanvasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    original_idea: str
    current_thesis: str
    target_user: str
    problem: str
    current_workaround: str
    proposed_solution: str
    wedge: str
    biggest_unknown: str
    proof_needed: str
    rejected_directions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ThesisCanvasUpdate(BaseModel):
    current_thesis: str | None = Field(default=None, min_length=1, max_length=10000)
    target_user: str | None = Field(default=None, max_length=5000)
    problem: str | None = Field(default=None, max_length=5000)
    current_workaround: str | None = Field(default=None, max_length=5000)
    proposed_solution: str | None = Field(default=None, max_length=5000)
    wedge: str | None = Field(default=None, max_length=5000)
    biggest_unknown: str | None = Field(default=None, max_length=5000)
    proof_needed: str | None = Field(default=None, max_length=5000)
    rejected_directions: list[str] | None = Field(default=None, max_length=20)
    open_questions: list[str] | None = Field(default=None, max_length=20)
    change_reason: str | None = Field(default=None, max_length=5000)


class ThesisEvolutionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    event_type: ThesisEvolutionEventType
    title: str
    change_summary: str
    reason: str
    source_entity_type: str | None
    source_entity_id: uuid.UUID | None
    origin: ThesisEvolutionOrigin
    created_at: datetime


class ThesisCanvasDetailRead(BaseModel):
    canvas: ThesisCanvasRead
    evolution: list[ThesisEvolutionEventRead] = Field(default_factory=list)


class IdeaStoryRead(BaseModel):
    project_id: uuid.UUID
    original_idea: str
    current_thesis: str
    selected_wedge: str
    rejected_directions: list[str] = Field(default_factory=list)
    why_it_changed: str
    current_blocker: str
    next_proof: str
    latest_change_title: str | None = None
    latest_change_reason: str | None = None
