"""enable tenant row-level security and scoped runtime grants

Revision ID: 0029_tenant_rls
Revises: 0028_production_identity
Create Date: 2026-07-18 00:00:00.000000
"""

from alembic import op

revision = "0029_tenant_rls"
down_revision = "0028_production_identity"
branch_labels = None
depends_on = None

RLS_DIRECT_TABLES = (
    "ai_cache_entries",
    "ai_cache_events",
    "ai_runs",
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
    "experiment_results",
    "experiments",
    "problems",
    "project_intakes",
    "project_memory_items",
    "project_nudges",
    "project_theses",
    "projects",
    "research_plans",
    "research_sprints",
    "risks",
    "thesis_canvases",
    "thesis_evolution_events",
    "tool_invocations",
    "validation_missions",
    "validation_result_interpretations",
    "wedge_options",
)

RLS_INHERITED_TABLES = {
    "ai_steps": ("ai_run_id", "ai_runs"),
    "assumption_evidence_links": ("assumption_id", "assumptions"),
    "claim_evidence_links": ("claim_id", "claims"),
    "competitor_evidence_links": ("competitor_id", "competitors"),
    "decision_links": ("decision_id", "decisions"),
}

IDENTITY_TABLES = ("users", "workspaces", "workspace_members")
RUNTIME_ROLES = ("thesys_api", "thesys_worker", "thesys_readonly")
WORKSPACE_SETTING = "NULLIF(current_setting('app.workspace_id', true), '')::uuid"


def upgrade() -> None:
    for table in RLS_DIRECT_TABLES:
        _enable_rls(table, f"workspace_id = {WORKSPACE_SETTING}")

    for table, (foreign_key, parent_table) in RLS_INHERITED_TABLES.items():
        predicate = (
            "EXISTS ("
            f'SELECT 1 FROM "{parent_table}" AS tenant_parent '
            f'WHERE tenant_parent.id = "{table}"."{foreign_key}" '
            f"AND tenant_parent.workspace_id = {WORKSPACE_SETTING}"
            ")"
        )
        _enable_rls(table, predicate)

    tenant_tables = (*RLS_DIRECT_TABLES, *RLS_INHERITED_TABLES)
    _grant_runtime_role(
        "thesys_api",
        select_tables=(*IDENTITY_TABLES, *tenant_tables),
        mutate_tables=(*IDENTITY_TABLES, *tenant_tables),
    )
    _grant_runtime_role(
        "thesys_worker",
        select_tables=(*IDENTITY_TABLES, *tenant_tables),
        mutate_tables=tenant_tables,
    )
    _grant_runtime_role(
        "thesys_readonly",
        select_tables=tenant_tables,
        mutate_tables=(),
    )


def downgrade() -> None:
    for table in reversed((*RLS_DIRECT_TABLES, *RLS_INHERITED_TABLES)):
        op.execute(f'DROP POLICY IF EXISTS workspace_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')

    all_tables = (*IDENTITY_TABLES, *RLS_DIRECT_TABLES, *RLS_INHERITED_TABLES)
    table_list = _quoted_table_list(all_tables)
    for role in RUNTIME_ROLES:
        _execute_if_role_exists(
            role,
            f"REVOKE ALL PRIVILEGES ON TABLE {table_list} FROM {role}",
        )


def _enable_rls(table: str, predicate: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY workspace_isolation ON "{table}" '
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )


def _grant_runtime_role(
    role: str,
    *,
    select_tables: tuple[str, ...],
    mutate_tables: tuple[str, ...],
) -> None:
    _execute_if_role_exists(role, f"GRANT USAGE ON SCHEMA public TO {role}")
    _execute_if_role_exists(role, f"REVOKE CREATE ON SCHEMA public FROM {role}")
    _execute_if_role_exists(
        role,
        f"GRANT SELECT ON TABLE {_quoted_table_list(select_tables)} TO {role}",
    )
    if mutate_tables:
        _execute_if_role_exists(
            role,
            "GRANT INSERT, UPDATE, DELETE ON TABLE "
            f"{_quoted_table_list(mutate_tables)} TO {role}",
        )


def _execute_if_role_exists(role: str, statement: str) -> None:
    escaped_statement = statement.replace("'", "''")
    op.execute(
        "DO $role_grant$ "
        "BEGIN "
        f"IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
        f"EXECUTE '{escaped_statement}'; "
        "END IF; "
        "END $role_grant$"
    )


def _quoted_table_list(tables: tuple[str, ...]) -> str:
    return ", ".join(f'"{table}"' for table in tables)
