import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AIStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "waiting_for_human"]


class AIRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    workflow_type: str
    status: AIStatus
    model_provider: str | None
    model_name: str | None
    prompt_version: str | None
    input_summary: str | None
    output_summary: str | None
    total_tokens: int | None
    total_cost: Decimal | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class AIStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ai_run_id: uuid.UUID
    step_name: str
    status: str
    latency_ms: int | None
    tokens: int | None
    cost: Decimal | None
    error: str | None
    created_at: datetime


class StructuredOutputTestCreate(BaseModel):
    idea: str = Field(min_length=1, max_length=5000)
    project_id: uuid.UUID | None = None


class StructuredOutputSmokeResult(BaseModel):
    summary: str
    target_users: list[str]
    key_uncertainties: list[str]
    recommended_next_step: str
    confidence: Literal["low", "medium", "high"]


class StructuredOutputTestRead(BaseModel):
    ai_run_id: uuid.UUID
    ai_step_id: uuid.UUID
    prompt_version: str
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None
    output: StructuredOutputSmokeResult


class AIProviderKeyStatus(BaseModel):
    openai: bool
    anthropic: bool
    gemini: bool
    any_present: bool


class LiteLLMReachabilityStatus(BaseModel):
    base_url: str
    endpoint: str
    reachable: bool
    status_code: int | None
    error: str | None


class AIStatusStructuredOutputCheck(BaseModel):
    ok: bool
    used_stub: bool | None
    model_provider: str | None
    model_name: str | None
    total_tokens: int | None
    total_cost: Decimal | None
    error: str | None


class AIStatusRead(BaseModel):
    llm_stub_mode: Literal["auto", "always", "never"]
    llm_fallback_policy: Literal["disabled", "emergency", "always"]
    llm_structured_output_repair_attempts: int
    resolved_mode: Literal["stub", "live"]
    should_use_stub: bool
    litellm_model: str
    litellm_base_url: str
    litellm_reachability: LiteLLMReachabilityStatus
    provider_keys: AIProviderKeyStatus
    embedding_provider: Literal["deterministic", "litellm"]
    embedding_model: str
    embedding_dimension: int
    embedding_version: str
    embedding_timeout_seconds: float
    embedding_retry_attempts: int
    retrieval_vector_path: Literal["auto", "sql", "python"]
    retrieval_python_fallback_enabled: bool
    retrieval_reranking_enabled: bool
    retrieval_reranker_provider: Literal["deterministic", "litellm"]
    retrieval_context_token_budget: int
    retrieval_max_chunks_per_source: int
    retrieval_min_context_score: float
    structured_output_healthcheck: AIStatusStructuredOutputCheck | None = None
