"""add encrypted per-server MCP credentials

Revision ID: 0040_mcp_server_credentials
Revises: 0039_workspace_kill_switch_states
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0040_mcp_server_credentials"
down_revision = "0039_workspace_kill_switch_states"
branch_labels = None
depends_on = None

TABLE_NAME = "mcp_server_credentials"
RUNTIME_ROLES = ("thesys_api", "thesys_worker", "thesys_readonly")
WORKSPACE_SETTING = "NULLIF(current_setting('app.workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("server_registration_id", sa.Uuid(), nullable=False),
        sa.Column("credential_type", sa.String(length=32), nullable=False),
        sa.Column("issuer", sa.String(length=2048), nullable=False),
        sa.Column("audience", sa.String(length=2048), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("access_token_nonce", sa.String(length=32), nullable=True),
        sa.Column("access_token_key_version", sa.String(length=64), nullable=True),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("refresh_token_nonce", sa.String(length=32), nullable=True),
        sa.Column("refresh_token_key_version", sa.String(length=64), nullable=True),
        sa.Column("client_id", sa.String(length=255), nullable=True),
        sa.Column("client_secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("client_secret_nonce", sa.String(length=32), nullable=True),
        sa.Column("client_secret_key_version", sa.String(length=64), nullable=True),
        sa.Column("algorithm", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "credential_type in ('oauth_user_delegated','oauth_client_credentials')",
            name="ck_mcp_server_credentials_type",
        ),
        sa.CheckConstraint(
            "algorithm = 'AES-256-GCM'",
            name="ck_mcp_server_credentials_algorithm",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["server_registration_id"],
            ["mcp_server_registrations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "server_registration_id",
            name="uq_mcp_server_credentials_registration",
        ),
    )
    op.create_index("ix_mcp_server_credentials_workspace_id", TABLE_NAME, ["workspace_id"])
    op.create_index(
        "ix_mcp_server_credentials_server_registration_id",
        TABLE_NAME,
        ["server_registration_id"],
    )
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
    op.drop_index("ix_mcp_server_credentials_server_registration_id", table_name=TABLE_NAME)
    op.drop_index("ix_mcp_server_credentials_workspace_id", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)


def _grant_if_role_exists(role: str, privileges: str) -> None:
    _execute_if_role_exists(role, f'GRANT {privileges} ON TABLE "{TABLE_NAME}" TO {role}')


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
