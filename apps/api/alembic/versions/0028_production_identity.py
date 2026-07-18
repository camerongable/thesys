"""add production identity account status

Revision ID: 0028_production_identity
Revises: 0027_ai_cache_entries
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0028_production_identity"
down_revision = "0027_ai_cache_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_status",
        "users",
        "status in ('active','disabled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.drop_column("users", "status")
