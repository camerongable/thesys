"""add project theses table

Revision ID: 0004_project_theses
Revises: 0003_projects
Create Date: 2026-05-19 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_project_theses"
down_revision = "0003_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_theses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("thesis_text", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_project_theses_project_version"),
    )
    op.create_index("ix_project_theses_project_id", "project_theses", ["project_id"])
    op.create_index("ix_project_theses_workspace_id", "project_theses", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_project_theses_workspace_id", table_name="project_theses")
    op.drop_index("ix_project_theses_project_id", table_name="project_theses")
    op.drop_table("project_theses")
