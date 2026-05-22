"""add competitor analysis records

Revision ID: 0009_competitors
Revises: 0008_opportunity_briefs
Create Date: 2026-05-21 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_competitors"
down_revision = "0008_opportunity_briefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competitors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=True),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("pricing_summary", sa.Text(), nullable=True),
        sa.Column("key_features", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("weaknesses", sa.Text(), nullable=True),
        sa.Column("differentiation_notes", sa.Text(), nullable=True),
        sa.Column("threat_level", sa.String(length=20), nullable=False),
        sa.Column("watchlist_status", sa.String(length=30), nullable=False),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category in ("
            "'direct','adjacent','incumbent','substitute','manual_alternative','unknown'"
            ")",
            name="ck_competitors_category",
        ),
        sa.CheckConstraint(
            "threat_level in ('low','medium','high','unknown')",
            name="ck_competitors_threat_level",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competitors_project_id", "competitors", ["project_id"])
    op.create_index("ix_competitors_workspace_id", "competitors", ["workspace_id"])

    op.create_table(
        "competitor_evidence_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("competitor_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_source_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"], ondelete="CASCADE"),
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
        "ix_competitor_evidence_links_competitor_id",
        "competitor_evidence_links",
        ["competitor_id"],
    )
    op.create_index(
        "ix_competitor_evidence_links_evidence_chunk_id",
        "competitor_evidence_links",
        ["evidence_chunk_id"],
    )
    op.create_index(
        "ix_competitor_evidence_links_evidence_source_id",
        "competitor_evidence_links",
        ["evidence_source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_competitor_evidence_links_evidence_source_id",
        table_name="competitor_evidence_links",
    )
    op.drop_index(
        "ix_competitor_evidence_links_evidence_chunk_id",
        table_name="competitor_evidence_links",
    )
    op.drop_index(
        "ix_competitor_evidence_links_competitor_id",
        table_name="competitor_evidence_links",
    )
    op.drop_table("competitor_evidence_links")
    op.drop_index("ix_competitors_workspace_id", table_name="competitors")
    op.drop_index("ix_competitors_project_id", table_name="competitors")
    op.drop_table("competitors")
