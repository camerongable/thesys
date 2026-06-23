"""add embedding metadata and pgvector retrieval index

Revision ID: 0024_embedding_metadata
Revises: 0023_project_nudges
Create Date: 2026-06-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0024_embedding_metadata"
down_revision = "0023_project_nudges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evidence_chunks", sa.Column("embedding_provider", sa.String(length=50)))
    op.add_column("evidence_chunks", sa.Column("embedding_model", sa.String(length=255)))
    op.add_column("evidence_chunks", sa.Column("embedding_dimension", sa.Integer()))
    op.add_column("evidence_chunks", sa.Column("embedding_version", sa.String(length=100)))
    op.add_column("evidence_chunks", sa.Column("embedded_at", sa.DateTime(timezone=True)))
    op.add_column("evidence_chunks", sa.Column("embedding_error", sa.Text()))
    op.create_index(
        "ix_evidence_chunks_embedding_provider",
        "evidence_chunks",
        ["embedding_provider"],
    )
    op.create_index(
        "ix_evidence_chunks_embedding_model",
        "evidence_chunks",
        ["embedding_model"],
    )
    op.create_index("ix_evidence_chunks_embedded_at", "evidence_chunks", ["embedded_at"])

    op.execute(
        """
        DO $$
        BEGIN
            BEGIN
                CREATE INDEX IF NOT EXISTS ix_evidence_chunks_embedding_hnsw
                ON evidence_chunks
                USING hnsw (embedding vector_cosine_ops);
            EXCEPTION
                WHEN undefined_object OR feature_not_supported OR invalid_parameter_value THEN
                    CREATE INDEX IF NOT EXISTS ix_evidence_chunks_embedding_ivfflat
                    ON evidence_chunks
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
            END;
        END $$;
        """
    )

    op.execute(
        """
        UPDATE evidence_chunks
        SET
            embedding_provider = COALESCE(metadata ->> 'embedding_provider', 'deterministic'),
            embedding_model = COALESCE(
                metadata ->> 'embedding_model',
                'deterministic-hash-embedding-1536'
            ),
            embedding_dimension = 1536,
            embedding_version = COALESCE(metadata ->> 'embedding_version', 'v1'),
            embedded_at = created_at
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_embedding_ivfflat")
    op.drop_index("ix_evidence_chunks_embedded_at", table_name="evidence_chunks")
    op.drop_index("ix_evidence_chunks_embedding_model", table_name="evidence_chunks")
    op.drop_index("ix_evidence_chunks_embedding_provider", table_name="evidence_chunks")
    op.drop_column("evidence_chunks", "embedding_error")
    op.drop_column("evidence_chunks", "embedded_at")
    op.drop_column("evidence_chunks", "embedding_version")
    op.drop_column("evidence_chunks", "embedding_dimension")
    op.drop_column("evidence_chunks", "embedding_model")
    op.drop_column("evidence_chunks", "embedding_provider")
