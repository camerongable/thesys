"""add research auto ingestion metadata

Revision ID: 0013_research_auto_ingestion
Revises: 0012_research_discovery
Create Date: 2026-05-25 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0013_research_auto_ingestion"
down_revision = "0012_research_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "discovered_sources",
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "competitor_candidates",
        sa.Column("evidence_source_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "competitor_candidates",
        sa.Column("ingestion_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "competitor_candidates",
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_competitor_candidates_evidence_source_id",
        "competitor_candidates",
        "evidence_sources",
        ["evidence_source_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_competitor_candidates_evidence_source_id",
        "competitor_candidates",
        ["evidence_source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_competitor_candidates_evidence_source_id",
        table_name="competitor_candidates",
    )
    op.drop_constraint(
        "fk_competitor_candidates_evidence_source_id",
        "competitor_candidates",
        type_="foreignkey",
    )
    op.drop_column("competitor_candidates", "ingested_at")
    op.drop_column("competitor_candidates", "ingestion_error")
    op.drop_column("competitor_candidates", "evidence_source_id")
    op.drop_column("discovered_sources", "ingested_at")
