"""add immutable authentication audit events

Revision ID: 0031_authentication_events
Revises: 0030_workspace_data_keys
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0031_authentication_events"
down_revision = "0030_workspace_data_keys"
branch_labels = None
depends_on = None

TABLE_NAME = "authentication_events"
RUNTIME_ROLES = ("thesys_api", "thesys_worker", "thesys_readonly")
WORKSPACE_SETTING = "NULLIF(current_setting('app.workspace_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("authentication_method", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "event_type in ("
            "'login_success','login_failure','token_validation_failure',"
            "'workspace_access_denied','role_change','session_revoked',"
            "'cross_tenant_access_attempt'"
            ")",
            name="ck_authentication_events_event_type",
        ),
        sa.CheckConstraint(
            "authentication_method in ('dev','jwt','api_key','oidc')",
            name="ck_authentication_events_method",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_authentication_events_workspace_id", TABLE_NAME, ["workspace_id"])
    op.create_index("ix_authentication_events_user_id", TABLE_NAME, ["user_id"])
    op.create_index("ix_authentication_events_event_type", TABLE_NAME, ["event_type"])
    op.create_index("ix_authentication_events_created_at", TABLE_NAME, ["created_at"])
    op.execute(f'ALTER TABLE "{TABLE_NAME}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY workspace_isolation ON "{TABLE_NAME}" '
        f'FOR ALL USING (workspace_id = {WORKSPACE_SETTING}) '
        f'WITH CHECK (workspace_id = {WORKSPACE_SETTING})'
    )
    op.execute(
        f'CREATE POLICY pre_authentication_failure_insert ON "{TABLE_NAME}" '
        "FOR INSERT WITH CHECK (workspace_id IS NULL AND user_id IS NULL)"
    )
    _grant_if_role_exists("thesys_api", "SELECT, INSERT")
    _grant_if_role_exists("thesys_worker", "SELECT, INSERT")
    _grant_if_role_exists("thesys_readonly", "SELECT")


def downgrade() -> None:
    for role in RUNTIME_ROLES:
        _execute_if_role_exists(role, f'REVOKE ALL PRIVILEGES ON TABLE "{TABLE_NAME}" FROM {role}')
    op.execute(f'DROP POLICY IF EXISTS pre_authentication_failure_insert ON "{TABLE_NAME}"')
    op.execute(f'DROP POLICY IF EXISTS workspace_isolation ON "{TABLE_NAME}"')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{TABLE_NAME}" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_authentication_events_created_at", table_name=TABLE_NAME)
    op.drop_index("ix_authentication_events_event_type", table_name=TABLE_NAME)
    op.drop_index("ix_authentication_events_user_id", table_name=TABLE_NAME)
    op.drop_index("ix_authentication_events_workspace_id", table_name=TABLE_NAME)
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
