"""add validation experiments and decisions

Revision ID: 0010_validation_decisions
Revises: 0009_competitors
Create Date: 2026-05-22 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0010_validation_decisions"
down_revision = "0009_competitors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("assumption_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=120), nullable=True),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("success_criteria", sa.Text(), nullable=True),
        sa.Column("failure_threshold", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('planned','running','completed','cancelled')",
            name="ck_experiments_status",
        ),
        sa.ForeignKeyConstraint(["assumption_id"], ["assumptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiments_assumption_id", "experiments", ["assumption_id"])
    op.create_index("ix_experiments_project_id", "experiments", ["project_id"])
    op.create_index("ix_experiments_workspace_id", "experiments", ["workspace_id"])

    op.create_table(
        "experiment_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("confidence_delta", sa.Numeric(), nullable=True),
        sa.Column("raw_notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome in ('positive','negative','mixed','inconclusive')",
            name="ck_experiment_results_outcome",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiment_results_experiment_id", "experiment_results", ["experiment_id"])
    op.create_index("ix_experiment_results_project_id", "experiment_results", ["project_id"])
    op.create_index("ix_experiment_results_workspace_id", "experiment_results", ["workspace_id"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("decision_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision_type in ("
            "'build','pivot','pause','kill','change_icp','change_positioning',"
            "'run_experiment','other'"
            ")",
            name="ck_decisions_decision_type",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decisions_project_id", "decisions", ["project_id"])
    op.create_index("ix_decisions_workspace_id", "decisions", ["workspace_id"])

    op.create_table(
        "decision_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("linked_type", sa.String(length=40), nullable=False),
        sa.Column("linked_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "linked_type in ('evidence','assumption','risk','artifact','competitor','experiment')",
            name="ck_decision_links_linked_type",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decision_links_decision_id", "decision_links", ["decision_id"])


def downgrade() -> None:
    op.drop_index("ix_decision_links_decision_id", table_name="decision_links")
    op.drop_table("decision_links")
    op.drop_index("ix_decisions_workspace_id", table_name="decisions")
    op.drop_index("ix_decisions_project_id", table_name="decisions")
    op.drop_table("decisions")
    op.drop_index("ix_experiment_results_workspace_id", table_name="experiment_results")
    op.drop_index("ix_experiment_results_project_id", table_name="experiment_results")
    op.drop_index("ix_experiment_results_experiment_id", table_name="experiment_results")
    op.drop_table("experiment_results")
    op.drop_index("ix_experiments_workspace_id", table_name="experiments")
    op.drop_index("ix_experiments_project_id", table_name="experiments")
    op.drop_index("ix_experiments_assumption_id", table_name="experiments")
    op.drop_table("experiments")
