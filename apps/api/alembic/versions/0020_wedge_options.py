"""add wedge explorer options

Revision ID: 0020_wedge_options
Revises: 0019_thesis_canvas
Create Date: 2026-06-13 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0020_wedge_options"
down_revision = "0019_thesis_canvas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wedge_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=False),
        sa.Column("problem_focus", sa.Text(), nullable=False),
        sa.Column("why_it_might_work", sa.Text(), nullable=False),
        sa.Column("main_risk", sa.Text(), nullable=False),
        sa.Column("competitor_pressure", sa.String(length=20), nullable=False),
        sa.Column("evidence_strength", sa.String(length=20), nullable=False),
        sa.Column("validation_test", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.String(length=30), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "competitor_pressure in ('low','medium','high')",
            name="ck_wedge_options_competitor_pressure",
        ),
        sa.CheckConstraint(
            "evidence_strength in ('none','weak','partial','strong')",
            name="ck_wedge_options_evidence_strength",
        ),
        sa.CheckConstraint(
            "recommendation in ("
            "'recommended','promising','research_later','avoid_for_now','rejected'"
            ")",
            name="ck_wedge_options_recommendation",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wedge_options_project_id", "wedge_options", ["project_id"])
    op.create_index("ix_wedge_options_recommendation", "wedge_options", ["recommendation"])
    op.create_index("ix_wedge_options_workspace_id", "wedge_options", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_wedge_options_workspace_id", table_name="wedge_options")
    op.drop_index("ix_wedge_options_recommendation", table_name="wedge_options")
    op.drop_index("ix_wedge_options_project_id", table_name="wedge_options")
    op.drop_table("wedge_options")
