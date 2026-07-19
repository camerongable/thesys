"""add encrypted project-local PII token mappings

Revision ID: 0034_pii_token_mappings
Revises: 0033_evidence_quarantine
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0034_pii_token_mappings"
down_revision = "0033_evidence_quarantine"
branch_labels = None
depends_on = None

TABLE_NAME = "pii_token_mappings"
RUNTIME_ROLES = ("thesys_api", "thesys_worker", "thesys_readonly")
WORKSPACE_SETTING = "NULLIF(current_setting('app.workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("encrypted_value_ciphertext", sa.Text(), nullable=False),
        sa.Column("encrypted_value_nonce", sa.String(length=32), nullable=False),
        sa.Column("encrypted_value_key_version", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("algorithm = 'AES-256-GCM'", name="ck_pii_token_mappings_algorithm"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "token", name="uq_pii_token_mappings_project_token"),
    )
    op.create_index("ix_pii_token_mappings_workspace_id", TABLE_NAME, ["workspace_id"])
    op.create_index("ix_pii_token_mappings_project_id", TABLE_NAME, ["project_id"])
    op.execute(f'ALTER TABLE "{TABLE_NAME}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY workspace_isolation ON "{TABLE_NAME}" '
        f"USING (workspace_id = {WORKSPACE_SETTING}) "
        f"WITH CHECK (workspace_id = {WORKSPACE_SETTING})"
    )
    _grant_if_role_exists("thesys_api", "SELECT, INSERT, UPDATE, DELETE")
    _grant_if_role_exists("thesys_worker", "SELECT, INSERT, UPDATE, DELETE")


def downgrade() -> None:
    for role in RUNTIME_ROLES:
        _execute_if_role_exists(role, f'REVOKE ALL PRIVILEGES ON TABLE "{TABLE_NAME}" FROM {role}')
    op.execute(f'DROP POLICY IF EXISTS workspace_isolation ON "{TABLE_NAME}"')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_pii_token_mappings_project_id", table_name=TABLE_NAME)
    op.drop_index("ix_pii_token_mappings_workspace_id", table_name=TABLE_NAME)
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
