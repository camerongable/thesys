"""add expiry to encrypted PII token mappings

Revision ID: 0035_pii_token_mapping_retention
Revises: 0034_pii_token_mappings
Create Date: 2026-07-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0035_pii_token_mapping_retention"
down_revision = "0034_pii_token_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pii_token_mappings",
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE pii_token_mappings "
        "SET retention_expires_at = created_at + INTERVAL '30 days' "
        "WHERE retention_expires_at IS NULL"
    )
    op.alter_column("pii_token_mappings", "retention_expires_at", nullable=False)
    op.create_index(
        "ix_pii_token_mappings_retention_expires_at",
        "pii_token_mappings",
        ["retention_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pii_token_mappings_retention_expires_at", table_name="pii_token_mappings")
    op.drop_column("pii_token_mappings", "retention_expires_at")
