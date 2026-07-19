import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
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


class MCPServerRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A workspace-owned, reviewed remote MCP server registration."""

    __tablename__ = "mcp_server_registrations"
    __table_args__ = (
        CheckConstraint(
            "transport in ('streamable_http','sse')",
            name="ck_mcp_server_registrations_transport",
        ),
        UniqueConstraint("workspace_id", "name", name="uq_mcp_server_registrations_workspace_name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    server_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_version: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_tools: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tool_schema_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    oauth_issuer: Mapped[str | None] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))


class MCPServerCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Encrypted, least-privilege OAuth material for one reviewed MCP server."""

    __tablename__ = "mcp_server_credentials"
    __table_args__ = (
        CheckConstraint(
            "credential_type in ('oauth_user_delegated','oauth_client_credentials')",
            name="ck_mcp_server_credentials_type",
        ),
        CheckConstraint(
            "algorithm = 'AES-256-GCM'",
            name="ck_mcp_server_credentials_algorithm",
        ),
        UniqueConstraint(
            "server_registration_id",
            name="uq_mcp_server_credentials_registration",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server_registration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mcp_server_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)
    issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    audience: Mapped[str] = mapped_column(String(2048), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    access_token_ciphertext: Mapped[str | None] = mapped_column(Text)
    access_token_nonce: Mapped[str | None] = mapped_column(String(32))
    access_token_key_version: Mapped[str | None] = mapped_column(String(64))
    refresh_token_ciphertext: Mapped[str | None] = mapped_column(Text)
    refresh_token_nonce: Mapped[str | None] = mapped_column(String(32))
    refresh_token_key_version: Mapped[str | None] = mapped_column(String(64))
    client_id: Mapped[str | None] = mapped_column(String(255))
    client_secret_ciphertext: Mapped[str | None] = mapped_column(Text)
    client_secret_nonce: Mapped[str | None] = mapped_column(String(32))
    client_secret_key_version: Mapped[str | None] = mapped_column(String(64))
    algorithm: Mapped[str] = mapped_column(String(20), nullable=False, default="AES-256-GCM")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))


class MCPOAuthAuthorizationTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single-use encrypted PKCE verifier for a reviewed MCP OAuth registration."""

    __tablename__ = "mcp_oauth_authorization_transactions"
    __table_args__ = (
        CheckConstraint(
            "algorithm = 'AES-256-GCM'",
            name="ck_mcp_oauth_authorization_transactions_algorithm",
        ),
        UniqueConstraint("state_hash", name="uq_mcp_oauth_authorization_transactions_state_hash"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server_registration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mcp_server_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    redirect_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    verifier_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    verifier_nonce: Mapped[str] = mapped_column(String(32), nullable=False)
    verifier_key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(20), nullable=False, default="AES-256-GCM")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkspaceKillSwitchState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workspace-scoped emergency capability disables."""

    __tablename__ = "workspace_kill_switch_states"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_workspace_kill_switch_states_workspace"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    disable_all_agent_writes: Mapped[bool] = mapped_column(nullable=False, default=False)
    disable_external_mcp: Mapped[bool] = mapped_column(nullable=False, default=False)
    disable_external_egress: Mapped[bool] = mapped_column(nullable=False, default=False)
    disable_model_provider: Mapped[bool] = mapped_column(nullable=False, default=False)
    disable_memory_writes: Mapped[bool] = mapped_column(nullable=False, default=False)
    disable_source_fetching: Mapped[bool] = mapped_column(nullable=False, default=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))


class SecurityEvent(UUIDPrimaryKeyMixin, Base):
    """Normalized, redacted detection record for security monitoring and response."""

    __tablename__ = "security_events"
    __table_args__ = (
        CheckConstraint(
            "severity in ('info','low','medium','high','critical')",
            name="ck_security_events_severity",
        ),
        CheckConstraint(
            "source in ('api','guardrail','retrieval','tool','memory','workflow','auth','mcp')",
            name="ck_security_events_source",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    audit_event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audit_events.id", ondelete="SET NULL"),
        index=True,
    )
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        index=True,
    )
    tool_invocation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tool_invocations.id", ondelete="SET NULL"),
        index=True,
    )
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        index=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(255), index=True)
    request_id: Mapped[str | None] = mapped_column(String(255), index=True)
    langsmith_trace_id: Mapped[str | None] = mapped_column(String(100), index=True)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    containment_status: Mapped[str | None] = mapped_column(String(80), index=True)
