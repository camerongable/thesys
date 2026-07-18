import ast
import importlib.util
import inspect
from importlib.util import find_spec
from pathlib import Path

import pytest
import yaml

from app.core.config import Settings
from app.db.models import Base
from app.features.governance_tools.registry import list_tool_definitions
from app.security.contracts import (
    DATA_TYPES,
    GLOBAL_TABLES,
    IDENTITY_BOOTSTRAP_TABLES,
    INHERITED_TENANT_TABLES,
    MEMORY_WRITE_PATHS,
    RLS_DIRECT_TENANT_TABLES,
    RLS_INHERITED_TENANT_TABLES,
    SECURITY_INVARIANTS,
    DataClassification,
    ProviderPolicy,
)
from app.services import (
    evidence_service,
    memory_service,
    retrieval_service,
    temporal_research_service,
    tool_service,
)

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_security_invariant_registry_is_complete_and_owned() -> None:
    assert [item.id for item in SECURITY_INVARIANTS] == [
        f"SEC-INV-{index:02d}" for index in range(1, 13)
    ]
    assert {item.status for item in SECURITY_INVARIANTS} <= {"enforced", "partial", "planned"}
    assert all(61 < item.owner_sprint <= 68 for item in SECURITY_INVARIANTS)
    assert all(
        item.enforcement and item.test_reference and item.residual_risk
        for item in SECURITY_INVARIANTS
    )


def test_security_contract_documents_cover_required_boundaries_and_pr_questions() -> None:
    security_dir = REPO_ROOT / "docs" / "security"
    required_documents = {
        "THREAT_MODEL.md",
        "DATA_CLASSIFICATION.md",
        "CONTROL_MATRIX.md",
        "SECURITY_ARCHITECTURE.md",
        "ABUSE_CASES.md",
    }
    assert required_documents <= {path.name for path in security_dir.glob("*.md")}

    architecture = (security_dir / "SECURITY_ARCHITECTURE.md").read_text().casefold()
    required_boundaries = {
        "browser to api",
        "api to database",
        "api to object storage",
        "api to litellm",
        "litellm to model provider",
        "api to external search provider",
        "api to fetched url",
        "uploaded file to parser",
        "retrieval layer to llm prompt",
        "llm to tool gateway",
        "tool gateway to application service",
        "agent to durable project memory",
        "api to langsmith",
        "api to temporal",
        "mcp client to mcp server",
    }
    assert all(boundary in architecture for boundary in required_boundaries)

    pull_request_template = (REPO_ROOT / ".github" / "pull_request_template.md").read_text()
    required_questions = {
        "introduce a new trust boundary",
        "send new data to an external provider",
        "add or modify an agent tool",
        "write durable memory",
        "affect tenant isolation",
        "require new audit events",
        "alter data retention or deletion",
        "require new adversarial tests",
    }
    assert all(question in pull_request_template for question in required_questions)


def test_data_classification_registry_covers_sensitive_assets() -> None:
    required = {
        "user_identity",
        "workspace_membership",
        "business_plan",
        "uploaded_file",
        "raw_extracted_text",
        "sanitized_searchable_text",
        "interview_notes_with_identifiers",
        "embeddings",
        "project_memory",
        "research_results",
        "validation_results",
        "decision_records",
        "api_credentials",
        "oauth_credentials",
        "system_prompts",
        "tool_schemas",
        "mcp_server_registrations",
        "audit_events",
        "authentication_events",
        "session_revocations",
        "langsmith_traces",
        "temporal_workflow_state",
        "model_provider_payload",
    }

    assert required <= DATA_TYPES.keys()
    assert all(item.owner for item in DATA_TYPES.values())


def test_restricted_data_types_define_provider_policy() -> None:
    restricted = [
        item for item in DATA_TYPES.values() if item.classification == DataClassification.RESTRICTED
    ]

    assert restricted
    assert all(
        item.provider_policy
        in {ProviderPolicy.LOCAL_ONLY, ProviderPolicy.APPROVED_RESTRICTED_PROVIDER}
        for item in restricted
    )


def test_all_database_tables_have_a_tenant_path() -> None:
    uncategorized: list[str] = []
    broken_inherited_paths: list[str] = []

    for table in Base.metadata.tables.values():
        if table.name in GLOBAL_TABLES or "workspace_id" in table.c:
            continue
        inherited = INHERITED_TENANT_TABLES.get(table.name)
        if inherited is None:
            uncategorized.append(table.name)
            continue
        column_name, target = inherited
        foreign_keys = {str(key.target_fullname) for key in table.c[column_name].foreign_keys}
        if target not in foreign_keys:
            broken_inherited_paths.append(f"{table.name}.{column_name}->{target}")

    assert not uncategorized, f"Tables without a declared tenant path: {uncategorized}"
    assert not broken_inherited_paths, f"Invalid inherited tenant paths: {broken_inherited_paths}"


def test_all_tenant_tables_are_covered_by_rls() -> None:
    direct_tenant_tables = {
        table.name
        for table in Base.metadata.tables.values()
        if "workspace_id" in table.c and table.name not in IDENTITY_BOOTSTRAP_TABLES
    }

    assert direct_tenant_tables == RLS_DIRECT_TENANT_TABLES
    assert set(INHERITED_TENANT_TABLES) == RLS_INHERITED_TENANT_TABLES
    assert {
        "projects",
        "project_theses",
        "evidence_sources",
        "evidence_chunks",
        "project_memory_items",
        "research_sprints",
        "research_plans",
        "competitors",
        "assumptions",
        "validation_missions",
        "experiment_results",
        "decisions",
        "tool_invocations",
        "approval_requests",
        "audit_events",
    } <= RLS_DIRECT_TENANT_TABLES


def test_rls_migration_forces_policies_and_scoped_role_grants(monkeypatch) -> None:
    migration_path = REPO_ROOT / "apps/api/alembic/versions/0029_tenant_rls.py"
    spec = importlib.util.spec_from_file_location("tenant_rls_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    assert set(migration.RLS_DIRECT_TABLES) < RLS_DIRECT_TENANT_TABLES
    assert RLS_DIRECT_TENANT_TABLES - set(migration.RLS_DIRECT_TABLES) == {
        "authentication_events",
        "pii_token_mappings",
        "session_revocations",
        "workspace_data_keys",
    }
    assert set(migration.RLS_INHERITED_TABLES) == RLS_INHERITED_TENANT_TABLES
    combined = "\n".join(statements)
    for table in (*migration.RLS_DIRECT_TABLES, *migration.RLS_INHERITED_TABLES):
        assert f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY' in statements
        assert f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY' in statements
        assert f'CREATE POLICY workspace_isolation ON "{table}"' in combined
    assert "current_setting('app.workspace_id', true)" in combined
    assert "WITH CHECK" in combined
    assert "GRANT SELECT" in combined
    assert "GRANT INSERT, UPDATE, DELETE" in combined
    assert "thesys_api" in combined
    assert "thesys_worker" in combined
    assert "thesys_readonly" in combined
    readonly_grants = "\n".join(
        statement for statement in statements if "thesys_readonly" in statement
    )
    assert '"users"' not in readonly_grants
    assert "GRANT INSERT, UPDATE, DELETE" not in readonly_grants

    statements.clear()
    migration.downgrade()
    for table in (*migration.RLS_DIRECT_TABLES, *migration.RLS_INHERITED_TABLES):
        assert f'DROP POLICY IF EXISTS workspace_isolation ON "{table}"' in statements
        assert f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY' in statements


def test_workspace_data_key_migration_adds_forced_rls_and_scoped_grants(monkeypatch) -> None:
    migration_path = REPO_ROOT / "apps/api/alembic/versions/0030_workspace_data_keys.py"
    spec = importlib.util.spec_from_file_location("workspace_data_key_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "create_table", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(migration.op, "create_index", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.TABLE_NAME in RLS_DIRECT_TENANT_TABLES
    assert 'ALTER TABLE "workspace_data_keys" ENABLE ROW LEVEL SECURITY' in statements
    assert 'ALTER TABLE "workspace_data_keys" FORCE ROW LEVEL SECURITY' in statements
    assert 'CREATE POLICY workspace_isolation ON "workspace_data_keys"' in combined
    assert "current_setting('app.workspace_id', true)" in combined
    assert "WITH CHECK" in combined
    assert "thesys_api" in combined and "SELECT, INSERT, UPDATE, DELETE" in combined
    assert "thesys_worker" in combined
    assert "thesys_readonly" not in combined


def test_authentication_event_migration_limits_pre_authentication_writes(monkeypatch) -> None:
    migration_path = REPO_ROOT / "apps/api/alembic/versions/0031_authentication_events.py"
    spec = importlib.util.spec_from_file_location("authentication_event_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "create_table", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(migration.op, "create_index", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.TABLE_NAME in RLS_DIRECT_TENANT_TABLES
    assert 'ALTER TABLE "authentication_events" ENABLE ROW LEVEL SECURITY' in statements
    assert 'ALTER TABLE "authentication_events" FORCE ROW LEVEL SECURITY' in statements
    assert 'CREATE POLICY workspace_isolation ON "authentication_events"' in combined
    assert "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid" in combined
    assert "pre_authentication_failure_insert" in combined
    assert "workspace_id IS NULL AND user_id IS NULL" in combined
    assert "thesys_api" in combined and "SELECT, INSERT" in combined
    assert "thesys_worker" in combined and "thesys_readonly" in combined


def test_session_revocation_migration_forces_rls_and_immutable_runtime_grants(monkeypatch) -> None:
    migration_path = REPO_ROOT / "apps/api/alembic/versions/0032_session_revocations.py"
    spec = importlib.util.spec_from_file_location("session_revocation_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "create_table", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(migration.op, "create_index", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.TABLE_NAME in RLS_DIRECT_TENANT_TABLES
    assert 'ALTER TABLE "session_revocations" ENABLE ROW LEVEL SECURITY' in statements
    assert 'ALTER TABLE "session_revocations" FORCE ROW LEVEL SECURITY' in statements
    assert 'CREATE POLICY workspace_isolation ON "session_revocations"' in combined
    assert "current_setting('app.workspace_id', true)" in combined
    assert "thesys_api" in combined and "SELECT, INSERT" in combined
    assert "UPDATE" not in combined and "DELETE" not in combined


def test_evidence_quarantine_migration_allows_the_fail_closed_status(monkeypatch) -> None:
    migration_path = REPO_ROOT / "apps/api/alembic/versions/0033_evidence_quarantine.py"
    spec = importlib.util.spec_from_file_location("evidence_quarantine_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    constraints: list[tuple[object, ...]] = []
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda *args, **_kwargs: constraints.append(args),
    )

    migration.upgrade()

    assert constraints == [
        (
            migration.CONSTRAINT_NAME,
            migration.TABLE_NAME,
            "ingestion_status in ('pending','processing','ready','failed','quarantined')",
        )
    ]


def test_pii_token_mapping_migration_forces_rls_and_excludes_readonly_role(monkeypatch) -> None:
    migration_path = REPO_ROOT / "apps/api/alembic/versions/0034_pii_token_mappings.py"
    spec = importlib.util.spec_from_file_location("pii_token_mapping_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "create_table", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(migration.op, "create_index", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    combined = "\n".join(statements)
    assert migration.TABLE_NAME in RLS_DIRECT_TENANT_TABLES
    assert 'ALTER TABLE "pii_token_mappings" ENABLE ROW LEVEL SECURITY' in statements
    assert 'ALTER TABLE "pii_token_mappings" FORCE ROW LEVEL SECURITY' in statements
    assert 'CREATE POLICY workspace_isolation ON "pii_token_mappings"' in combined
    assert "current_setting('app.workspace_id', true)" in combined
    assert "WITH CHECK" in combined
    assert "thesys_api" in combined and "SELECT, INSERT, UPDATE, DELETE" in combined
    assert "thesys_worker" in combined
    assert "thesys_readonly" not in combined


def test_application_credentials_are_read_only_through_secret_provider() -> None:
    sensitive_settings = {
        "auth_jwt_secret",
        "litellm_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "gemini_api_key",
        "s3_access_key_id",
        "s3_secret_access_key",
        "tavily_api_key",
        "langsmith_api_key",
    }
    allowed_paths = {
        REPO_ROOT / "apps/api/app/core/config.py",
        REPO_ROOT / "apps/api/app/security/secrets.py",
    }
    approved_provider_consumers = {
        "apps/api/app/ai/litellm_client.py",
        "apps/api/app/core/auth.py",
        "apps/api/app/routers/ai.py",
        "apps/api/app/security/encryption.py",
        "apps/api/app/services/embedding_service.py",
        "apps/api/app/services/external_search_service.py",
        "apps/api/app/services/langsmith_observability_service.py",
        "apps/api/app/services/multimodal_extraction_service.py",
        "apps/api/app/services/object_storage_service.py",
    }
    violations: list[str] = []
    provider_consumers: set[str] = set()

    for path in (REPO_ROOT / "apps/api/app").rglob("*.py"):
        if path in allowed_paths or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in sensitive_settings:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}:{node.attr}")
            if isinstance(node, ast.ImportFrom) and node.module == "app.security.secrets":
                provider_consumers.add(str(path.relative_to(REPO_ROOT)))

    assert not violations, f"Credential settings bypass the secret provider: {violations}"
    assert provider_consumers <= approved_provider_consumers


def test_database_role_manifest_separates_runtime_and_migration_credentials() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    api = compose["services"]["api"]
    worker = compose["services"]["temporal-worker"]
    api_environment = api["environment"]
    worker_environment = worker["environment"]

    assert "thesys_api:" in api_environment["DATABASE_URL"]
    assert "thesys_migration:" in api_environment["MIGRATION_DATABASE_URL"]
    assert "unset MIGRATION_DATABASE_URL" in api["command"]
    assert "exec uvicorn" in api["command"]
    assert "thesys_worker:" in worker_environment["DATABASE_URL"]
    assert api_environment["DATABASE_RUNTIME_ROLE"] == "api"
    assert worker_environment["DATABASE_RUNTIME_ROLE"] == "worker"

    bootstrap = (REPO_ROOT / "infra/postgres/init.sql").read_text()
    assert "thesys_migration" in bootstrap and "BYPASSRLS" in bootstrap
    for role in ("thesys_api", "thesys_worker", "thesys_readonly"):
        assert role in bootstrap
    assert bootstrap.count("NOBYPASSRLS") >= 3
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC" in bootstrap
    assert "ALTER SCHEMA public OWNER TO thesys_migration" in bootstrap


def test_mutating_tools_require_policy_and_approval() -> None:
    mutating_tools = [item for item in list_tool_definitions() if item.access_mode != "read"]

    assert mutating_tools
    assert all(item.allowed_project_roles for item in mutating_tools)
    assert all(item.approval_policy != "never_required" for item in mutating_tools)
    assert callable(tool_service._authorize_tool_invocation)


def test_memory_mutation_entrypoints_are_classified() -> None:
    tree = ast.parse(inspect.getsource(memory_service))
    detected_mutators: set[str] = set()
    mutation_calls = {"commit", "flush", "delete"}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if isinstance(child.func, ast.Attribute) and child.func.attr in mutation_calls:
                detected_mutators.add(node.name)
            if isinstance(child.func, ast.Name) and child.func.id == "ProjectMemoryItem":
                detected_mutators.add(node.name)

    assert detected_mutators <= MEMORY_WRITE_PATHS.keys()
    assert {"upsert_from_assumption", "upsert_from_risk"} <= MEMORY_WRITE_PATHS.keys()
    assert all(hasattr(memory_service, function_name) for function_name in MEMORY_WRITE_PATHS)


def test_externally_visible_tool_paths_emit_audit_events() -> None:
    execute_source = inspect.getsource(tool_service.execute_tool)

    assert "tool_invocation_requested" in execute_source
    assert "tool_invocation_executed" in execute_source
    assert "_audit_tool_denial" in execute_source


def test_production_auth_cannot_run_in_dev_header_mode() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production", auth_mode="dev")


def test_sources_require_classification_before_retrieval() -> None:
    retrieval_conditions = inspect.getsource(retrieval_service._base_conditions)
    reembedding = inspect.getsource(evidence_service.reembed_evidence)

    assert 'source_metadata["security"]["security_status"]' in retrieval_conditions
    assert 'source_metadata["security"]["classification_status"]' in retrieval_conditions
    assert 'chunk_metadata["security"]["retrieval_allowed"]' in retrieval_conditions
    assert "is_source_approved" in reembedding
    assert "is_chunk_retrievable" in reembedding


@pytest.mark.xfail(strict=True, reason="Sprint 64 will centralize all model calls.")
def test_all_llm_calls_route_through_guardrail_gateway() -> None:
    assert find_spec("app.security.guardrail_gateway") is not None


@pytest.mark.xfail(strict=True, reason="Sprint 67 will add complete durable-workflow budgets.")
def test_durable_workflows_declare_complete_budgets() -> None:
    payload_source = inspect.getsource(temporal_research_service._workflow_payload)
    required_budget_fields = {
        "max_tokens",
        "max_cost_usd",
        "max_duration_seconds",
        "max_retrieval_calls",
        "max_tool_calls",
    }

    assert all(field in payload_source for field in required_budget_fields)
