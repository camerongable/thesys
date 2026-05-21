"""add ai run and step tables

Revision ID: 0005_ai_runs_steps
Revises: 0004_project_theses
Create Date: 2026-05-20 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0005_ai_runs_steps"
down_revision = "0004_project_theses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("model_provider", sa.String(length=100), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=255), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('queued','running','succeeded','failed','cancelled','waiting_for_human')",
            name="ck_ai_runs_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_runs_project_id", "ai_runs", ["project_id"])
    op.create_index("ix_ai_runs_status", "ai_runs", ["status"])
    op.create_index("ix_ai_runs_workflow_type", "ai_runs", ["workflow_type"])
    op.create_index("ix_ai_runs_workspace_id", "ai_runs", ["workspace_id"])

    op.create_table(
        "ai_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_steps_ai_run_id", "ai_steps", ["ai_run_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_steps_ai_run_id", table_name="ai_steps")
    op.drop_table("ai_steps")
    op.drop_index("ix_ai_runs_workspace_id", table_name="ai_runs")
    op.drop_index("ix_ai_runs_workflow_type", table_name="ai_runs")
    op.drop_index("ix_ai_runs_status", table_name="ai_runs")
    op.drop_index("ix_ai_runs_project_id", table_name="ai_runs")
    op.drop_table("ai_runs")
