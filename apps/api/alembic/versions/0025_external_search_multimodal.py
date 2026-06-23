"""add external search and multimodal evidence metadata

Revision ID: 0025_external_search_multimodal
Revises: 0024_embedding_metadata
Create Date: 2026-06-22 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0025_external_search_multimodal"
down_revision = "0024_embedding_metadata"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "evidence_sources",
        sa.Column("source_metadata", _json_type(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.add_column("discovered_sources", sa.Column("search_provider", sa.String(length=50)))
    op.add_column("discovered_sources", sa.Column("search_query", sa.Text()))
    op.add_column("discovered_sources", sa.Column("search_result_rank", sa.Integer()))
    op.add_column("discovered_sources", sa.Column("retrieved_at", sa.DateTime(timezone=True)))
    op.add_column(
        "discovered_sources",
        sa.Column("risk_level", sa.String(length=20), nullable=False, server_default="medium"),
    )
    op.add_column(
        "discovered_sources",
        sa.Column(
            "provenance_metadata",
            _json_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_index(
        "ix_discovered_sources_search_provider",
        "discovered_sources",
        ["search_provider"],
    )
    op.create_index(
        "ix_discovered_sources_search_result_rank",
        "discovered_sources",
        ["search_result_rank"],
    )
    op.create_index("ix_discovered_sources_retrieved_at", "discovered_sources", ["retrieved_at"])


def downgrade() -> None:
    op.drop_index("ix_discovered_sources_retrieved_at", table_name="discovered_sources")
    op.drop_index("ix_discovered_sources_search_result_rank", table_name="discovered_sources")
    op.drop_index("ix_discovered_sources_search_provider", table_name="discovered_sources")
    op.drop_column("discovered_sources", "provenance_metadata")
    op.drop_column("discovered_sources", "risk_level")
    op.drop_column("discovered_sources", "retrieved_at")
    op.drop_column("discovered_sources", "search_result_rank")
    op.drop_column("discovered_sources", "search_query")
    op.drop_column("discovered_sources", "search_provider")
    op.drop_column("evidence_sources", "source_metadata")
