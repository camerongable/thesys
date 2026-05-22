"""add opportunity brief artifacts and strategic records

Revision ID: 0008_opportunity_briefs
Revises: 0007_evidence_retrieval
Create Date: 2026-05-21 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_opportunity_briefs"
down_revision = "0007_evidence_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_type in ("
            "'opportunity_brief','competitor_landscape','validation_plan',"
            "'decision_memo','research_memo','customer_discovery_summary','other'"
            ")",
            name="ck_artifacts_artifact_type",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_artifact_type", "artifacts", ["artifact_type"])
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
    op.create_index("ix_artifacts_workspace_id", "artifacts", ["workspace_id"])

    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        sa.Column("structured_content", sa.JSON(), nullable=False),
        sa.Column("generated_by_ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["generated_by_ai_run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id", "version", name="uq_artifact_versions_artifact_version"),
    )
    op.create_index("ix_artifact_versions_artifact_id", "artifact_versions", ["artifact_id"])
    op.create_index(
        "ix_artifact_versions_generated_by_ai_run_id",
        "artifact_versions",
        ["generated_by_ai_run_id"],
    )
    op.create_index("ix_artifact_versions_workspace_id", "artifact_versions", ["workspace_id"])

    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version_id", sa.Uuid(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=80), nullable=True),
        sa.Column("confidence_score", sa.Numeric(), nullable=True),
        sa.Column("support_level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "support_level in ('supported','partial','unsupported','inference')",
            name="ck_claims_support_level",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"],
            ["artifact_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_artifact_version_id", "claims", ["artifact_version_id"])
    op.create_index("ix_claims_project_id", "claims", ["project_id"])
    op.create_index("ix_claims_workspace_id", "claims", ["workspace_id"])

    op.create_table(
        "claim_evidence_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_source_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("relevance_score", sa.Numeric(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
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
    op.create_index("ix_claim_evidence_links_claim_id", "claim_evidence_links", ["claim_id"])
    op.create_index(
        "ix_claim_evidence_links_evidence_chunk_id",
        "claim_evidence_links",
        ["evidence_chunk_id"],
    )
    op.create_index(
        "ix_claim_evidence_links_evidence_source_id",
        "claim_evidence_links",
        ["evidence_source_id"],
    )

    op.create_table(
        "assumptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("importance", sa.String(length=20), nullable=False),
        sa.Column("uncertainty", sa.String(length=20), nullable=False),
        sa.Column("kill_risk", sa.Boolean(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recommended_test", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "importance in ('low','medium','high','critical')",
            name="ck_assumptions_importance",
        ),
        sa.CheckConstraint(
            "uncertainty in ('low','medium','high')",
            name="ck_assumptions_uncertainty",
        ),
        sa.CheckConstraint(
            "status in ('untested','testing','validated','invalidated','inconclusive')",
            name="ck_assumptions_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assumptions_project_id", "assumptions", ["project_id"])
    op.create_index("ix_assumptions_workspace_id", "assumptions", ["workspace_id"])

    op.create_table(
        "risks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("likelihood", sa.String(length=20), nullable=False),
        sa.Column("mitigation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "severity in ('low','medium','high','critical')",
            name="ck_risks_severity",
        ),
        sa.CheckConstraint(
            "likelihood in ('low','medium','high','unknown')",
            name="ck_risks_likelihood",
        ),
        sa.CheckConstraint(
            "status in ('open','mitigated','accepted','closed')",
            name="ck_risks_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risks_project_id", "risks", ["project_id"])
    op.create_index("ix_risks_workspace_id", "risks", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_risks_workspace_id", table_name="risks")
    op.drop_index("ix_risks_project_id", table_name="risks")
    op.drop_table("risks")
    op.drop_index("ix_assumptions_workspace_id", table_name="assumptions")
    op.drop_index("ix_assumptions_project_id", table_name="assumptions")
    op.drop_table("assumptions")
    op.drop_index("ix_claim_evidence_links_evidence_source_id", table_name="claim_evidence_links")
    op.drop_index("ix_claim_evidence_links_evidence_chunk_id", table_name="claim_evidence_links")
    op.drop_index("ix_claim_evidence_links_claim_id", table_name="claim_evidence_links")
    op.drop_table("claim_evidence_links")
    op.drop_index("ix_claims_workspace_id", table_name="claims")
    op.drop_index("ix_claims_project_id", table_name="claims")
    op.drop_index("ix_claims_artifact_version_id", table_name="claims")
    op.drop_table("claims")
    op.drop_index("ix_artifact_versions_workspace_id", table_name="artifact_versions")
    op.drop_index(
        "ix_artifact_versions_generated_by_ai_run_id",
        table_name="artifact_versions",
    )
    op.drop_index("ix_artifact_versions_artifact_id", table_name="artifact_versions")
    op.drop_table("artifact_versions")
    op.drop_index("ix_artifacts_workspace_id", table_name="artifacts")
    op.drop_index("ix_artifacts_project_id", table_name="artifacts")
    op.drop_index("ix_artifacts_artifact_type", table_name="artifacts")
    op.drop_table("artifacts")
