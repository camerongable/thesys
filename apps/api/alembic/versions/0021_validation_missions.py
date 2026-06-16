"""add validation missions

Revision ID: 0021_validation_missions
Revises: 0020_wedge_options
Create Date: 2026-06-13 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0021_validation_missions"
down_revision = "0020_wedge_options"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_missions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("assumption_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=True),
        sa.Column("mission_title", sa.String(length=255), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=False),
        sa.Column("test_type", sa.String(length=120), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("success_criteria", sa.Text(), nullable=False),
        sa.Column("failure_criteria", sa.Text(), nullable=False),
        sa.Column("assets", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('planned','running','results_logged','interpreted','closed')",
            name="ck_validation_missions_status",
        ),
        sa.ForeignKeyConstraint(["assumption_id"], ["assumptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_missions_assumption_id", "validation_missions", ["assumption_id"])
    op.create_index("ix_validation_missions_experiment_id", "validation_missions", ["experiment_id"])
    op.create_index("ix_validation_missions_project_id", "validation_missions", ["project_id"])
    op.create_index("ix_validation_missions_workspace_id", "validation_missions", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_validation_missions_workspace_id", table_name="validation_missions")
    op.drop_index("ix_validation_missions_project_id", table_name="validation_missions")
    op.drop_index("ix_validation_missions_experiment_id", table_name="validation_missions")
    op.drop_index("ix_validation_missions_assumption_id", table_name="validation_missions")
    op.drop_table("validation_missions")
