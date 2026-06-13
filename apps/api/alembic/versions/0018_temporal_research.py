"""add temporal research sprint execution metadata

Revision ID: 0018_temporal_research
Revises: 0017_security_governance
Create Date: 2026-06-12 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0018_temporal_research"
down_revision = "0017_security_governance"
branch_labels = None
depends_on = None


NEW_STATUS_CHECK = (
    "status in ("
    "'planned','waiting_for_approval','approved','running','needs_review',"
    "'waiting_for_memory_approval','completed','failed','cancelled','rejected'"
    ")"
)
OLD_STATUS_CHECK = (
    "status in ('planned','approved','running','needs_review','completed','failed','rejected')"
)


def upgrade() -> None:
    op.add_column("research_sprints", sa.Column("temporal_workflow_id", sa.String(length=255), nullable=True))
    op.add_column("research_sprints", sa.Column("temporal_run_id", sa.String(length=255), nullable=True))
    op.add_column("research_sprints", sa.Column("current_step", sa.String(length=120), nullable=True))
    op.add_column("research_sprints", sa.Column("failed_step", sa.String(length=120), nullable=True))
    op.add_column("research_sprints", sa.Column("failure_message", sa.Text(), nullable=True))
    op.create_index(
        "ix_research_sprints_temporal_workflow_id",
        "research_sprints",
        ["temporal_workflow_id"],
    )
    op.create_index(
        "ix_research_sprints_temporal_run_id",
        "research_sprints",
        ["temporal_run_id"],
    )
    op.create_index("ix_research_sprints_current_step", "research_sprints", ["current_step"])
    op.drop_constraint("ck_research_sprints_status", "research_sprints", type_="check")
    op.create_check_constraint(
        "ck_research_sprints_status",
        "research_sprints",
        NEW_STATUS_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("ck_research_sprints_status", "research_sprints", type_="check")
    op.execute("UPDATE research_sprints SET status = 'needs_review' WHERE status = 'waiting_for_memory_approval'")
    op.execute("UPDATE research_sprints SET status = 'planned' WHERE status = 'waiting_for_approval'")
    op.execute("UPDATE research_sprints SET status = 'failed' WHERE status = 'cancelled'")
    op.create_check_constraint(
        "ck_research_sprints_status",
        "research_sprints",
        OLD_STATUS_CHECK,
    )
    op.drop_index("ix_research_sprints_current_step", table_name="research_sprints")
    op.drop_index("ix_research_sprints_temporal_run_id", table_name="research_sprints")
    op.drop_index("ix_research_sprints_temporal_workflow_id", table_name="research_sprints")
    op.drop_column("research_sprints", "failure_message")
    op.drop_column("research_sprints", "failed_step")
    op.drop_column("research_sprints", "current_step")
    op.drop_column("research_sprints", "temporal_run_id")
    op.drop_column("research_sprints", "temporal_workflow_id")
