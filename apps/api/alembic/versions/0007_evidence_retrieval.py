"""add evidence sources and chunks

Revision ID: 0007_evidence_retrieval
Revises: 0006_structured_intake
Create Date: 2026-05-20 00:00:00.000000
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0007_evidence_retrieval"
down_revision = "0006_structured_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("object_storage_key", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("classification", sa.String(length=100), nullable=True),
        sa.Column("credibility_score", sa.Numeric(), nullable=True),
        sa.Column("ingestion_status", sa.String(length=20), nullable=False),
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type in ('url','file','note','transcript','manual')",
            name="ck_evidence_sources_source_type",
        ),
        sa.CheckConstraint(
            "ingestion_status in ('pending','processing','ready','failed')",
            name="ck_evidence_sources_ingestion_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evidence_sources_classification",
        "evidence_sources",
        ["classification"],
    )
    op.create_index("ix_evidence_sources_ingested_at", "evidence_sources", ["ingested_at"])
    op.create_index("ix_evidence_sources_project_id", "evidence_sources", ["project_id"])
    op.create_index("ix_evidence_sources_source_date", "evidence_sources", ["source_date"])
    op.create_index("ix_evidence_sources_source_type", "evidence_sources", ["source_type"])
    op.create_index("ix_evidence_sources_workspace_id", "evidence_sources", ["workspace_id"])

    op.create_table(
        "evidence_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["evidence_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_chunks_project_id", "evidence_chunks", ["project_id"])
    op.create_index("ix_evidence_chunks_source_id", "evidence_chunks", ["source_id"])
    op.create_index("ix_evidence_chunks_workspace_id", "evidence_chunks", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_chunks_workspace_id", table_name="evidence_chunks")
    op.drop_index("ix_evidence_chunks_source_id", table_name="evidence_chunks")
    op.drop_index("ix_evidence_chunks_project_id", table_name="evidence_chunks")
    op.drop_table("evidence_chunks")
    op.drop_index("ix_evidence_sources_workspace_id", table_name="evidence_sources")
    op.drop_index("ix_evidence_sources_source_type", table_name="evidence_sources")
    op.drop_index("ix_evidence_sources_source_date", table_name="evidence_sources")
    op.drop_index("ix_evidence_sources_project_id", table_name="evidence_sources")
    op.drop_index("ix_evidence_sources_ingested_at", table_name="evidence_sources")
    op.drop_index("ix_evidence_sources_classification", table_name="evidence_sources")
    op.drop_table("evidence_sources")
