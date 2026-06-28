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
