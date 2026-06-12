import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ToolInvocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        CheckConstraint(
            "access_mode in ('read','write','proposal')",
            name="ck_tool_invocations_access_mode",
        ),
        CheckConstraint(
            "risk_level in ('low','medium','high')",
            name="ck_tool_invocations_risk_level",
        ),
        CheckConstraint(
            "status in ('requested','approved','rejected','executed','failed')",
            name="ck_tool_invocations_status",
        ),
        CheckConstraint(
            "requested_by in ('agent','user','system')",
            name="ck_tool_invocations_requested_by",
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
    research_sprint_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_sprints.id", ondelete="CASCADE"),
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    access_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    output_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
    )
    output_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(20), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
