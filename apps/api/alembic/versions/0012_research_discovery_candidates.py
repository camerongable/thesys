"""add research discovery candidate tables

Revision ID: 0012_research_discovery
Revises: 0011_research_sprints
Create Date: 2026-05-25 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_research_discovery"
down_revision = "0011_research_sprints"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "discovered_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("research_sprint_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_source_id", sa.Uuid(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("relevance_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("reason_selected", sa.Text(), nullable=False),
        sa.Column("associated_research_question", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type in ("
            "'company_site','pricing_page','product_page','review','forum','blog',"
            "'market_report','directory','docs','unknown'"
            ")",
            name="ck_discovered_sources_source_type",
        ),
        sa.CheckConstraint(
            "status in ('candidate','approved','rejected','ingested','failed')",
            name="ck_discovered_sources_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["evidence_source_id"],
            ["evidence_sources.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["research_sprint_id"],
            ["research_sprints.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_discovered_sources_evidence_source_id",
        "discovered_sources",
        ["evidence_source_id"],
    )
    op.create_index("ix_discovered_sources_project_id", "discovered_sources", ["project_id"])
    op.create_index(
        "ix_discovered_sources_research_sprint_id",
        "discovered_sources",
        ["research_sprint_id"],
    )
    op.create_index("ix_discovered_sources_status", "discovered_sources", ["status"])
    op.create_index("ix_discovered_sources_workspace_id", "discovered_sources", ["workspace_id"])

    op.create_table(
        "competitor_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("research_sprint_id", sa.Uuid(), nullable=False),
        sa.Column("competitor_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=True),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("pricing_signal", sa.Text(), nullable=True),
        sa.Column("core_features", _json_type(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("threat_level", sa.String(length=20), nullable=False),
        sa.Column("relevance_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("source_ids", _json_type(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category in ("
            "'direct_competitor','indirect_competitor','substitute_behavior',"
            "'incumbent_platform','adjacent_solution','irrelevant'"
            ")",
            name="ck_competitor_candidates_category",
        ),
        sa.CheckConstraint(
            "threat_level in ('low','medium','high')",
            name="ck_competitor_candidates_threat_level",
        ),
        sa.CheckConstraint(
            "status in ('candidate','approved','rejected','merged')",
            name="ck_competitor_candidates_status",
        ),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["research_sprint_id"],
            ["research_sprints.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_competitor_candidates_competitor_id",
        "competitor_candidates",
        ["competitor_id"],
    )
    op.create_index(
        "ix_competitor_candidates_project_id",
        "competitor_candidates",
        ["project_id"],
    )
    op.create_index(
        "ix_competitor_candidates_research_sprint_id",
        "competitor_candidates",
        ["research_sprint_id"],
    )
    op.create_index("ix_competitor_candidates_status", "competitor_candidates", ["status"])
    op.create_index(
        "ix_competitor_candidates_workspace_id",
        "competitor_candidates",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_competitor_candidates_workspace_id", table_name="competitor_candidates")
    op.drop_index("ix_competitor_candidates_status", table_name="competitor_candidates")
    op.drop_index(
        "ix_competitor_candidates_research_sprint_id",
        table_name="competitor_candidates",
    )
    op.drop_index("ix_competitor_candidates_project_id", table_name="competitor_candidates")
    op.drop_index("ix_competitor_candidates_competitor_id", table_name="competitor_candidates")
    op.drop_table("competitor_candidates")

    op.drop_index("ix_discovered_sources_workspace_id", table_name="discovered_sources")
    op.drop_index("ix_discovered_sources_status", table_name="discovered_sources")
    op.drop_index("ix_discovered_sources_research_sprint_id", table_name="discovered_sources")
    op.drop_index("ix_discovered_sources_project_id", table_name="discovered_sources")
    op.drop_index("ix_discovered_sources_evidence_source_id", table_name="discovered_sources")
    op.drop_table("discovered_sources")
