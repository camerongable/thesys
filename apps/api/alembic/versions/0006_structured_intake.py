"""add structured intake project objects

Revision ID: 0006_structured_intake
Revises: 0005_ai_runs_steps
Create Date: 2026-05-20 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_structured_intake"
down_revision = "0005_ai_runs_steps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_intakes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("one_sentence_summary", sa.Text(), nullable=False),
        sa.Column("target_users", sa.JSON(), nullable=False),
        sa.Column("buyer_type", sa.String(length=20), nullable=False),
        sa.Column("problem_hypotheses", sa.JSON(), nullable=False),
        sa.Column("proposed_solution", sa.Text(), nullable=False),
        sa.Column("market_category", sa.String(length=255), nullable=True),
        sa.Column("business_model_guess", sa.String(length=255), nullable=True),
        sa.Column("suspected_competitors", sa.JSON(), nullable=False),
        sa.Column("key_uncertainties", sa.JSON(), nullable=False),
        sa.Column("clarifying_questions", sa.JSON(), nullable=False),
        sa.Column("user_answers", sa.JSON(), nullable=False),
        sa.Column("raw_idea", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "buyer_type in ('consumer','prosumer','smb','midmarket','enterprise','unknown')",
            name="ck_project_intakes_buyer_type",
        ),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_intakes_ai_run_id", "project_intakes", ["ai_run_id"])
    op.create_index("ix_project_intakes_project_id", "project_intakes", ["project_id"])
    op.create_index("ix_project_intakes_workspace_id", "project_intakes", ["workspace_id"])

    op.create_table(
        "customer_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("buyer_type", sa.String(length=20), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("confidence_score", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "buyer_type in ('consumer','prosumer','smb','midmarket','enterprise','unknown')",
            name="ck_customer_segments_buyer_type",
        ),
        sa.CheckConstraint(
            "priority in ('primary','secondary','rejected','unknown')",
            name="ck_customer_segments_priority",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_segments_project_id", "customer_segments", ["project_id"])
    op.create_index("ix_customer_segments_workspace_id", "customer_segments", ["workspace_id"])

    op.create_table(
        "problems",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("segment_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("frequency", sa.Text(), nullable=True),
        sa.Column("current_alternatives", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "severity in ('low','medium','high','critical','unknown')",
            name="ck_problems_severity",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["customer_segments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_problems_project_id", "problems", ["project_id"])
    op.create_index("ix_problems_segment_id", "problems", ["segment_id"])
    op.create_index("ix_problems_workspace_id", "problems", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_problems_workspace_id", table_name="problems")
    op.drop_index("ix_problems_segment_id", table_name="problems")
    op.drop_index("ix_problems_project_id", table_name="problems")
    op.drop_table("problems")
    op.drop_index("ix_customer_segments_workspace_id", table_name="customer_segments")
    op.drop_index("ix_customer_segments_project_id", table_name="customer_segments")
    op.drop_table("customer_segments")
    op.drop_index("ix_project_intakes_workspace_id", table_name="project_intakes")
    op.drop_index("ix_project_intakes_project_id", table_name="project_intakes")
    op.drop_index("ix_project_intakes_ai_run_id", table_name="project_intakes")
    op.drop_table("project_intakes")
