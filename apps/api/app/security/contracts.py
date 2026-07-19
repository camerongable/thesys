"""Security classifications and invariants that later hardening sprints enforce."""

from dataclasses import dataclass
from enum import StrEnum


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ProviderPolicy(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    APPROVED_PROVIDER = "approved_provider"
    APPROVED_RESTRICTED_PROVIDER = "approved_restricted_provider"
    LOCAL_ONLY = "local_only"


@dataclass(frozen=True)
class ClassifiedDataType:
    name: str
    classification: DataClassification
    provider_policy: ProviderPolicy
    owner: str


DATA_TYPES: dict[str, ClassifiedDataType] = {
    "public_web_source": ClassifiedDataType(
        "Public web source",
        DataClassification.PUBLIC,
        ProviderPolicy.APPROVED_PROVIDER,
        "EvidenceService",
    ),
    "project_name": ClassifiedDataType(
        "Project name or general concept",
        DataClassification.INTERNAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "ProjectService",
    ),
    "user_identity": ClassifiedDataType(
        "User identity",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "IdentityService",
    ),
    "workspace_membership": ClassifiedDataType(
        "Workspace membership",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "IdentityService",
    ),
    "business_plan": ClassifiedDataType(
        "User-entered business plan or thesis",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "ProjectService",
    ),
    "uploaded_file": ClassifiedDataType(
        "Uploaded file",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "EvidenceService",
    ),
    "raw_extracted_text": ClassifiedDataType(
        "Raw extracted text",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "EvidenceService",
    ),
    "sanitized_searchable_text": ClassifiedDataType(
        "Sanitized searchable text",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "RetrievalService",
    ),
    "interview_notes_with_identifiers": ClassifiedDataType(
        "Interview notes containing names, emails, or contact details",
        DataClassification.RESTRICTED,
        ProviderPolicy.APPROVED_RESTRICTED_PROVIDER,
        "EvidenceService",
    ),
    "embeddings": ClassifiedDataType(
        "Embeddings derived from project text",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "EmbeddingService",
    ),
    "project_memory": ClassifiedDataType(
        "Durable project memory",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "MemoryService",
    ),
    "research_results": ClassifiedDataType(
        "Research results and memos",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "ResearchSprintService",
    ),
    "validation_results": ClassifiedDataType(
        "Validation results",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "ValidationService",
    ),
    "decision_records": ClassifiedDataType(
        "Decision records",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "ValidationService",
    ),
    "api_credentials": ClassifiedDataType(
        "API credentials",
        DataClassification.RESTRICTED,
        ProviderPolicy.LOCAL_ONLY,
        "PlatformSecurity",
    ),
    "oauth_credentials": ClassifiedDataType(
        "OAuth credentials and refresh tokens",
        DataClassification.RESTRICTED,
        ProviderPolicy.LOCAL_ONLY,
        "PlatformSecurity",
    ),
    "workspace_data_key": ClassifiedDataType(
        "Wrapped per-workspace data-encryption key",
        DataClassification.RESTRICTED,
        ProviderPolicy.LOCAL_ONLY,
        "PlatformSecurity",
    ),
    "pii_token_mapping": ClassifiedDataType(
        "Encrypted project-local mapping from a PII token to its original identifier",
        DataClassification.RESTRICTED,
        ProviderPolicy.LOCAL_ONLY,
        "PseudonymizationService",
    ),
    "system_prompts": ClassifiedDataType(
        "System prompts",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "AISafetyGateway",
    ),
    "tool_schemas": ClassifiedDataType(
        "Tool schemas",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "ToolPolicyGateway",
    ),
    "mcp_server_registrations": ClassifiedDataType(
        "MCP server registrations",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "ToolPolicyGateway",
    ),
    "mcp_server_credentials": ClassifiedDataType(
        "Encrypted, per-server MCP OAuth credentials",
        DataClassification.RESTRICTED,
        ProviderPolicy.LOCAL_ONLY,
        "ToolPolicyGateway",
    ),
    "mcp_oauth_authorization_transactions": ClassifiedDataType(
        "Encrypted single-use MCP OAuth PKCE transactions",
        DataClassification.RESTRICTED,
        ProviderPolicy.LOCAL_ONLY,
        "ToolPolicyGateway",
    ),
    "workspace_kill_switch_states": ClassifiedDataType(
        "Workspace emergency kill-switch state",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "PlatformSecurity",
    ),
    "audit_events": ClassifiedDataType(
        "Audit events",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "GovernanceService",
    ),
    "security_events": ClassifiedDataType(
        "Normalized security monitoring events",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "SecurityEventService",
    ),
    "security_alerts": ClassifiedDataType(
        "Actionable security incident alerts",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "SecurityEventService",
    ),
    "authentication_events": ClassifiedDataType(
        "Authentication audit events",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "IdentityService",
    ),
    "session_revocations": ClassifiedDataType(
        "Hashed session revocations",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "IdentityService",
    ),
    "langsmith_traces": ClassifiedDataType(
        "LangSmith traces",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "ObservabilityService",
    ),
    "temporal_workflow_state": ClassifiedDataType(
        "Temporal workflow state",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.LOCAL_ONLY,
        "TemporalResearchService",
    ),
    "model_provider_payload": ClassifiedDataType(
        "Raw model-provider request or response",
        DataClassification.CONFIDENTIAL,
        ProviderPolicy.APPROVED_PROVIDER,
        "AISafetyGateway",
    ),
}


@dataclass(frozen=True)
class SecurityInvariant:
    id: str
    statement: str
    status: str
    owner_sprint: int
    enforcement: str
    test_reference: str
    residual_risk: str


SECURITY_INVARIANTS: tuple[SecurityInvariant, ...] = (
    SecurityInvariant(
        "SEC-INV-01",
        "No request may return data outside the authenticated workspace.",
        "enforced",
        62,
        "Workspace-scoped queries plus forced Postgres RLS on every tenant table.",
        "test_all_tenant_tables_are_covered_by_rls",
        "A live Postgres policy test remains environment-gated until CI provisions Postgres.",
    ),
    SecurityInvariant(
        "SEC-INV-02",
        "No retrieved document may issue instructions to an agent.",
        "enforced",
        64,
        (
            "Central untrusted-content boundary, source-trust filters, and guardrail "
            "gateway restrictions."
        ),
        "test_gateway_escapes_retrieved_content_wrapper_boundaries",
        "Novel instruction forms require ongoing detector and red-team corpus updates.",
    ),
    SecurityInvariant(
        "SEC-INV-03",
        "No agent proposal may mutate durable state without satisfying policy.",
        "enforced",
        66,
        "Proposal tools, approvals, and trusted memory write paths.",
        "test_memory_mutation_entrypoints_are_classified",
        "Trusted system paths must remain narrow and explicitly classified.",
    ),
    SecurityInvariant(
        "SEC-INV-04",
        "No high-risk tool may execute without explicit approval.",
        "enforced",
        66,
        "Governed tool registry and centralized authorization.",
        "test_mutating_tools_require_policy_and_approval",
        (
            "Hosted MCP identity-provider and remote-server operations require "
            "deployment verification."
        ),
    ),
    SecurityInvariant(
        "SEC-INV-05",
        "No restricted data may be sent to an unapproved provider.",
        "enforced",
        62,
        (
            "Data-type policies, approved provider/model registry, egress allowlists, "
            "and sanitized provider payload routing."
        ),
        "test_restricted_provider_routing",
        "Supported PII and secret detectors bound the data that can be recognized and redacted.",
    ),
    SecurityInvariant(
        "SEC-INV-06",
        "No source may become retrievable before security classification.",
        "enforced",
        63,
        "Approved source and chunk security metadata is required at retrieval and re-embedding.",
        "test_sources_require_classification_before_retrieval",
        "Classifier and scanner coverage must evolve with new file types and threats.",
    ),
    SecurityInvariant(
        "SEC-INV-07",
        "No unverified factual claim may be stored as a supported finding.",
        "enforced",
        65,
        "Citation verification and claim support levels.",
        "app/tests/test_citation_verifier.py",
        "Semantic support evaluation can require human review for ambiguous evidence.",
    ),
    SecurityInvariant(
        "SEC-INV-08",
        "No secret may be recorded in logs, traces, prompts, audit metadata, or memory.",
        "enforced",
        64,
        (
            "Shared audit, trace, provider, output, and memory redaction with closed "
            "secret resolution."
        ),
        "test_trace_payloads_redact_pii_and_secrets",
        "Novel secret formats may evade best-effort detection and require pattern updates.",
    ),
    SecurityInvariant(
        "SEC-INV-09",
        "No external side effect may occur without an attributable actor and audit record.",
        "enforced",
        66,
        (
            "Attributable tool invocation identity, policy decisions, approvals, and "
            "requested/executed/denied audit events."
        ),
        "test_externally_visible_tool_paths_emit_audit_events",
        (
            "New side-effecting integrations require a governed manifest and audit "
            "regression coverage."
        ),
    ),
    SecurityInvariant(
        "SEC-INV-10",
        "No AI workflow may exceed configured resource budgets.",
        "enforced",
        67,
        (
            "Redis-backed rate limits, immutable durable budgets, loop detection, "
            "alerts, and kill switches."
        ),
        "test_durable_workflows_declare_complete_budgets",
        "Hosted Redis is a required fail-closed deployment dependency.",
    ),
    SecurityInvariant(
        "SEC-INV-11",
        "No AI-generated durable memory may bypass provenance and trust checks.",
        "enforced",
        65,
        (
            "Memory proposals, source provenance, trust/quarantine checks, conflict "
            "detection, approvals, TTL, and invalidation."
        ),
        "test_memory_mutation_entrypoints_are_classified",
        "Trusted-looking evidence can still require human review before durable activation.",
    ),
    SecurityInvariant(
        "SEC-INV-12",
        "No model output may be treated as executable authorization or policy.",
        "enforced",
        66,
        "Deterministic role, tool, approval, and service policy checks.",
        "test_mutating_tools_require_policy_and_approval",
        "New model-facing execution paths must remain behind deterministic policy boundaries.",
    ),
)


GLOBAL_TABLES = frozenset({"users", "workspaces"})

IDENTITY_BOOTSTRAP_TABLES = frozenset({"users", "workspaces", "workspace_members"})

RLS_DIRECT_TENANT_TABLES = frozenset(
    {
        "ai_cache_entries",
        "ai_cache_events",
        "ai_runs",
        "authentication_events",
        "approval_requests",
        "artifact_versions",
        "artifacts",
        "assumptions",
        "audit_events",
        "claims",
        "competitor_candidates",
        "competitors",
        "customer_segments",
        "decisions",
        "discovered_sources",
        "evidence_chunks",
        "evidence_sources",
        "evidence_source_tombstones",
        "experiment_results",
        "experiments",
        "problems",
        "project_intakes",
        "project_memory_items",
        "mcp_server_credentials",
        "mcp_oauth_authorization_transactions",
        "mcp_server_registrations",
        "project_nudges",
        "project_theses",
        "pii_token_mappings",
        "projects",
        "research_plans",
        "research_sprints",
        "risks",
        "session_revocations",
        "security_alerts",
        "security_events",
        "thesis_canvases",
        "thesis_evolution_events",
        "tool_invocations",
        "validation_missions",
        "validation_result_interpretations",
        "wedge_options",
        "workspace_data_keys",
        "workspace_kill_switch_states",
    }
)

INHERITED_TENANT_TABLES: dict[str, tuple[str, str]] = {
    "ai_steps": ("ai_run_id", "ai_runs.id"),
    "assumption_evidence_links": ("assumption_id", "assumptions.id"),
    "claim_evidence_links": ("claim_id", "claims.id"),
    "competitor_evidence_links": ("competitor_id", "competitors.id"),
    "decision_links": ("decision_id", "decisions.id"),
}

RLS_INHERITED_TENANT_TABLES = frozenset(INHERITED_TENANT_TABLES)


MEMORY_WRITE_PATHS: dict[str, str] = {
    "upsert_memory_item": "policy_checked_internal",
    "propose_preference_memory": "proposal",
    "propose_compacted_memory": "proposal",
    "approve_memory_proposal": "trusted_user",
    "reject_memory_proposal": "trusted_user",
    "upsert_from_assumption": "approved_projection",
    "upsert_from_risk": "approved_projection",
    "mark_stale": "trusted_user",
    "archive_memory": "trusted_user",
    "merge_duplicates": "trusted_user",
    "detect_memory_conflicts": "trusted_service",
    "resolve_memory_conflict": "trusted_user",
}
