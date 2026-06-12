"""add langsmith observability fields

Revision ID: 0015_langsmith_observability
Revises: 0014_assumption_evidence_links
Create Date: 2026-06-11 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0015_langsmith_observability"
down_revision = "0014_assumption_evidence_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_runs", sa.Column("langsmith_trace_id", sa.String(length=100), nullable=True))
    op.add_column("ai_runs", sa.Column("langsmith_trace_url", sa.Text(), nullable=True))
    op.create_index("ix_ai_runs_langsmith_trace_id", "ai_runs", ["langsmith_trace_id"])

    op.add_column("ai_steps", sa.Column("langsmith_trace_id", sa.String(length=100), nullable=True))
    op.add_column("ai_steps", sa.Column("langsmith_run_id", sa.String(length=100), nullable=True))
    op.add_column("ai_steps", sa.Column("langsmith_trace_url", sa.Text(), nullable=True))
    op.create_index("ix_ai_steps_langsmith_trace_id", "ai_steps", ["langsmith_trace_id"])
    op.create_index("ix_ai_steps_langsmith_run_id", "ai_steps", ["langsmith_run_id"])

    op.add_column(
        "research_sprints",
        sa.Column("langsmith_trace_id", sa.String(length=100), nullable=True),
    )
    op.add_column("research_sprints", sa.Column("langsmith_trace_url", sa.Text(), nullable=True))
    op.create_index(
        "ix_research_sprints_langsmith_trace_id",
        "research_sprints",
        ["langsmith_trace_id"],
    )

    op.add_column(
        "artifact_versions",
        sa.Column("langsmith_trace_id", sa.String(length=100), nullable=True),
    )
    op.add_column("artifact_versions", sa.Column("langsmith_trace_url", sa.Text(), nullable=True))
    op.create_index(
        "ix_artifact_versions_langsmith_trace_id",
        "artifact_versions",
        ["langsmith_trace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_versions_langsmith_trace_id", table_name="artifact_versions")
    op.drop_column("artifact_versions", "langsmith_trace_url")
    op.drop_column("artifact_versions", "langsmith_trace_id")

    op.drop_index("ix_research_sprints_langsmith_trace_id", table_name="research_sprints")
    op.drop_column("research_sprints", "langsmith_trace_url")
    op.drop_column("research_sprints", "langsmith_trace_id")

    op.drop_index("ix_ai_steps_langsmith_run_id", table_name="ai_steps")
    op.drop_index("ix_ai_steps_langsmith_trace_id", table_name="ai_steps")
    op.drop_column("ai_steps", "langsmith_trace_url")
    op.drop_column("ai_steps", "langsmith_run_id")
    op.drop_column("ai_steps", "langsmith_trace_id")

    op.drop_index("ix_ai_runs_langsmith_trace_id", table_name="ai_runs")
    op.drop_column("ai_runs", "langsmith_trace_url")
    op.drop_column("ai_runs", "langsmith_trace_id")
