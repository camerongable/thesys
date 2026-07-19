"""add durable research sprint workflow usage

Revision ID: 0046_research_sprint_workflow_usage
Revises: 0045_research_sprint_workflow_budgets
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0046_research_sprint_workflow_usage"
down_revision = "0045_research_sprint_workflow_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_sprints",
        sa.Column(
            "workflow_security_usage",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column("research_sprints", "workflow_security_usage", server_default=None)


def downgrade() -> None:
    op.drop_column("research_sprints", "workflow_security_usage")
