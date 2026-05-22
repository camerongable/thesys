import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Competitor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "competitors"
    __table_args__ = (
        CheckConstraint(
            "category in ("
            "'direct','adjacent','incumbent','substitute','manual_alternative','unknown'"
            ")",
            name="ck_competitors_category",
        ),
        CheckConstraint(
            "threat_level in ('low','medium','high','unknown')",
            name="ck_competitors_threat_level",
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    target_user: Mapped[str | None] = mapped_column(Text)
    positioning: Mapped[str | None] = mapped_column(Text)
    pricing_summary: Mapped[str | None] = mapped_column(Text)
    key_features: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    strengths: Mapped[str | None] = mapped_column(Text)
    weaknesses: Mapped[str | None] = mapped_column(Text)
    differentiation_notes: Mapped[str | None] = mapped_column(Text)
    threat_level: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    watchlist_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_watched")
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    evidence_links: Mapped[list["CompetitorEvidenceLink"]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
        order_by="CompetitorEvidenceLink.created_at",
    )


class CompetitorEvidenceLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "competitor_evidence_links"

    competitor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_chunks.id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    competitor: Mapped[Competitor] = relationship(back_populates="evidence_links")
