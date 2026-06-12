"""add mcp tool boundary audit records

Revision ID: 0016_mcp_tool_boundary
Revises: 0015_langsmith_observability
Create Date: 2026-06-11 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0016_mcp_tool_boundary"
down_revision = "0015_langsmith_observability"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "tool_invocations",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("research_sprint_id", sa.Uuid(), nullable=True),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("access_mode", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("input_json", _json_type(), nullable=False),
        sa.Column("output_json", _json_type(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_by", sa.String(length=20), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "access_mode in ('read','write','proposal')",
            name="ck_tool_invocations_access_mode",
        ),
        sa.CheckConstraint(
            "requested_by in ('agent','user','system')",
            name="ck_tool_invocations_requested_by",
        ),
        sa.CheckConstraint(
            "risk_level in ('low','medium','high')",
            name="ck_tool_invocations_risk_level",
        ),
        sa.CheckConstraint(
            "status in ('requested','approved','rejected','executed','failed')",
            name="ck_tool_invocations_status",
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_sprint_id"], ["research_sprints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_invocations_access_mode", "tool_invocations", ["access_mode"])
    op.create_index("ix_tool_invocations_approved_by_user_id", "tool_invocations", ["approved_by_user_id"])
    op.create_index("ix_tool_invocations_project_id", "tool_invocations", ["project_id"])
    op.create_index("ix_tool_invocations_research_sprint_id", "tool_invocations", ["research_sprint_id"])
    op.create_index("ix_tool_invocations_risk_level", "tool_invocations", ["risk_level"])
    op.create_index("ix_tool_invocations_status", "tool_invocations", ["status"])
    op.create_index("ix_tool_invocations_tool_name", "tool_invocations", ["tool_name"])
    op.create_index("ix_tool_invocations_workspace_id", "tool_invocations", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_invocations_workspace_id", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_tool_name", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_status", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_risk_level", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_research_sprint_id", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_project_id", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_approved_by_user_id", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_access_mode", table_name="tool_invocations")
    op.drop_table("tool_invocations")
