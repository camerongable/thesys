"""persist remote MCP write invocation idempotency

Revision ID: 0042_remote_mcp_write_invocations
Revises: 0041_mcp_oauth_authorization_transactions
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0042_remote_mcp_write_invocations"
down_revision = "0041_mcp_oauth_authorization_transactions"
branch_labels = None
depends_on = None

TABLE_NAME = "tool_invocations"
REMOTE_SERVER_COLUMN = "remote_mcp_server_id"
IDEMPOTENCY_KEY_COLUMN = "idempotency_key"


def upgrade() -> None:
    op.add_column(TABLE_NAME, sa.Column(REMOTE_SERVER_COLUMN, sa.Uuid(), nullable=True))
    op.add_column(
        TABLE_NAME,
        sa.Column(IDEMPOTENCY_KEY_COLUMN, sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_tool_invocations_remote_mcp_server_id",
        TABLE_NAME,
        "mcp_server_registrations",
        [REMOTE_SERVER_COLUMN],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_tool_invocations_remote_mcp_server_id",
        TABLE_NAME,
        [REMOTE_SERVER_COLUMN],
    )
    op.create_unique_constraint(
        "uq_tool_invocations_remote_mcp_idempotency",
        TABLE_NAME,
        [REMOTE_SERVER_COLUMN, IDEMPOTENCY_KEY_COLUMN],
    )


def downgrade() -> None:
    op.drop_constraint("uq_tool_invocations_remote_mcp_idempotency", TABLE_NAME, type_="unique")
    op.drop_index("ix_tool_invocations_remote_mcp_server_id", table_name=TABLE_NAME)
    op.drop_constraint("fk_tool_invocations_remote_mcp_server_id", TABLE_NAME, type_="foreignkey")
    op.drop_column(TABLE_NAME, IDEMPOTENCY_KEY_COLUMN)
    op.drop_column(TABLE_NAME, REMOTE_SERVER_COLUMN)
