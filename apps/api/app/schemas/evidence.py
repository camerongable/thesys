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
    metadata: dict[str, object] = Field(default_factory=dict)
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
    research_sprint_id: uuid.UUID | None = None
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
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    embedding_version: str | None = None
    embedded_at: datetime | None = None
    rerank_score: float | None = None
    final_rank: int | None = None
    context_included: bool = True
    selection_reason: str | None = None
    created_at: datetime


class RetrievalQueryPlanRead(BaseModel):
    intent: str
    target_entities: list[str] = Field(default_factory=list)
    needed_evidence_types: list[str] = Field(default_factory=list)
    subqueries: list[str] = Field(default_factory=list)
    decomposed: bool = False


class RetrievalRerankerDiagnosticsRead(BaseModel):
    enabled: bool
    provider: str
    fallback_used: bool = False
    fallback_reason: str | None = None


class RetrievalContextDiagnosticsRead(BaseModel):
    token_budget: int
    token_count: int
    selected_count: int
    dropped_count: int
    deduped_count: int
    max_chunks_per_source: int
    min_context_score: float


class RetrievalQualityReportRead(BaseModel):
    recall_proxy: float
    precision_proxy: float
    citation_coverage_proxy: float
    unsupported_claim_count: int
    average_retrieval_latency_ms: int
    reranker_used: bool
    context_token_count: int


class RetrievalDiagnosticsRead(BaseModel):
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_version: str
    index_name: str | None
    index_available: bool
    candidate_count: int
    query_latency_ms: int
    used_sql_vector_search: bool
    fallback_path_used: bool
    fallback_reason: str | None
    query_plan: RetrievalQueryPlanRead | None = None
    reranker: RetrievalRerankerDiagnosticsRead | None = None
    context: RetrievalContextDiagnosticsRead | None = None
    quality_report: RetrievalQualityReportRead | None = None


class EvidenceRetrieveRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    mode: RetrievalMode
    query: str
    diagnostics: RetrievalDiagnosticsRead
    results: list[EvidenceRetrievalResultRead]


class ReembedEvidenceCreate(BaseModel):
    dry_run: bool = True
    force: bool = False
    scope: Literal["project", "workspace"] = "project"


class ReembedFailureRead(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    error: str


class ReembedEvidenceRead(BaseModel):
    dry_run: bool
    scope: Literal["project", "workspace"]
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_version: str
    scanned_count: int
    eligible_count: int
    skipped_count: int
    reembedded_count: int
    failed_count: int
    failures: list[ReembedFailureRead]
