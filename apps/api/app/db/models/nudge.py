import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectNudge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_nudges"
    __table_args__ = (
        CheckConstraint(
            "severity in ('info','warning','action_required')",
            name="ck_project_nudges_severity",
        ),
        UniqueConstraint("project_id", "nudge_key", name="uq_project_nudges_project_key"),
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
    nudge_key: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
