"""add project memory index

Revision ID: 0026_project_memory_items
Revises: 0025_external_search_multimodal
Create Date: 2026-06-27 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0026_project_memory_items"
down_revision = "0025_external_search_multimodal"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "project_memory_items",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("memory_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("write_policy", sa.String(length=30), nullable=False),
        sa.Column("entity_type", sa.String(length=80)),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("source_entity_type", sa.String(length=80)),
        sa.Column("source_entity_id", sa.Uuid()),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content", _json_type(), nullable=False),
        sa.Column("provenance_metadata", _json_type(), nullable=False),
        sa.Column("confidence_score", sa.Numeric()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_by_id", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "memory_type in ('working','episodic','semantic','project','procedural','preference')",
            name="ck_project_memory_items_memory_type",
        ),
        sa.CheckConstraint(
            "status in ('active','stale','archived','superseded','proposed')",
            name="ck_project_memory_items_status",
        ),
        sa.CheckConstraint(
            "write_policy in ('direct','approval_required','derived_read_only','transient')",
            name="ck_project_memory_items_write_policy",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["project_memory_items.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "workspace_id",
        "project_id",
        "memory_type",
        "status",
        "write_policy",
        "entity_type",
        "entity_id",
        "source_entity_type",
        "source_entity_id",
        "expires_at",
        "superseded_by_id",
    ):
        op.create_index(f"ix_project_memory_items_{column}", "project_memory_items", [column])


def downgrade() -> None:
    for column in (
        "superseded_by_id",
        "expires_at",
        "source_entity_id",
        "source_entity_type",
        "entity_id",
        "entity_type",
        "write_policy",
        "status",
        "memory_type",
        "project_id",
        "workspace_id",
    ):
        op.drop_index(f"ix_project_memory_items_{column}", table_name="project_memory_items")
    op.drop_table("project_memory_items")
