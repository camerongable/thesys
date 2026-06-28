import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectMemoryItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Typed durable memory item selected by AI workflows as project context."""

    __tablename__ = "project_memory_items"
    __table_args__ = (
        CheckConstraint(
            "memory_type in ('working','episodic','semantic','project','procedural','preference')",
            name="ck_project_memory_items_memory_type",
        ),
        CheckConstraint(
            "status in ('active','stale','archived','superseded','proposed')",
            name="ck_project_memory_items_status",
        ),
        CheckConstraint(
            "write_policy in ('direct','approval_required','derived_read_only','transient')",
            name="ck_project_memory_items_write_policy",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    write_policy: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    source_entity_type: Mapped[str | None] = mapped_column(String(80), index=True)
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    provenance_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_memory_items.id"),
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    superseded_by: Mapped["ProjectMemoryItem | None"] = relationship(
        remote_side="ProjectMemoryItem.id"
    )
