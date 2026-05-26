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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Artifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_type in ("
            "'opportunity_brief','competitor_landscape','validation_plan',"
            "'decision_memo','research_memo','customer_discovery_summary','other'"
            ")",
            name="ck_artifacts_artifact_type",
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
    artifact_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    versions: Mapped[list["ArtifactVersion"]] = relationship(
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="ArtifactVersion.version",
    )


class ArtifactVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("artifact_id", "version", name="uq_artifact_versions_artifact_version"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_by_ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    artifact: Mapped[Artifact] = relationship(back_populates="versions")
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="artifact_version",
        cascade="all, delete-orphan",
        order_by="Claim.created_at",
    )


class Claim(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(
            "support_level in ('supported','partial','unsupported','inference')",
            name="ck_claims_support_level",
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
    artifact_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("artifact_versions.id", ondelete="CASCADE"),
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str | None] = mapped_column(String(80))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)
    support_level: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    artifact_version: Mapped[ArtifactVersion | None] = relationship(back_populates="claims")
    evidence_links: Mapped[list["ClaimEvidenceLink"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="ClaimEvidenceLink.created_at",
    )


class ClaimEvidenceLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "claim_evidence_links"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
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
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric)
    quote: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    claim: Mapped[Claim] = relationship(back_populates="evidence_links")


class Assumption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assumptions"
    __table_args__ = (
        CheckConstraint(
            "importance in ('low','medium','high','critical')",
            name="ck_assumptions_importance",
        ),
        CheckConstraint(
            "uncertainty in ('low','medium','high')",
            name="ck_assumptions_uncertainty",
        ),
        CheckConstraint(
            "status in ('untested','testing','validated','invalidated','inconclusive')",
            name="ck_assumptions_status",
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
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    importance: Mapped[str] = mapped_column(String(20), nullable=False)
    uncertainty: Mapped[str] = mapped_column(String(20), nullable=False)
    kill_risk: Mapped[bool] = mapped_column(default=False, nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="untested")
    recommended_test: Mapped[str | None] = mapped_column(Text)

    evidence_links: Mapped[list["AssumptionEvidenceLink"]] = relationship(
        back_populates="assumption",
        cascade="all, delete-orphan",
        order_by="AssumptionEvidenceLink.created_at",
    )


class AssumptionEvidenceLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "assumption_evidence_links"

    assumption_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assumptions.id", ondelete="CASCADE"),
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
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric)
    quote: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    assumption: Mapped[Assumption] = relationship(back_populates="evidence_links")


class Risk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risks"
    __table_args__ = (
        CheckConstraint(
            "severity in ('low','medium','high','critical')",
            name="ck_risks_severity",
        ),
        CheckConstraint(
            "likelihood in ('low','medium','high','unknown')",
            name="ck_risks_likelihood",
        ),
        CheckConstraint(
            "status in ('open','mitigated','accepted','closed')",
            name="ck_risks_status",
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
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    likelihood: Mapped[str] = mapped_column(String(20), nullable=False)
    mitigation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
