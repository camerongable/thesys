import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint, Uuid
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
