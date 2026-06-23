from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Thesys API"
    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    auth_mode: str = Field(default="dev", validation_alias="AUTH_MODE")
    dev_auth_default_email: str = Field(
        default="dev@thesys.local",
        validation_alias="DEV_AUTH_DEFAULT_EMAIL",
    )
    dev_auth_default_name: str = Field(default="Dev User", validation_alias="DEV_AUTH_DEFAULT_NAME")

    database_url: str = Field(
        default="postgresql+psycopg://thesys:thesys@localhost:5432/thesys",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    litellm_base_url: str = Field(
        default="http://localhost:4000",
        validation_alias="LITELLM_BASE_URL",
    )
    litellm_api_key: str = Field(default="sk-local-dev", validation_alias="LITELLM_API_KEY")
    litellm_model: str = Field(default="dev-gpt-4o-mini", validation_alias="LITELLM_MODEL")
    litellm_timeout_seconds: float = Field(default=60.0, validation_alias="LITELLM_TIMEOUT_SECONDS")
    llm_stub_mode: Literal["auto", "always", "never"] = Field(
        default="auto",
        validation_alias="LLM_STUB_MODE",
    )
    llm_structured_output_repair_attempts: int = Field(
        default=1,
        ge=0,
        le=5,
        validation_alias="LLM_STRUCTURED_OUTPUT_REPAIR_ATTEMPTS",
    )
    llm_fallback_policy: Literal["disabled", "emergency", "always"] = Field(
        default="emergency",
        validation_alias="LLM_FALLBACK_POLICY",
    )
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")

    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        validation_alias="S3_ENDPOINT_URL",
    )
    s3_access_key_id: str = Field(default="minioadmin", validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="minioadmin", validation_alias="S3_SECRET_ACCESS_KEY")
    s3_bucket: str = Field(default="thesys-local", validation_alias="S3_BUCKET")
    object_storage_mode: Literal["local", "s3"] = Field(
        default="local",
        validation_alias="OBJECT_STORAGE_MODE",
    )
    local_object_storage_path: str = Field(
        default="/tmp/thesys-object-storage",
        validation_alias="LOCAL_OBJECT_STORAGE_PATH",
    )
    max_upload_mb: int = Field(default=10, validation_alias="MAX_UPLOAD_MB")
    url_fetch_timeout_seconds: float = Field(
        default=15.0,
        validation_alias="URL_FETCH_TIMEOUT_SECONDS",
    )
    embedding_model: str = Field(
        default="deterministic-hash-embedding-1536",
        validation_alias="EMBEDDING_MODEL",
    )
    embedding_dimension: int = Field(default=1536, validation_alias="EMBEDDING_DIMENSION")
    embedding_provider: Literal["deterministic", "litellm"] = Field(
        default="deterministic",
        validation_alias="EMBEDDING_PROVIDER",
    )
    embedding_version: str = Field(default="v1", validation_alias="EMBEDDING_VERSION")
    embedding_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="EMBEDDING_TIMEOUT_SECONDS",
    )
    embedding_retry_attempts: int = Field(
        default=1,
        ge=0,
        le=5,
        validation_alias="EMBEDDING_RETRY_ATTEMPTS",
    )
    retrieval_vector_path: Literal["auto", "sql", "python"] = Field(
        default="auto",
        validation_alias="RETRIEVAL_VECTOR_PATH",
    )
    retrieval_python_fallback_enabled: bool = Field(
        default=True,
        validation_alias="RETRIEVAL_PYTHON_FALLBACK_ENABLED",
    )
    retrieval_reranking_enabled: bool = Field(
        default=True,
        validation_alias="RETRIEVAL_RERANKING_ENABLED",
    )
    retrieval_reranker_provider: Literal["deterministic", "litellm"] = Field(
        default="deterministic",
        validation_alias="RETRIEVAL_RERANKER_PROVIDER",
    )
    retrieval_context_token_budget: int = Field(
        default=3500,
        ge=500,
        le=20000,
        validation_alias="RETRIEVAL_CONTEXT_TOKEN_BUDGET",
    )
    retrieval_max_chunks_per_source: int = Field(
        default=2,
        ge=1,
        le=10,
        validation_alias="RETRIEVAL_MAX_CHUNKS_PER_SOURCE",
    )
    retrieval_min_context_score: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        validation_alias="RETRIEVAL_MIN_CONTEXT_SCORE",
    )
    external_search_enabled: bool = Field(
        default=False,
        validation_alias="EXTERNAL_SEARCH_ENABLED",
    )
    external_search_provider: Literal["deterministic", "tavily"] = Field(
        default="deterministic",
        validation_alias="EXTERNAL_SEARCH_PROVIDER",
    )
    external_search_max_results_per_query: int = Field(
        default=5,
        ge=1,
        le=10,
        validation_alias="EXTERNAL_SEARCH_MAX_RESULTS_PER_QUERY",
    )
    external_search_max_queries_per_sprint: int = Field(
        default=6,
        ge=1,
        le=20,
        validation_alias="EXTERNAL_SEARCH_MAX_QUERIES_PER_SPRINT",
    )
    external_search_timeout_seconds: float = Field(
        default=20.0,
        ge=1.0,
        le=120.0,
        validation_alias="EXTERNAL_SEARCH_TIMEOUT_SECONDS",
    )
    tavily_api_key: str | None = Field(default=None, validation_alias="TAVILY_API_KEY")
    multimodal_extraction_provider: Literal["deterministic", "litellm"] = Field(
        default="deterministic",
        validation_alias="MULTIMODAL_EXTRACTION_PROVIDER",
    )
    multimodal_extraction_model: str = Field(
        default="dev-gpt-4o-mini",
        validation_alias="MULTIMODAL_EXTRACTION_MODEL",
    )
    multimodal_extraction_timeout_seconds: float = Field(
        default=90.0,
        ge=5.0,
        le=300.0,
        validation_alias="MULTIMODAL_EXTRACTION_TIMEOUT_SECONDS",
    )
    multimodal_pdf_fallback_enabled: bool = Field(
        default=False,
        validation_alias="MULTIMODAL_PDF_FALLBACK_ENABLED",
    )
    multimodal_pdf_min_text_chars: int = Field(
        default=80,
        ge=0,
        le=5000,
        validation_alias="MULTIMODAL_PDF_MIN_TEXT_CHARS",
    )
    langsmith_tracing: bool = Field(default=False, validation_alias="LANGSMITH_TRACING")
    langsmith_api_key: str | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias="LANGSMITH_ENDPOINT",
    )
    langsmith_project: str = Field(default="thesys-local", validation_alias="LANGSMITH_PROJECT")
    langsmith_public_url_base: str = Field(
        default="https://smith.langchain.com",
        validation_alias="LANGSMITH_PUBLIC_URL_BASE",
    )
    temporal_enabled: bool = Field(default=False, validation_alias="TEMPORAL_ENABLED")
    temporal_address: str = Field(default="localhost:7233", validation_alias="TEMPORAL_ADDRESS")
    temporal_namespace: str = Field(default="default", validation_alias="TEMPORAL_NAMESPACE")
    temporal_task_queue: str = Field(
        default="thesys-research-sprints",
        validation_alias="TEMPORAL_TASK_QUEUE",
    )
    temporal_workflow_timeout_seconds: int = Field(
        default=3600,
        ge=60,
        validation_alias="TEMPORAL_WORKFLOW_TIMEOUT_SECONDS",
    )

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def should_use_llm_stub(self) -> bool:
        if self.llm_stub_mode == "always":
            return True
        if self.llm_stub_mode == "never":
            return False
        provider_keys = [self.openai_api_key, self.anthropic_api_key, self.gemini_api_key]
        return not any(key for key in provider_keys if key and key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
