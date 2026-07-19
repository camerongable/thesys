"""add durable research sprint workflow budgets

Revision ID: 0045_workflow_budgets
Revises: 0044_security_alerts
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0045_workflow_budgets"
down_revision = "0044_security_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_sprints",
        sa.Column(
            "workflow_security_budget",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column("research_sprints", "workflow_security_budget", server_default=None)


def downgrade() -> None:
    op.drop_column("research_sprints", "workflow_security_budget")
