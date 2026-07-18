import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkspaceDataKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A per-workspace data key wrapped by a versioned external key."""

    __tablename__ = "workspace_data_keys"
    __table_args__ = (
        CheckConstraint(
            "algorithm = 'AES-256-GCM'",
            name="ck_workspace_data_keys_algorithm",
        ),
        UniqueConstraint("workspace_id", name="uq_workspace_data_keys_workspace"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    wrapping_key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    wrapped_dek_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    wrapped_dek_nonce: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(20), nullable=False, default="AES-256-GCM")


class PiiTokenMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Encrypted reversible identifier mapping scoped to one workspace project."""

    __tablename__ = "pii_token_mappings"
    __table_args__ = (
        CheckConstraint(
            "algorithm = 'AES-256-GCM'",
            name="ck_pii_token_mappings_algorithm",
        ),
        UniqueConstraint("project_id", "token", name="uq_pii_token_mappings_project_token"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_value_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_value_nonce: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_value_key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(20), nullable=False, default="AES-256-GCM")
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
