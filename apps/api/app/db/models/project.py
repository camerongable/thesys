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
    thesis_canvas: Mapped["ThesisCanvas | None"] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )
    thesis_evolution_events: Mapped[list["ThesisEvolutionEvent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ThesisEvolutionEvent.created_at",
    )
    wedge_options: Mapped[list["WedgeOption"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="WedgeOption.created_at",
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


class ThesisCanvas(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "thesis_canvases"

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
        unique=True,
        index=True,
    )
    original_idea: Mapped[str] = mapped_column(Text, nullable=False)
    current_thesis: Mapped[str] = mapped_column(Text, nullable=False)
    target_user: Mapped[str] = mapped_column(Text, nullable=False, default="")
    problem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_workaround: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proposed_solution: Mapped[str] = mapped_column(Text, nullable=False, default="")
    wedge: Mapped[str] = mapped_column(Text, nullable=False, default="")
    biggest_unknown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proof_needed: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rejected_directions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    open_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    project: Mapped[Project] = relationship(back_populates="thesis_canvas")


class ThesisEvolutionEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "thesis_evolution_events"
    __table_args__ = (
        CheckConstraint(
            "event_type in ("
            "'original_idea','structured_thesis','research_update','wedge_change',"
            "'validation_blocker','decision','manual_update'"
            ")",
            name="ck_thesis_evolution_events_event_type",
        ),
        CheckConstraint(
            "origin in ('user','agent','system')",
            name="ck_thesis_evolution_events_origin",
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
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_entity_type: Mapped[str | None] = mapped_column(String(40))
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="thesis_evolution_events")


class WedgeOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wedge_options"
    __table_args__ = (
        CheckConstraint(
            "competitor_pressure in ('low','medium','high')",
            name="ck_wedge_options_competitor_pressure",
        ),
        CheckConstraint(
            "evidence_strength in ('none','weak','partial','strong')",
            name="ck_wedge_options_evidence_strength",
        ),
        CheckConstraint(
            "recommendation in ("
            "'recommended','promising','research_later','avoid_for_now','rejected'"
            ")",
            name="ck_wedge_options_recommendation",
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
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_user: Mapped[str] = mapped_column(Text, nullable=False)
    problem_focus: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_might_work: Mapped[str] = mapped_column(Text, nullable=False)
    main_risk: Mapped[str] = mapped_column(Text, nullable=False)
    competitor_pressure: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_test: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    project: Mapped[Project] = relationship(back_populates="wedge_options")


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
