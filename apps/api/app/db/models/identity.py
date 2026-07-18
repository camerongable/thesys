import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status in ('active','disabled')", name="ck_users_status"),
    )

    external_auth_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    memberships: Mapped[list["WorkspaceMember"]] = relationship(back_populates="user")


class Workspace(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    members: Mapped[list["WorkspaceMember"]] = relationship(back_populates="workspace")


class WorkspaceMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        CheckConstraint(
            "role in ('owner','admin','editor','viewer')",
            name="ck_workspace_members_role",
        ),
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class AuthenticationEvent(UUIDPrimaryKeyMixin, Base):
    """Immutable, credential-free records of authentication outcomes."""

    __tablename__ = "authentication_events"
    __table_args__ = (
        CheckConstraint(
            "event_type in ("
            "'login_success','login_failure','token_validation_failure',"
            "'workspace_access_denied','role_change','session_revoked',"
            "'cross_tenant_access_attempt'"
            ")",
            name="ck_authentication_events_event_type",
        ),
        CheckConstraint(
            "authentication_method in ('dev','jwt','api_key','oidc')",
            name="ck_authentication_events_method",
        ),
    )

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    authentication_method: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )


class SessionRevocation(UUIDPrimaryKeyMixin, Base):
    """Hashed session identifiers that must no longer authenticate a principal."""

    __tablename__ = "session_revocations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "session_identifier_hash",
            name="uq_session_revocations_identity",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_identifier_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
