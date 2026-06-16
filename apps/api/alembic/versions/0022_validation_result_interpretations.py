"""add validation result interpretations

Revision ID: 0022_validation_interp
Revises: 0021_validation_missions
Create Date: 2026-06-15 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0022_validation_interp"
down_revision = "0021_validation_missions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_result_interpretations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=True),
        sa.Column("assumption_id", sa.Uuid(), nullable=True),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("approval_request_id", sa.Uuid(), nullable=True),
        sa.Column("raw_notes", sa.Text(), nullable=False),
        sa.Column("signal_summary", sa.Text(), nullable=False),
        sa.Column("what_strengthened", sa.JSON(), nullable=False),
        sa.Column("what_weakened", sa.JSON(), nullable=False),
        sa.Column("pain_severity", sa.String(length=20), nullable=False),
        sa.Column("current_workaround", sa.Text(), nullable=False),
        sa.Column("urgency", sa.String(length=20), nullable=False),
        sa.Column("willingness_to_pay", sa.String(length=20), nullable=False),
        sa.Column("switching_signal", sa.String(length=20), nullable=False),
        sa.Column("objections", sa.JSON(), nullable=False),
        sa.Column("quotes", sa.JSON(), nullable=False),
        sa.Column("confidence_change", sa.String(length=20), nullable=False),
        sa.Column("confidence_rationale", sa.Text(), nullable=False),
        sa.Column("recommended_next_action", sa.Text(), nullable=False),
        sa.Column("decision_recommendation", sa.String(length=40), nullable=False),
        sa.Column("proposed_confidence_delta", sa.Numeric(), nullable=False),
        sa.Column("proposed_assumption_status", sa.String(length=30), nullable=True),
        sa.Column("proposed_updates", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "pain_severity in ('none','low','medium','high')",
            name="ck_validation_result_interpretations_pain_severity",
        ),
        sa.CheckConstraint(
            "urgency in ('low','medium','high')",
            name="ck_validation_result_interpretations_urgency",
        ),
        sa.CheckConstraint(
            "willingness_to_pay in ('none','weak','medium','strong')",
            name="ck_validation_result_interpretations_willingness_to_pay",
        ),
        sa.CheckConstraint(
            "switching_signal in ('none','weak','medium','strong')",
            name="ck_validation_result_interpretations_switching_signal",
        ),
        sa.CheckConstraint(
            "confidence_change in ('decrease','no_change','increase')",
            name="ck_validation_result_interpretations_confidence_change",
        ),
        sa.CheckConstraint(
            "decision_recommendation in "
            "('proceed','pivot','pause','kill','continue_research')",
            name="ck_validation_result_interpretations_decision_recommendation",
        ),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["approval_request_id"],
            ["approval_requests.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["assumption_id"], ["assumptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["validation_missions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_validation_result_interpretations_ai_run_id",
        "validation_result_interpretations",
        ["ai_run_id"],
    )
    op.create_index(
        "ix_validation_result_interpretations_approval_request_id",
        "validation_result_interpretations",
        ["approval_request_id"],
    )
    op.create_index(
        "ix_validation_result_interpretations_assumption_id",
        "validation_result_interpretations",
        ["assumption_id"],
    )
    op.create_index(
        "ix_validation_result_interpretations_experiment_id",
        "validation_result_interpretations",
        ["experiment_id"],
    )
    op.create_index(
        "ix_validation_result_interpretations_mission_id",
        "validation_result_interpretations",
        ["mission_id"],
    )
    op.create_index(
        "ix_validation_result_interpretations_project_id",
        "validation_result_interpretations",
        ["project_id"],
    )
    op.create_index(
        "ix_validation_result_interpretations_workspace_id",
        "validation_result_interpretations",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_validation_result_interpretations_workspace_id",
        table_name="validation_result_interpretations",
    )
    op.drop_index(
        "ix_validation_result_interpretations_project_id",
        table_name="validation_result_interpretations",
    )
    op.drop_index(
        "ix_validation_result_interpretations_mission_id",
        table_name="validation_result_interpretations",
    )
    op.drop_index(
        "ix_validation_result_interpretations_experiment_id",
        table_name="validation_result_interpretations",
    )
    op.drop_index(
        "ix_validation_result_interpretations_assumption_id",
        table_name="validation_result_interpretations",
    )
    op.drop_index(
        "ix_validation_result_interpretations_approval_request_id",
        table_name="validation_result_interpretations",
    )
    op.drop_index(
        "ix_validation_result_interpretations_ai_run_id",
        table_name="validation_result_interpretations",
    )
    op.drop_table("validation_result_interpretations")
