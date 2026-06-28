"""add ai cache entries and events

Revision ID: 0027_ai_cache_entries
Revises: 0026_project_memory_items
Create Date: 2026-06-28 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0027_ai_cache_entries"
down_revision = "0026_project_memory_items"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "ai_cache_entries",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid()),
        sa.Column("scope_key", sa.String(length=80), nullable=False),
        sa.Column("cache_type", sa.String(length=40), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("family_hash", sa.String(length=128), nullable=False),
        sa.Column("key_payload", _json_type(), nullable=False),
        sa.Column("version_payload", _json_type(), nullable=False),
        sa.Column("value_payload", _json_type(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "cache_type in ('embedding','retrieval_plan','rerank_result','guide_answer')",
            name="ck_ai_cache_entries_cache_type",
        ),
        sa.CheckConstraint(
            "status in ('active','stale','disabled')",
            name="ck_ai_cache_entries_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_cache_entries_workspace_id", "ai_cache_entries", ["workspace_id"])
    op.create_index("ix_ai_cache_entries_project_id", "ai_cache_entries", ["project_id"])
    op.create_index("ix_ai_cache_entries_scope_key", "ai_cache_entries", ["scope_key"])
    op.create_index("ix_ai_cache_entries_cache_type", "ai_cache_entries", ["cache_type"])
    op.create_index("ix_ai_cache_entries_key_hash", "ai_cache_entries", ["key_hash"])
    op.create_index("ix_ai_cache_entries_family_hash", "ai_cache_entries", ["family_hash"])
    op.create_index("ix_ai_cache_entries_status", "ai_cache_entries", ["status"])
    op.create_index(
        "uq_ai_cache_entries_scope_key",
        "ai_cache_entries",
        ["workspace_id", "scope_key", "cache_type", "key_hash"],
        unique=True,
    )

    op.create_table(
        "ai_cache_events",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid()),
        sa.Column("cache_entry_id", sa.Uuid()),
        sa.Column("cache_type", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("key_hash", sa.String(length=128)),
        sa.Column("family_hash", sa.String(length=128)),
        sa.Column("saved_tokens", sa.Integer(), nullable=False),
        sa.Column("saved_cost", sa.Numeric(12, 6), nullable=False),
        sa.Column("latency_saved_ms", sa.Integer(), nullable=False),
        sa.Column("event_metadata", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "cache_type in ('embedding','retrieval_plan','rerank_result','guide_answer')",
            name="ck_ai_cache_events_cache_type",
        ),
        sa.CheckConstraint(
            "event_type in ('hit','miss','stale_denial','write','disabled','invalidate')",
            name="ck_ai_cache_events_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["cache_entry_id"],
            ["ai_cache_entries.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "workspace_id",
        "project_id",
        "cache_entry_id",
        "cache_type",
        "event_type",
        "key_hash",
        "family_hash",
        "created_at",
    ):
        op.create_index(f"ix_ai_cache_events_{column}", "ai_cache_events", [column])


def downgrade() -> None:
    for column in (
        "created_at",
        "family_hash",
        "key_hash",
        "event_type",
        "cache_type",
        "cache_entry_id",
        "project_id",
        "workspace_id",
    ):
        op.drop_index(f"ix_ai_cache_events_{column}", table_name="ai_cache_events")
    op.drop_table("ai_cache_events")
    op.drop_index("uq_ai_cache_entries_scope_key", table_name="ai_cache_entries")
    for column in (
        "status",
        "family_hash",
        "key_hash",
        "cache_type",
        "scope_key",
        "project_id",
        "workspace_id",
    ):
        op.drop_index(f"ix_ai_cache_entries_{column}", table_name="ai_cache_entries")
    op.drop_table("ai_cache_entries")
