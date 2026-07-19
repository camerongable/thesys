"""Reviewed external MCP server registration boundary."""

import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, record_cross_tenant_access_attempt, require_workspace_owner
from app.core.config import Settings
from app.db.models import MCPServerRegistration
from app.features.governance_tools import registry as tool_registry
from app.schemas.mcp_registry import MCPServerRegistrationCreate
from app.services import (
    governance_service,
    remote_mcp_review_service,
    security_policy_service,
)

_FINGERPRINT_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def list_registrations(db: Session, auth: AuthContext) -> list[MCPServerRegistration]:
    return list(
        db.scalars(
            select(MCPServerRegistration)
            .where(MCPServerRegistration.workspace_id == auth.workspace_id)
            .order_by(MCPServerRegistration.created_at.desc())
        )
    )


def register_server(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    payload: MCPServerRegistrationCreate,
) -> MCPServerRegistration:
    """Register a reviewed server disabled until a separate enablement review."""
    require_workspace_owner(auth)
    security_policy_service.enforce_external_mcp_allowed(
        db,
        auth,
        settings,
        operation="registration",
    )
    base_url = _validated_server_url(str(payload.base_url), settings)
    if payload.oauth_issuer is not None:
        _validated_server_url(str(payload.oauth_issuer), settings)
    if not _FINGERPRINT_PATTERN.fullmatch(payload.server_fingerprint):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP server fingerprint must be a SHA-256 hex digest.",
        )
    allowed_tools = sorted(set(payload.allowed_tools))
    if len(allowed_tools) != len(payload.allowed_tools):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP allowed tools must not contain duplicates.",
        )
    manifests = {
        definition.name: definition for definition in tool_registry.list_tool_definitions()
    }
    unknown_tools = sorted(set(allowed_tools) - set(manifests))
    if unknown_tools:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP registration includes a tool that is not locally approved.",
        )
    registration = MCPServerRegistration(
        workspace_id=auth.workspace_id,
        name=payload.name.strip(),
        base_url=base_url,
        transport=payload.transport,
        server_fingerprint=payload.server_fingerprint.lower(),
        approved_version=payload.approved_version.strip(),
        allowed_tools=allowed_tools,
        tool_schema_snapshot={name: _manifest_snapshot(manifests[name]) for name in allowed_tools},
        oauth_issuer=str(payload.oauth_issuer) if payload.oauth_issuer is not None else None,
        enabled=False,
        reviewed_at=datetime.now(UTC),
        reviewed_by=auth.user_id,
    )
    db.add(registration)
    db.flush()
    governance_service.record_audit_event(
        db,
        auth,
        event_type="mcp_server_registered",
        actor_type="user",
        entity_type="mcp_server_registration",
        entity_id=registration.id,
        risk_level="high",
        summary=f"Registered external MCP server {registration.name} in a disabled state.",
        metadata={
            "transport": registration.transport,
            "host": urlparse(registration.base_url).hostname,
            "allowed_tools": allowed_tools,
            "enabled": False,
        },
    )
    db.commit()
    db.refresh(registration)
    return registration


def enable_server(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    registration_id: uuid.UUID,
) -> MCPServerRegistration:
    """Enable a server only after a fresh identity and manifest review succeeds."""
    require_workspace_owner(auth)
    registration = _get_registration(db, auth, registration_id)
    security_policy_service.enforce_external_mcp_allowed(
        db,
        auth,
        settings,
        operation="enablement",
    )
    try:
        review = remote_mcp_review_service.review_registration(settings, registration)
    except remote_mcp_review_service.RemoteMcpReviewError as exc:
        registration.enabled = False
        governance_service.record_audit_event(
            db,
            auth,
            event_type="mcp_server_review_failed",
            actor_type="user",
            entity_type="mcp_server_registration",
            entity_id=registration.id,
            risk_level="high",
            summary="Remote MCP server review failed and the server remains disabled.",
            metadata={"reason_code": exc.reason_code},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Remote MCP server review failed; it remains disabled.",
        ) from exc

    registration.enabled = True
    registration.reviewed_at = datetime.now(UTC)
    registration.reviewed_by = auth.user_id
    governance_service.record_audit_event(
        db,
        auth,
        event_type="mcp_server_enabled",
        actor_type="user",
        entity_type="mcp_server_registration",
        entity_id=registration.id,
        risk_level="high",
        summary=f"Enabled reviewed external MCP server {registration.name}.",
        metadata={
            "server_name": review.server_name,
            "server_version": review.server_version,
            "certificate_fingerprint": review.certificate_fingerprint,
            "tool_count": review.tool_count,
        },
    )
    db.commit()
    db.refresh(registration)
    return registration


def _validated_server_url(value: str, settings: Settings) -> str:
    parsed = urlparse(value)
    host = parsed.hostname.casefold() if parsed.hostname else ""
    allowed_hosts = {candidate.casefold() for candidate in settings.mcp_server_allowed_hosts}
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or host not in allowed_hosts
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP server URL is not approved by the host and TLS policy.",
        )
    return value.rstrip("/")


def _get_registration(
    db: Session,
    auth: AuthContext,
    registration_id: uuid.UUID,
) -> MCPServerRegistration:
    registration = db.scalar(
        select(MCPServerRegistration).where(
            MCPServerRegistration.id == registration_id,
            MCPServerRegistration.workspace_id == auth.workspace_id,
        )
    )
    if registration is None:
        record_cross_tenant_access_attempt(
            db,
            auth,
            reason_code="mcp_server_registration_scope_denied",
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found.")
    return registration


def _manifest_snapshot(definition: tool_registry.ToolDefinition) -> dict[str, object]:
    return {
        "version": definition.version,
        "input_schema": definition.input_schema,
        "output_schema": definition.output_schema,
        "access_mode": definition.access_mode,
        "risk_level": definition.risk_level,
        "required_scopes": list(definition.required_scopes),
    }
