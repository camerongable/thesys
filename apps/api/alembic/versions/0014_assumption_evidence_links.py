"""add assumption evidence links

Revision ID: 0014_assumption_evidence_links
Revises: 0013_research_auto_ingestion
Create Date: 2026-05-25 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0014_assumption_evidence_links"
down_revision = "0013_research_auto_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assumption_evidence_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assumption_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_source_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("relevance_score", sa.Numeric(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assumption_id"],
            ["assumptions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_chunk_id"],
            ["evidence_chunks.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_source_id"],
            ["evidence_sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assumption_evidence_links_assumption_id",
        "assumption_evidence_links",
        ["assumption_id"],
    )
    op.create_index(
        "ix_assumption_evidence_links_evidence_chunk_id",
        "assumption_evidence_links",
        ["evidence_chunk_id"],
    )
    op.create_index(
        "ix_assumption_evidence_links_evidence_source_id",
        "assumption_evidence_links",
        ["evidence_source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assumption_evidence_links_evidence_source_id",
        table_name="assumption_evidence_links",
    )
    op.drop_index(
        "ix_assumption_evidence_links_evidence_chunk_id",
        table_name="assumption_evidence_links",
    )
    op.drop_index(
        "ix_assumption_evidence_links_assumption_id",
        table_name="assumption_evidence_links",
    )
    op.drop_table("assumption_evidence_links")
