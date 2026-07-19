import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, UUIDPrimaryKeyMixin


class AICacheEntry(UUIDPrimaryKeyMixin, Base):
    """Versioned AI cache entry scoped to a workspace and optional project."""

    __tablename__ = "ai_cache_entries"
    __table_args__ = (
        CheckConstraint(
            "cache_type in ('embedding','retrieval_plan','rerank_result','guide_answer')",
            name="ck_ai_cache_entries_cache_type",
        ),
        CheckConstraint(
            "status in ('active','stale','disabled')",
            name="ck_ai_cache_entries_status",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    cache_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    family_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    key_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    version_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    value_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    events: Mapped[list["AICacheEvent"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="AICacheEvent.created_at",
    )


class AICacheEvent(UUIDPrimaryKeyMixin, Base):
    """Per-access cache telemetry used by eval reports and hidden diagnostics."""

    __tablename__ = "ai_cache_events"
    __table_args__ = (
        CheckConstraint(
            "cache_type in ('embedding','retrieval_plan','rerank_result','guide_answer')",
            name="ck_ai_cache_events_cache_type",
        ),
        CheckConstraint(
            "event_type in ('hit','miss','stale_denial','write','disabled','invalidate')",
            name="ck_ai_cache_events_event_type",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    cache_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_cache_entries.id", ondelete="SET NULL"),
        index=True,
    )
    cache_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    key_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    family_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    saved_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saved_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    latency_saved_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    entry: Mapped[AICacheEntry | None] = relationship(back_populates="events")
