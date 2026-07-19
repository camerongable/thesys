"""add workspace kill-switch state

Revision ID: 0039_workspace_kill_switch_states
Revises: 0038_mcp_server_registrations
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0039_workspace_kill_switch_states"
down_revision = "0038_mcp_server_registrations"
branch_labels = None
depends_on = None

TABLE_NAME = "workspace_kill_switch_states"
RUNTIME_ROLES = ("thesys_api", "thesys_worker", "thesys_readonly")
WORKSPACE_SETTING = "NULLIF(current_setting('app.workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("disable_all_agent_writes", sa.Boolean(), nullable=False),
        sa.Column("disable_external_mcp", sa.Boolean(), nullable=False),
        sa.Column("disable_external_egress", sa.Boolean(), nullable=False),
        sa.Column("disable_model_provider", sa.Boolean(), nullable=False),
        sa.Column("disable_memory_writes", sa.Boolean(), nullable=False),
        sa.Column("disable_source_fetching", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            name="uq_workspace_kill_switch_states_workspace",
        ),
    )
    op.create_index("ix_workspace_kill_switch_states_workspace_id", TABLE_NAME, ["workspace_id"])
    op.execute(f'ALTER TABLE "{TABLE_NAME}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY workspace_isolation ON "{TABLE_NAME}" '
        f"USING (workspace_id = {WORKSPACE_SETTING}) "
        f"WITH CHECK (workspace_id = {WORKSPACE_SETTING})"
    )
    _grant_if_role_exists("thesys_api", "SELECT, INSERT, UPDATE, DELETE")
    _grant_if_role_exists("thesys_worker", "SELECT, INSERT, UPDATE, DELETE")
    _grant_if_role_exists("thesys_readonly", "SELECT")


def downgrade() -> None:
    for role in RUNTIME_ROLES:
        _execute_if_role_exists(role, f'REVOKE ALL PRIVILEGES ON TABLE "{TABLE_NAME}" FROM {role}')
    op.execute(f'DROP POLICY IF EXISTS workspace_isolation ON "{TABLE_NAME}"')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_workspace_kill_switch_states_workspace_id", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)


def _grant_if_role_exists(role: str, privileges: str) -> None:
    _execute_if_role_exists(role, f"GRANT {privileges} ON TABLE \"{TABLE_NAME}\" TO {role}")


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
