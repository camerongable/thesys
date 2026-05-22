import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

EvidenceSourceType = Literal["url", "file", "note", "transcript", "manual"]
EvidenceIngestionStatus = Literal["pending", "processing", "ready", "failed"]
RetrievalMode = Literal["semantic", "keyword", "hybrid"]


class EvidenceSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source_type: EvidenceSourceType
    title: str | None
    url: str | None
    object_storage_key: str | None
    summary: str | None
    source_date: datetime | None
    ingested_at: datetime | None
    classification: str | None
    credibility_score: Decimal | None
    ingestion_status: EvidenceIngestionStatus
    ingestion_error: str | None
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0
    text_preview: str | None = None


class EvidenceSourceListRead(BaseModel):
    sources: list[EvidenceSourceRead]


class EvidenceUrlCreate(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, min_length=1, max_length=500)


class EvidenceNoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=100_000)
    source_type: Literal["note", "transcript", "manual"] = "note"
    source_date: datetime | None = None


class EvidenceRetrieveCreate(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: RetrievalMode = "hybrid"
    top_k: int = Field(default=8, ge=1, le=25)
    source_types: list[EvidenceSourceType] = Field(default_factory=list, max_length=5)
    competitor_id: uuid.UUID | None = None
    assumption_id: uuid.UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    freshness_days: int | None = Field(default=None, ge=1, le=3650)


class EvidenceChunkRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int | None
    metadata: dict[str, object]


class EvidenceRetrievalResultRead(BaseModel):
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str | None
    url: str | None
    source_type: EvidenceSourceType
    chunk_index: int
    text: str
    score: float
    semantic_score: float
    keyword_score: float
    metadata: dict[str, object]
    created_at: datetime


class EvidenceRetrieveRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    mode: RetrievalMode
    query: str
    results: list[EvidenceRetrievalResultRead]
