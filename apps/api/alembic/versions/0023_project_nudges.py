"""add project nudges

Revision ID: 0023_project_nudges
Revises: 0022_validation_interp
Create Date: 2026-06-15 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0023_project_nudges"
down_revision = "0022_validation_interp"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "project_nudges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("nudge_key", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("action_payload", _json_type(), nullable=False),
        sa.Column("dismissed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "severity in ('info','warning','action_required')",
            name="ck_project_nudges_severity",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "nudge_key", name="uq_project_nudges_project_key"),
    )
    op.create_index("ix_project_nudges_project_id", "project_nudges", ["project_id"])
    op.create_index("ix_project_nudges_workspace_id", "project_nudges", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_project_nudges_workspace_id", table_name="project_nudges")
    op.drop_index("ix_project_nudges_project_id", table_name="project_nudges")
    op.drop_table("project_nudges")
