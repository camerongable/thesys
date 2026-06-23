import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ResearchPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_plans"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','approved','rejected','completed')",
            name="ck_research_plans_status",
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
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    target_customer_hypotheses: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    research_questions: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    competitor_queries: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    market_queries: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    substitute_queries: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    source_types: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    assumptions_to_test: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    expected_outputs: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    sprints: Mapped[list["ResearchSprint"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ResearchSprint.created_at.desc()",
    )


class ResearchSprint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_sprints"
    __table_args__ = (
        CheckConstraint(
            "status in ("
            "'planned','waiting_for_approval','approved','running','needs_review',"
            "'waiting_for_memory_approval','completed','failed','cancelled','rejected'"
            ")",
            name="ck_research_sprints_status",
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
    research_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned", index=True)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(255), index=True)
    temporal_run_id: Mapped[str | None] = mapped_column(String(255), index=True)
    current_step: Mapped[str | None] = mapped_column(String(120), index=True)
    failed_step: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    langsmith_trace_id: Mapped[str | None] = mapped_column(String(100), index=True)
    langsmith_trace_url: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    plan: Mapped[ResearchPlan] = relationship(back_populates="sprints")
    discovered_sources: Mapped[list["DiscoveredSource"]] = relationship(
        back_populates="research_sprint",
        cascade="all, delete-orphan",
        order_by="DiscoveredSource.relevance_score.desc()",
    )
    competitor_candidates: Mapped[list["CompetitorCandidate"]] = relationship(
        back_populates="research_sprint",
        cascade="all, delete-orphan",
        order_by="CompetitorCandidate.relevance_score.desc()",
    )


class DiscoveredSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discovered_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type in ("
            "'company_site','pricing_page','product_page','review','forum','blog',"
            "'market_report','directory','docs','unknown'"
            ")",
            name="ck_discovered_sources_source_type",
        ),
        CheckConstraint(
            "status in ('candidate','approved','rejected','ingested','failed')",
            name="ck_discovered_sources_status",
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
    research_sprint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_sprints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_sources.id", ondelete="SET NULL"),
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    snippet: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    search_provider: Mapped[str | None] = mapped_column(String(50), index=True)
    search_query: Mapped[str | None] = mapped_column(Text)
    search_result_rank: Mapped[int | None] = mapped_column(index=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    provenance_metadata: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    relevance_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    reason_selected: Mapped[str] = mapped_column(Text, nullable=False)
    associated_research_question: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate", index=True)
    ingestion_error: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    research_sprint: Mapped[ResearchSprint] = relationship(back_populates="discovered_sources")


class CompetitorCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "competitor_candidates"
    __table_args__ = (
        CheckConstraint(
            "category in ("
            "'direct_competitor','indirect_competitor','substitute_behavior',"
            "'incumbent_platform','adjacent_solution','irrelevant'"
            ")",
            name="ck_competitor_candidates_category",
        ),
        CheckConstraint(
            "threat_level in ('low','medium','high')",
            name="ck_competitor_candidates_threat_level",
        ),
        CheckConstraint(
            "status in ('candidate','approved','rejected','merged')",
            name="ck_competitor_candidates_status",
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
    research_sprint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_sprints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    competitor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("competitors.id", ondelete="SET NULL"),
        index=True,
    )
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_sources.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    target_user: Mapped[str | None] = mapped_column(Text)
    positioning: Mapped[str | None] = mapped_column(Text)
    pricing_signal: Mapped[str | None] = mapped_column(Text)
    core_features: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    threat_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    relevance_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    source_ids: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate", index=True)
    ingestion_error: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    research_sprint: Mapped[ResearchSprint] = relationship(back_populates="competitor_candidates")
