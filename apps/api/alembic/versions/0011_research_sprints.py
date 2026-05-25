"""add research sprint planning tables

Revision ID: 0011_research_sprints
Revises: 0010_validation_decisions
Create Date: 2026-05-25 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011_research_sprints"
down_revision = "0010_validation_decisions"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "research_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("target_customer_hypotheses", _json_type(), nullable=False),
        sa.Column("research_questions", _json_type(), nullable=False),
        sa.Column("competitor_queries", _json_type(), nullable=False),
        sa.Column("market_queries", _json_type(), nullable=False),
        sa.Column("substitute_queries", _json_type(), nullable=False),
        sa.Column("source_types", _json_type(), nullable=False),
        sa.Column("assumptions_to_test", _json_type(), nullable=False),
        sa.Column("expected_outputs", _json_type(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('draft','approved','rejected','completed')",
            name="ck_research_plans_status",
        ),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_plans_ai_run_id", "research_plans", ["ai_run_id"])
    op.create_index("ix_research_plans_project_id", "research_plans", ["project_id"])
    op.create_index("ix_research_plans_status", "research_plans", ["status"])
    op.create_index("ix_research_plans_workspace_id", "research_plans", ["workspace_id"])

    op.create_table(
        "research_sprints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("research_plan_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ("
            "'planned','approved','running','needs_review','completed','failed','rejected'"
            ")",
            name="ck_research_sprints_status",
        ),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_plan_id"], ["research_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_sprints_ai_run_id", "research_sprints", ["ai_run_id"])
    op.create_index("ix_research_sprints_project_id", "research_sprints", ["project_id"])
    op.create_index(
        "ix_research_sprints_research_plan_id",
        "research_sprints",
        ["research_plan_id"],
    )
    op.create_index("ix_research_sprints_status", "research_sprints", ["status"])
    op.create_index("ix_research_sprints_workspace_id", "research_sprints", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_research_sprints_workspace_id", table_name="research_sprints")
    op.drop_index("ix_research_sprints_status", table_name="research_sprints")
    op.drop_index("ix_research_sprints_research_plan_id", table_name="research_sprints")
    op.drop_index("ix_research_sprints_project_id", table_name="research_sprints")
    op.drop_index("ix_research_sprints_ai_run_id", table_name="research_sprints")
    op.drop_table("research_sprints")
    op.drop_index("ix_research_plans_workspace_id", table_name="research_plans")
    op.drop_index("ix_research_plans_status", table_name="research_plans")
    op.drop_index("ix_research_plans_project_id", table_name="research_plans")
    op.drop_index("ix_research_plans_ai_run_id", table_name="research_plans")
    op.drop_table("research_plans")
