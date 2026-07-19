from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    app_name: str = "Thesys API"
    environment: str = Field(
        default="local",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    secret_provider: Literal["environment", "vault", "cloud"] = Field(
        default="environment",
        validation_alias="SECRET_PROVIDER",
    )
    vault_address: str | None = Field(default=None, validation_alias="VAULT_ADDRESS")
    vault_mount_point: str = Field(default="secret", validation_alias="VAULT_MOUNT_POINT")
    vault_secret_path_prefix: str = Field(
        default="thesys",
        validation_alias="VAULT_SECRET_PATH_PREFIX",
    )
    cloud_secret_region: str | None = Field(
        default=None,
        validation_alias="CLOUD_SECRET_REGION",
    )
    cloud_secret_id_prefix: str = Field(
        default="thesys/",
        validation_alias="CLOUD_SECRET_ID_PREFIX",
    )
    encryption_key_current_version: str = Field(
        default="v1",
        validation_alias="ENCRYPTION_KEY_CURRENT_VERSION",
    )
    encryption_key_secret_prefix: str = Field(
        default="THESYS_ENCRYPTION_KEK",
        validation_alias="ENCRYPTION_KEY_SECRET_PREFIX",
    )
    auth_mode: Literal["dev", "jwt", "api_key", "oidc"] = Field(
        default="dev",
        validation_alias="AUTH_MODE",
    )
    dev_auth_default_email: str = Field(
        default="dev@thesys.local",
        validation_alias="DEV_AUTH_DEFAULT_EMAIL",
    )
    dev_auth_default_name: str = Field(default="Dev User", validation_alias="DEV_AUTH_DEFAULT_NAME")
    auth_jwt_secret: str | None = Field(
        default=None,
        validation_alias="AUTH_JWT_SECRET",
        repr=False,
    )
    auth_jwt_issuer: str | None = Field(default=None, validation_alias="AUTH_JWT_ISSUER")
    auth_jwt_audience: str | None = Field(default=None, validation_alias="AUTH_JWT_AUDIENCE")
    auth_jwt_allowed_key_ids: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias="AUTH_JWT_ALLOWED_KEY_IDS",
    )
    auth_jwt_revoked_ids: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias="AUTH_JWT_REVOKED_IDS",
    )
    auth_api_key_hashes: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias="AUTH_API_KEY_HASHES",
    )
    auth_revoked_api_key_hashes: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias="AUTH_REVOKED_API_KEY_HASHES",
    )
    auth_service_account_email: str = Field(
        default="service-account@thesys.local",
        validation_alias="AUTH_SERVICE_ACCOUNT_EMAIL",
    )
    auth_service_account_workspace: str = Field(
        default="Thesys Service Workspace",
        validation_alias="AUTH_SERVICE_ACCOUNT_WORKSPACE",
    )
    auth_service_account_role: Literal["owner", "admin", "editor", "viewer"] = Field(
        default="admin",
        validation_alias="AUTH_SERVICE_ACCOUNT_ROLE",
    )
    oidc_issuer: str | None = Field(default=None, validation_alias="OIDC_ISSUER")
    oidc_audience: str | None = Field(default=None, validation_alias="OIDC_AUDIENCE")
    oidc_jwks_url: str | None = Field(default=None, validation_alias="OIDC_JWKS_URL")
    oidc_required_algorithms: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["RS256"],
        validation_alias="OIDC_REQUIRED_ALGORITHMS",
    )
    oidc_authorized_party: str | None = Field(
        default=None,
        validation_alias="OIDC_AUTHORIZED_PARTY",
    )
    oidc_jwks_cache_seconds: int = Field(
        default=300,
        ge=60,
        le=86_400,
        validation_alias="OIDC_JWKS_CACHE_SECONDS",
    )
    oidc_jwks_timeout_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        validation_alias="OIDC_JWKS_TIMEOUT_SECONDS",
    )

    database_url: str = Field(
        default="postgresql+psycopg://thesys_api:thesys-api-local@localhost:5432/thesys",
        validation_alias="DATABASE_URL",
    )
    migration_database_url: str | None = Field(
        default=None,
        validation_alias="MIGRATION_DATABASE_URL",
    )
    database_runtime_role: Literal["api", "worker", "readonly"] = Field(
        default="api",
        validation_alias="DATABASE_RUNTIME_ROLE",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    litellm_base_url: str = Field(
        default="http://localhost:4000",
        validation_alias="LITELLM_BASE_URL",
    )
    litellm_api_key: str = Field(
        default="sk-local-dev",
        validation_alias="LITELLM_API_KEY",
        repr=False,
    )
    litellm_model: str = Field(default="dev-gpt-4o-mini", validation_alias="LITELLM_MODEL")
    litellm_timeout_seconds: float = Field(default=60.0, validation_alias="LITELLM_TIMEOUT_SECONDS")
    guide_chat_stream_timeout_seconds: float = Field(
        default=75.0,
        ge=1.0,
        le=300.0,
        validation_alias="GUIDE_CHAT_STREAM_TIMEOUT_SECONDS",
    )
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
    guardrail_attack_detector: Literal[
        "deterministic",
        "prompt_guard",
        "nemo_guardrails",
        "llama_guard",
    ] = Field(
        default="deterministic",
        validation_alias="GUARDRAIL_ATTACK_DETECTOR",
    )
    ai_workflow_max_tokens: int = Field(
        default=100_000,
        ge=1_000,
        validation_alias="AI_WORKFLOW_MAX_TOKENS",
    )
    ai_workflow_max_cost_usd: float = Field(
        default=10.0,
        ge=0.0,
        validation_alias="AI_WORKFLOW_MAX_COST_USD",
    )
    ai_provider_failure_circuit_threshold: int = Field(
        default=5,
        ge=1,
        le=100,
        validation_alias="AI_PROVIDER_FAILURE_CIRCUIT_THRESHOLD",
    )
    ai_workflow_budget_preflight_enabled: bool = Field(
        default=True,
        validation_alias="AI_WORKFLOW_BUDGET_PREFLIGHT_ENABLED",
    )
    ai_workflow_default_estimated_tokens: int = Field(
        default=4_000,
        ge=1,
        le=100_000,
        validation_alias="AI_WORKFLOW_DEFAULT_ESTIMATED_TOKENS",
    )
    ai_workflow_default_estimated_cost_usd: float = Field(
        default=0.05,
        ge=0.0,
        validation_alias="AI_WORKFLOW_DEFAULT_ESTIMATED_COST_USD",
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        repr=False,
    )
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
        repr=False,
    )
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
        repr=False,
    )

    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        validation_alias="S3_ENDPOINT_URL",
    )
    s3_access_key_id: str = Field(
        default="minioadmin",
        validation_alias="S3_ACCESS_KEY_ID",
        repr=False,
    )
    s3_secret_access_key: str = Field(
        default="minioadmin",
        validation_alias="S3_SECRET_ACCESS_KEY",
        repr=False,
    )
    s3_bucket: str = Field(default="thesys-local", validation_alias="S3_BUCKET")
    s3_auto_create_bucket: bool = Field(
        default=False,
        validation_alias="S3_AUTO_CREATE_BUCKET",
    )
    s3_verify_bucket_security: bool = Field(
        default=False,
        validation_alias="S3_VERIFY_BUCKET_SECURITY",
    )
    s3_server_side_encryption: Literal["AES256", "aws:kms"] = Field(
        default="AES256",
        validation_alias="S3_SERVER_SIDE_ENCRYPTION",
    )
    s3_kms_key_id: str | None = Field(default=None, validation_alias="S3_KMS_KEY_ID")
    s3_presigned_url_ttl_seconds: int = Field(
        default=300,
        ge=30,
        le=900,
        validation_alias="S3_PRESIGNED_URL_TTL_SECONDS",
    )
    s3_retention_days: int = Field(
        default=30,
        ge=1,
        le=3650,
        validation_alias="S3_RETENTION_DAYS",
    )
    retention_sanitized_text_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        validation_alias="RETENTION_SANITIZED_TEXT_DAYS",
    )
    retention_embedding_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        validation_alias="RETENTION_EMBEDDING_DAYS",
    )
    retention_pii_token_map_days: int = Field(
        default=30,
        ge=1,
        le=3650,
        validation_alias="RETENTION_PII_TOKEN_MAP_DAYS",
    )
    retention_model_prompt_days: int = Field(
        default=14,
        ge=1,
        le=3650,
        validation_alias="RETENTION_MODEL_PROMPT_DAYS",
    )
    retention_model_output_days: int = Field(
        default=30,
        ge=1,
        le=3650,
        validation_alias="RETENTION_MODEL_OUTPUT_DAYS",
    )
    retention_langsmith_trace_days: int = Field(
        default=14,
        ge=1,
        le=3650,
        validation_alias="RETENTION_LANGSMITH_TRACE_DAYS",
    )
    retention_audit_event_days: int = Field(
        default=365,
        ge=1,
        le=3650,
        validation_alias="RETENTION_AUDIT_EVENT_DAYS",
    )
    retention_security_event_days: int = Field(
        default=730,
        ge=1,
        le=3650,
        validation_alias="RETENTION_SECURITY_EVENT_DAYS",
    )
    retention_temporal_history_days: int = Field(
        default=30,
        ge=1,
        le=3650,
        validation_alias="RETENTION_TEMPORAL_HISTORY_DAYS",
    )
    object_storage_mode: Literal["local", "s3"] = Field(
        default="local",
        validation_alias="OBJECT_STORAGE_MODE",
    )
    local_object_storage_path: str = Field(
        default="/tmp/thesys-object-storage",
        validation_alias="LOCAL_OBJECT_STORAGE_PATH",
    )
    max_upload_mb: int = Field(default=10, validation_alias="MAX_UPLOAD_MB")
    malware_scanner_mode: Literal["clamav", "deterministic", "disabled"] = Field(
        default="clamav",
        validation_alias="MALWARE_SCANNER_MODE",
    )
    malware_scanner_host: str = Field(default="clamav", validation_alias="MALWARE_SCANNER_HOST")
    malware_scanner_port: int = Field(
        default=3310,
        ge=1,
        le=65535,
        validation_alias="MALWARE_SCANNER_PORT",
    )
    malware_scanner_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        le=60,
        validation_alias="MALWARE_SCANNER_TIMEOUT_SECONDS",
    )
    url_fetch_timeout_seconds: float = Field(
        default=15.0,
        validation_alias="URL_FETCH_TIMEOUT_SECONDS",
    )
    url_fetch_max_bytes: int = Field(
        default=2_000_000,
        ge=10_000,
        le=20_000_000,
        validation_alias="URL_FETCH_MAX_BYTES",
    )
    url_fetch_max_redirects: int = Field(
        default=5,
        ge=0,
        le=10,
        validation_alias="URL_FETCH_MAX_REDIRECTS",
    )
    url_fetch_allowed_ports: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: [80, 443],
        validation_alias="URL_FETCH_ALLOWED_PORTS",
    )
    url_fetch_allowed_domains: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias="URL_FETCH_ALLOWED_DOMAINS",
    )
    url_fetch_denied_domains: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias="URL_FETCH_DENIED_DOMAINS",
    )
    url_fetch_allowed_content_types: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "text/html",
            "text/plain",
            "text/markdown",
            "application/pdf",
            "application/xhtml+xml",
        ],
        validation_alias="URL_FETCH_ALLOWED_CONTENT_TYPES",
    )
    max_extracted_text_chars: int = Field(
        default=200_000,
        ge=1_000,
        le=2_000_000,
        validation_alias="MAX_EXTRACTED_TEXT_CHARS",
    )
    max_pdf_pages: int = Field(
        default=200,
        ge=1,
        le=10_000,
        validation_alias="MAX_PDF_PAGES",
    )
    pdf_extraction_timeout_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=120.0,
        validation_alias="PDF_EXTRACTION_TIMEOUT_SECONDS",
    )
    pdf_extraction_memory_mb: int = Field(
        default=256,
        ge=64,
        le=4096,
        validation_alias="PDF_EXTRACTION_MEMORY_MB",
    )
    max_pdf_decompression_ratio: float = Field(
        default=100.0,
        ge=1.0,
        le=1000.0,
        validation_alias="MAX_PDF_DECOMPRESSION_RATIO",
    )
    max_image_pixels: int = Field(
        default=20_000_000,
        ge=1_000,
        le=100_000_000,
        validation_alias="MAX_IMAGE_PIXELS",
    )
    max_image_decoded_bytes: int = Field(
        default=80_000_000,
        ge=1_000_000,
        le=500_000_000,
        validation_alias="MAX_IMAGE_DECODED_BYTES",
    )
    max_image_decompression_ratio: float = Field(
        default=100.0,
        ge=1.0,
        le=1000.0,
        validation_alias="MAX_IMAGE_DECOMPRESSION_RATIO",
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
    ai_embedding_cache_enabled: bool = Field(
        default=True,
        validation_alias="AI_EMBEDDING_CACHE_ENABLED",
    )
    ai_retrieval_cache_enabled: bool = Field(
        default=True,
        validation_alias="AI_RETRIEVAL_CACHE_ENABLED",
    )
    ai_rerank_cache_enabled: bool = Field(
        default=True,
        validation_alias="AI_RERANK_CACHE_ENABLED",
    )
    ai_semantic_answer_cache_enabled: bool = Field(
        default=False,
        validation_alias="AI_SEMANTIC_ANSWER_CACHE_ENABLED",
    )
    ai_semantic_answer_cache_live_enabled: bool = Field(
        default=False,
        validation_alias="AI_SEMANTIC_ANSWER_CACHE_LIVE_ENABLED",
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
    retrieval_reranker_provider: Literal["none", "deterministic", "litellm"] = Field(
        default="deterministic",
        validation_alias="RETRIEVAL_RERANKER_PROVIDER",
    )
    retrieval_text_search_enabled: bool = Field(
        default=True,
        validation_alias="RETRIEVAL_TEXT_SEARCH_ENABLED",
    )
    retrieval_text_search_weight: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        validation_alias="RETRIEVAL_TEXT_SEARCH_WEIGHT",
    )
    retrieval_mmr_enabled: bool = Field(
        default=True,
        validation_alias="RETRIEVAL_MMR_ENABLED",
    )
    retrieval_mmr_lambda: float = Field(
        default=0.72,
        ge=0.0,
        le=1.0,
        validation_alias="RETRIEVAL_MMR_LAMBDA",
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
    retrieval_max_chunks_per_domain: int = Field(
        default=3,
        ge=1,
        le=20,
        validation_alias="RETRIEVAL_MAX_CHUNKS_PER_DOMAIN",
    )
    retrieval_max_chunks_per_source_type: int = Field(
        default=5,
        ge=1,
        le=25,
        validation_alias="RETRIEVAL_MAX_CHUNKS_PER_SOURCE_TYPE",
    )
    retrieval_max_chunks_per_competitor: int = Field(
        default=3,
        ge=1,
        le=20,
        validation_alias="RETRIEVAL_MAX_CHUNKS_PER_COMPETITOR",
    )
    retrieval_min_context_score: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        validation_alias="RETRIEVAL_MIN_CONTEXT_SCORE",
    )
    retrieval_min_source_trust_score: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        validation_alias="RETRIEVAL_MIN_SOURCE_TRUST_SCORE",
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
    tavily_api_key: str | None = Field(
        default=None,
        validation_alias="TAVILY_API_KEY",
        repr=False,
    )
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
    langsmith_api_key: str | None = Field(
        default=None,
        validation_alias="LANGSMITH_API_KEY",
        repr=False,
    )
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias="LANGSMITH_ENDPOINT",
    )
    langsmith_project: str = Field(default="thesys-local", validation_alias="LANGSMITH_PROJECT")
    langsmith_public_url_base: str = Field(
        default="https://smith.langchain.com",
        validation_alias="LANGSMITH_PUBLIC_URL_BASE",
    )
    langsmith_provider_retention_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        validation_alias="LANGSMITH_PROVIDER_RETENTION_DAYS",
    )
    provider_egress_policy_enabled: bool = Field(
        default=True,
        validation_alias="PROVIDER_EGRESS_POLICY_ENABLED",
    )
    provider_egress_allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "::1",
            "api.openai.com",
            "api.anthropic.com",
            "generativelanguage.googleapis.com",
            "api.tavily.com",
            "api.smith.langchain.com",
            "smith.langchain.com",
        ],
        validation_alias="PROVIDER_EGRESS_ALLOWED_HOSTS",
    )
    provider_egress_max_response_bytes: int = Field(
        default=5_000_000,
        ge=100_000,
        le=50_000_000,
        validation_alias="PROVIDER_EGRESS_MAX_RESPONSE_BYTES",
    )
    opa_policy_url: str = Field(
        default="http://localhost:8181",
        validation_alias="OPA_POLICY_URL",
    )
    opa_policy_timeout_seconds: float = Field(
        default=2.0,
        ge=0.1,
        le=30.0,
        validation_alias="OPA_POLICY_TIMEOUT_SECONDS",
    )
    opa_policy_enforcement_enabled: bool = Field(
        default=False,
        validation_alias="OPA_POLICY_ENFORCEMENT_ENABLED",
    )
    mcp_server_allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias="MCP_SERVER_ALLOWED_HOSTS",
    )
    disable_all_agent_writes: bool = Field(
        default=False,
        validation_alias="DISABLE_ALL_AGENT_WRITES",
    )
    disable_external_mcp: bool = Field(
        default=False,
        validation_alias="DISABLE_EXTERNAL_MCP",
    )
    disable_external_egress: bool = Field(
        default=False,
        validation_alias="DISABLE_EXTERNAL_EGRESS",
    )
    disable_model_provider: bool = Field(
        default=False,
        validation_alias="DISABLE_MODEL_PROVIDER",
    )
    disable_memory_writes: bool = Field(
        default=False,
        validation_alias="DISABLE_MEMORY_WRITES",
    )
    disable_source_fetching: bool = Field(
        default=False,
        validation_alias="DISABLE_SOURCE_FETCHING",
    )
    security_rate_limit_enabled: bool = Field(
        default=True,
        validation_alias="SECURITY_RATE_LIMIT_ENABLED",
    )
    security_rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        le=86_400,
        validation_alias="SECURITY_RATE_LIMIT_WINDOW_SECONDS",
    )
    security_rate_limit_user_max_requests: int = Field(
        default=120,
        ge=1,
        validation_alias="SECURITY_RATE_LIMIT_USER_MAX_REQUESTS",
    )
    security_rate_limit_workspace_max_requests: int = Field(
        default=1_000,
        ge=1,
        validation_alias="SECURITY_RATE_LIMIT_WORKSPACE_MAX_REQUESTS",
    )
    security_max_concurrent_workflows: int = Field(
        default=8,
        ge=1,
        validation_alias="SECURITY_MAX_CONCURRENT_WORKFLOWS",
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
    retention_cleanup_schedule_enabled: bool = Field(
        default=False,
        validation_alias="RETENTION_CLEANUP_SCHEDULE_ENABLED",
    )
    retention_cleanup_interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        validation_alias="RETENTION_CLEANUP_INTERVAL_HOURS",
    )
    temporal_namespace_retention_reconcile_enabled: bool = Field(
        default=False,
        validation_alias="TEMPORAL_NAMESPACE_RETENTION_RECONCILE_ENABLED",
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

    @field_validator(
        "auth_api_key_hashes",
        "auth_revoked_api_key_hashes",
        "auth_jwt_allowed_key_ids",
        "auth_jwt_revoked_ids",
        "oidc_required_algorithms",
        "url_fetch_allowed_domains",
        "url_fetch_denied_domains",
        "url_fetch_allowed_content_types",
        "provider_egress_allowed_hosts",
        "mcp_server_allowed_hosts",
        mode="before",
    )
    @classmethod
    def parse_csv_list(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("auth_mode", mode="before")
    @classmethod
    def normalize_auth_mode(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("secret_provider", mode="before")
    @classmethod
    def normalize_secret_provider(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        if self.auth_mode == "dev" and self.environment != "local":
            raise ValueError("AUTH_MODE=dev is permitted only when APP_ENV=local.")

        if self.environment == "local" and self.secret_provider != "environment":
            raise ValueError(
                "Local development must use SECRET_PROVIDER=environment."
            )
        if self.environment in {"staging", "production"} and self.secret_provider not in {
            "vault",
            "cloud",
        }:
            raise ValueError(
                "Hosted environments must use SECRET_PROVIDER=vault or cloud."
            )
        if self.secret_provider == "vault" and not (
            self.vault_address and self.vault_address.strip()
        ):
            raise ValueError("SECRET_PROVIDER=vault requires VAULT_ADDRESS.")

        if self.langsmith_tracing and (
            self.langsmith_provider_retention_days != self.retention_langsmith_trace_days
        ):
            raise ValueError(
                "LANGSMITH_PROVIDER_RETENTION_DAYS must match "
                "RETENTION_LANGSMITH_TRACE_DAYS when LANGSMITH_TRACING=true."
            )

        if self.environment in {"staging", "production"}:
            expected_database_user = f"thesys_{self.database_runtime_role}"
            if make_url(self.database_url).username != expected_database_user:
                raise ValueError(
                    "Hosted DATABASE_URL must use the declared scoped runtime role."
                )
            endpoint = urlparse(self.s3_endpoint_url)
            if self.object_storage_mode != "s3":
                raise ValueError("Hosted environments must use OBJECT_STORAGE_MODE=s3.")
            if endpoint.scheme != "https" or not endpoint.netloc:
                raise ValueError("Hosted S3_ENDPOINT_URL must use HTTPS.")
            if endpoint.username or endpoint.password:
                raise ValueError("S3_ENDPOINT_URL must not contain credentials.")
            if self.s3_auto_create_bucket:
                raise ValueError("Hosted application roles must not create S3 buckets.")
            if not self.s3_verify_bucket_security:
                raise ValueError("Hosted S3 bucket security verification is required.")
            if self.malware_scanner_mode != "clamav":
                raise ValueError("Hosted environments must use MALWARE_SCANNER_MODE=clamav.")
            if not self.malware_scanner_host.strip():
                raise ValueError("MALWARE_SCANNER_HOST is required for hosted environments.")
            self.auth_jwt_secret = None
            self.litellm_api_key = ""
            self.openai_api_key = None
            self.anthropic_api_key = None
            self.gemini_api_key = None
            self.s3_access_key_id = ""
            self.s3_secret_access_key = ""
            self.tavily_api_key = None
            self.langsmith_api_key = None

        if self.auth_mode != "oidc":
            return self

        required = {
            "OIDC_ISSUER": self.oidc_issuer,
            "OIDC_AUDIENCE": self.oidc_audience,
            "OIDC_JWKS_URL": self.oidc_jwks_url,
        }
        missing = [name for name, value in required.items() if not value or not value.strip()]
        if missing:
            raise ValueError(f"AUTH_MODE=oidc requires {', '.join(missing)}.")

        allowed_asymmetric_algorithms = {
            "RS256",
            "RS384",
            "RS512",
            "ES256",
            "ES384",
            "ES512",
        }
        configured_algorithms = set(self.oidc_required_algorithms)
        if not configured_algorithms or not configured_algorithms <= allowed_asymmetric_algorithms:
            raise ValueError(
                "OIDC_REQUIRED_ALGORITHMS must contain only approved asymmetric algorithms."
            )
        return self

    @field_validator("url_fetch_allowed_ports", mode="before")
    @classmethod
    def parse_csv_int_list(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @property
    def should_use_llm_stub(self) -> bool:
        if self.llm_stub_mode == "always":
            return True
        if self.llm_stub_mode == "never":
            return False
        if self.secret_provider != "environment":
            return False
        provider_keys = [self.openai_api_key, self.anthropic_api_key, self.gemini_api_key]
        return not any(key for key in provider_keys if key and key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
