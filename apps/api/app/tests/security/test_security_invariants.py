import ast
import inspect
from importlib.util import find_spec
from pathlib import Path

import pytest

from app.core.config import Settings
from app.db.models import Base, EvidenceSource
from app.features.governance_tools.registry import list_tool_definitions
from app.security.contracts import (
    DATA_TYPES,
    GLOBAL_TABLES,
    INHERITED_TENANT_TABLES,
    MEMORY_WRITE_PATHS,
    SECURITY_INVARIANTS,
    DataClassification,
    ProviderPolicy,
)
from app.services import memory_service, temporal_research_service, tool_service

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


@pytest.mark.xfail(strict=True, reason="Sprint 62 will reject dev auth in production config.")
def test_production_auth_cannot_run_in_dev_header_mode() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production", auth_mode="dev")


@pytest.mark.xfail(strict=True, reason="Sprint 63 will require classification before promotion.")
def test_sources_require_classification_before_retrieval() -> None:
    assert EvidenceSource.__table__.c.classification.nullable is False


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
