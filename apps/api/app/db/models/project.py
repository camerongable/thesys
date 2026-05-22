import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from app.db.models.evidence import EvidenceSource


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status in ('active','paused','killed','launched','archived')",
            name="ck_projects_status",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    current_thesis_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    theses: Mapped[list["ProjectThesis"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectThesis.version",
    )
    intakes: Mapped[list["ProjectIntake"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectIntake.created_at",
    )
    customer_segments: Mapped[list["CustomerSegment"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="CustomerSegment.created_at",
    )
    problems: Mapped[list["Problem"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Problem.created_at",
    )
    evidence_sources: Mapped[list["EvidenceSource"]] = relationship(
        cascade="all, delete-orphan",
        order_by="EvidenceSource.created_at.desc()",
    )


class ProjectThesis(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "project_theses"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_theses_project_version"),
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
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    thesis_text: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="theses")


class ProjectIntake(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "project_intakes"
    __table_args__ = (
        CheckConstraint(
            "buyer_type in ('consumer','prosumer','smb','midmarket','enterprise','unknown')",
            name="ck_project_intakes_buyer_type",
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
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        index=True,
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    one_sentence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    target_users: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    buyer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    problem_hypotheses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    proposed_solution: Mapped[str] = mapped_column(Text, nullable=False)
    market_category: Mapped[str | None] = mapped_column(String(255))
    business_model_guess: Mapped[str | None] = mapped_column(String(255))
    suspected_competitors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    key_uncertainties: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    clarifying_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    user_answers: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    raw_idea: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="intakes")


class CustomerSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_segments"
    __table_args__ = (
        CheckConstraint(
            "buyer_type in ('consumer','prosumer','smb','midmarket','enterprise','unknown')",
            name="ck_customer_segments_buyer_type",
        ),
        CheckConstraint(
            "priority in ('primary','secondary','rejected','unknown')",
            name="ck_customer_segments_priority",
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
    description: Mapped[str | None] = mapped_column(Text)
    buyer_type: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[str | None] = mapped_column(String(20))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)

    project: Mapped[Project] = relationship(back_populates="customer_segments")
    problems: Mapped[list["Problem"]] = relationship(back_populates="segment")


class Problem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "problems"
    __table_args__ = (
        CheckConstraint(
            "severity in ('low','medium','high','critical','unknown')",
            name="ck_problems_severity",
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
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customer_segments.id", ondelete="SET NULL"),
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20))
    frequency: Mapped[str | None] = mapped_column(Text)
    current_alternatives: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric)

    project: Mapped[Project] = relationship(back_populates="problems")
    segment: Mapped[CustomerSegment | None] = relationship(back_populates="problems")
