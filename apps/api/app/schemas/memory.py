import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryType = Literal["working", "episodic", "semantic", "project", "procedural", "preference"]
MemoryStatus = Literal["active", "stale", "archived", "superseded", "proposed"]
MemoryWritePolicy = Literal["direct", "approval_required", "derived_read_only", "transient"]


class ProjectMemoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    memory_type: MemoryType
    status: MemoryStatus
    write_policy: MemoryWritePolicy
    entity_type: str | None
    entity_id: uuid.UUID | None
    source_entity_type: str | None
    source_entity_id: uuid.UUID | None
    title: str
    summary: str
    content: dict[str, Any]
    provenance_metadata: dict[str, Any]
    confidence_score: Decimal | None
    expires_at: datetime | None
    superseded_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ProjectMemoryListRead(BaseModel):
    memory_items: list[ProjectMemoryItemRead] = Field(default_factory=list)


class ProjectMemoryExplainRead(BaseModel):
    memory_item: ProjectMemoryItemRead
    explanation: str
    provenance: dict[str, Any]


class MemorySelectionExcludedRead(BaseModel):
    id: uuid.UUID
    memory_type: MemoryType
    status: MemoryStatus
    title: str
    reason: str


class MemoryConflictRead(BaseModel):
    conflict_group_id: str
    reason: str
    memory_item_ids: list[uuid.UUID] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)


class ProjectMemoryInspectRead(BaseModel):
    workflow_type: str
    selected_memory: list[ProjectMemoryItemRead] = Field(default_factory=list)
    excluded_memory: list[MemorySelectionExcludedRead] = Field(default_factory=list)
    proposed_memory: list[ProjectMemoryItemRead] = Field(default_factory=list)
    conflicts: list[MemoryConflictRead] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)


class ProjectMemoryPreferenceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=2000)
    content: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="user_preference", max_length=120)


class ProjectMemoryCompactionCreate(BaseModel):
    workflow_type: str = Field(default="guide_chat", max_length=120)
    memory_type: MemoryType = "semantic"
    title: str | None = Field(default=None, max_length=255)
    source_memory_ids: list[uuid.UUID] = Field(default_factory=list)


class ProjectMemoryConflictResolveCreate(BaseModel):
    keeper_id: uuid.UUID
    supersede_ids: list[uuid.UUID] = Field(default_factory=list)
    archive_ids: list[uuid.UUID] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=1000)
