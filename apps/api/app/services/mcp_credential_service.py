"""Encrypted, per-server OAuth credentials for remote MCP connections."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from fastapi import HTTPException, status
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_workspace_owner
from app.core.config import Settings
from app.db.models import MCPServerCredential, MCPServerRegistration
from app.schemas.mcp_registry import MCPServerCredentialConfigure
from app.security.encryption import (
    EncryptedValue,
    EnvelopeEncryptionError,
    build_envelope_encryption_service,
)
from app.services import governance_service, mcp_registry_service, remote_mcp_token_service

MAX_USER_DELEGATED_TOKEN_LIFETIME = timedelta(hours=1)


@dataclass(frozen=True)
class MCPServerCredentialMaterial:
    credential_type: str
    issuer: str
    audience: str
    scopes: tuple[str, ...]
    access_token: SecretStr | None
    refresh_token: SecretStr | None
    client_id: str | None
    client_secret: SecretStr | None
    expires_at: datetime | None


def configure_credential(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    registration_id: uuid.UUID,
    payload: MCPServerCredentialConfigure,
) -> MCPServerCredential:
    """Persist a credential only for its reviewed server and OAuth issuer."""
    require_workspace_owner(auth)
    registration = mcp_registry_service.get_registration(db, auth, registration_id)
    _validate_credential_binding(registration, payload)
    encryption = build_envelope_encryption_service(settings)
    try:
        credential = db.scalar(
            select(MCPServerCredential).where(
                MCPServerCredential.workspace_id == auth.workspace_id,
                MCPServerCredential.server_registration_id == registration.id,
            )
        )
        if credential is None:
            credential = MCPServerCredential(
                workspace_id=auth.workspace_id,
                server_registration_id=registration.id,
                credential_type=payload.credential_type,
                issuer=str(payload.issuer).rstrip("/"),
                audience=payload.audience.rstrip("/"),
                scopes=list(payload.scopes),
                algorithm="AES-256-GCM",
                created_by=auth.user_id,
            )
            db.add(credential)

        _clear_secret_fields(credential)
        credential.credential_type = payload.credential_type
        credential.issuer = str(payload.issuer).rstrip("/")
        credential.audience = payload.audience.rstrip("/")
        credential.scopes = list(payload.scopes)
        credential.client_id = payload.client_id
        credential.expires_at = None
        if payload.credential_type == "oauth_user_delegated":
            _store_encrypted(
                credential,
                "access_token",
                encryption.encrypt(
                    db,
                    workspace_id=auth.workspace_id,
                    plaintext=payload.access_token.get_secret_value(),
                    purpose=_credential_purpose(registration.id, "access-token"),
                ),
            )
            _store_encrypted(
                credential,
                "refresh_token",
                encryption.encrypt(
                    db,
                    workspace_id=auth.workspace_id,
                    plaintext=payload.refresh_token.get_secret_value(),
                    purpose=_credential_purpose(registration.id, "refresh-token"),
                ),
            )
            credential.expires_at = _as_utc(payload.expires_at)
        else:
            credential.client_id = payload.client_id
            _store_encrypted(
                credential,
                "client_secret",
                encryption.encrypt(
                    db,
                    workspace_id=auth.workspace_id,
                    plaintext=payload.client_secret.get_secret_value(),
                    purpose=_credential_purpose(registration.id, "client-secret"),
                ),
            )
        registration.enabled = False
        db.flush()
    except EnvelopeEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remote MCP credential storage is temporarily unavailable.",
        ) from exc

    governance_service.record_audit_event(
        db,
        auth,
        event_type="mcp_server_credential_configured",
        actor_type="user",
        entity_type="mcp_server_registration",
        entity_id=registration.id,
        risk_level="high",
        summary="Configured encrypted credentials for a remote MCP server.",
        metadata={
            "credential_type": credential.credential_type,
            "issuer": credential.issuer,
            "audience": credential.audience,
            "server_disabled_pending_review": True,
        },
    )
    db.commit()
    db.refresh(credential)
    return credential


def get_credential_metadata(
    db: Session,
    auth: AuthContext,
    registration_id: uuid.UUID,
) -> MCPServerCredential:
    require_workspace_owner(auth)
    registration = mcp_registry_service.get_registration(db, auth, registration_id)
    credential = _get_credential(db, auth.workspace_id, registration.id)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP credential not found.",
        )
    return credential


def revoke_credential(
    db: Session,
    auth: AuthContext,
    registration_id: uuid.UUID,
) -> None:
    require_workspace_owner(auth)
    registration = mcp_registry_service.get_registration(db, auth, registration_id)
    credential = _get_credential(db, auth.workspace_id, registration.id)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP credential not found.",
        )
    registration.enabled = False
    db.delete(credential)
    governance_service.record_audit_event(
        db,
        auth,
        event_type="mcp_server_credential_revoked",
        actor_type="user",
        entity_type="mcp_server_registration",
        entity_id=registration.id,
        risk_level="high",
        summary="Revoked credentials for a remote MCP server and disabled it.",
        metadata={"credential_type": credential.credential_type},
    )
    db.commit()


def resolve_credential_material(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    registration: MCPServerRegistration,
    *,
    allow_expired_access_token: bool = False,
) -> MCPServerCredentialMaterial:
    """Decrypt only the credentials isolated to the reviewed target server."""
    if registration.workspace_id != auth.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found.")
    credential = _get_credential(db, auth.workspace_id, registration.id)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remote MCP credentials are unavailable.",
        )
    expires_at = _stored_as_utc(credential.expires_at)
    if (
        not allow_expired_access_token
        and expires_at is not None
        and expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remote MCP credentials are unavailable.",
        )
    encryption = build_envelope_encryption_service(settings)
    try:
        return MCPServerCredentialMaterial(
            credential_type=credential.credential_type,
            issuer=credential.issuer,
            audience=credential.audience,
            scopes=tuple(credential.scopes),
            access_token=_decrypt_secret(
                encryption,
                db,
                auth.workspace_id,
                registration.id,
                credential,
                "access_token",
                "access-token",
            ),
            refresh_token=_decrypt_secret(
                encryption,
                db,
                auth.workspace_id,
                registration.id,
                credential,
                "refresh_token",
                "refresh-token",
            ),
            client_id=credential.client_id,
            client_secret=_decrypt_secret(
                encryption,
                db,
                auth.workspace_id,
                registration.id,
                credential,
                "client_secret",
                "client-secret",
            ),
            expires_at=expires_at,
        )
    except EnvelopeEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remote MCP credentials are unavailable.",
        ) from exc


def resolve_validated_access_token(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    registration: MCPServerRegistration,
) -> SecretStr:
    """Return only a valid access token bound to the reviewed registration."""
    material = resolve_credential_material(
        db,
        auth,
        settings,
        registration,
        allow_expired_access_token=True,
    )
    if not _material_matches_registration(material, registration):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remote MCP credentials are unavailable.",
        )
    try:
        if material.credential_type == "oauth_user_delegated":
            if (
                material.access_token is not None
                and material.expires_at is not None
                and material.expires_at > datetime.now(UTC)
            ):
                remote_mcp_token_service.validate_access_token(
                    settings,
                    access_token=material.access_token,
                    issuer=material.issuer,
                    audience=material.audience,
                    required_scopes=material.scopes,
                )
                return material.access_token
            if material.refresh_token is None or material.client_id is None:
                raise remote_mcp_token_service.RemoteMcpTokenValidationError(
                    "scoped_credentials_unavailable"
                )
            grant = remote_mcp_token_service.request_user_delegated_refresh_token(
                settings,
                issuer=material.issuer,
                audience=material.audience,
                scopes=material.scopes,
                client_id=material.client_id,
                refresh_token=material.refresh_token,
            )
            _persist_refreshed_user_delegated_credential(
                db,
                auth,
                settings,
                registration,
                grant,
            )
            return grant.access_token
        if (
            material.credential_type == "oauth_client_credentials"
            and material.client_id is not None
            and material.client_secret is not None
        ):
            return remote_mcp_token_service.request_client_credentials_access_token(
                settings,
                issuer=material.issuer,
                audience=material.audience,
                scopes=material.scopes,
                client_id=material.client_id,
                client_secret=material.client_secret,
            )
        raise remote_mcp_token_service.RemoteMcpTokenValidationError(
            "scoped_credentials_unavailable"
        )
    except remote_mcp_token_service.RemoteMcpTokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remote MCP credentials are unavailable.",
        ) from exc


def _material_matches_registration(
    material: MCPServerCredentialMaterial,
    registration: MCPServerRegistration,
) -> bool:
    return (
        registration.oauth_issuer is not None
        and material.issuer == registration.oauth_issuer.rstrip("/")
        and material.audience == _registration_audience(registration)
    )


def _persist_refreshed_user_delegated_credential(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    registration: MCPServerRegistration,
    grant: remote_mcp_token_service.RemoteMcpOAuthTokenGrant,
) -> None:
    credential = _get_credential(db, auth.workspace_id, registration.id)
    if credential is None or credential.credential_type != "oauth_user_delegated":
        raise remote_mcp_token_service.RemoteMcpTokenValidationError(
            "scoped_credentials_unavailable"
        )
    encryption = build_envelope_encryption_service(settings)
    try:
        _store_encrypted(
            credential,
            "access_token",
            encryption.encrypt(
                db,
                workspace_id=auth.workspace_id,
                plaintext=grant.access_token.get_secret_value(),
                purpose=_credential_purpose(registration.id, "access-token"),
            ),
        )
        if grant.refresh_token is not None:
            _store_encrypted(
                credential,
                "refresh_token",
                encryption.encrypt(
                    db,
                    workspace_id=auth.workspace_id,
                    plaintext=grant.refresh_token.get_secret_value(),
                    purpose=_credential_purpose(registration.id, "refresh-token"),
                ),
            )
        credential.expires_at = grant.expires_at
        db.flush()
    except EnvelopeEncryptionError as exc:
        raise remote_mcp_token_service.RemoteMcpTokenValidationError(
            "credential_refresh_storage_unavailable"
        ) from exc
    governance_service.record_audit_event(
        db,
        auth,
        event_type="mcp_server_credential_refreshed",
        actor_type="user",
        entity_type="mcp_server_registration",
        entity_id=registration.id,
        risk_level="high",
        summary="Refreshed encrypted user-delegated MCP credentials.",
        metadata={"credential_type": credential.credential_type},
    )


def _validate_credential_binding(
    registration: MCPServerRegistration,
    payload: MCPServerCredentialConfigure,
) -> None:
    if registration.oauth_issuer is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The MCP server registration does not allow OAuth credentials.",
        )
    if str(payload.issuer).rstrip("/") != registration.oauth_issuer.rstrip("/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP credential issuer does not match the reviewed server registration.",
        )
    if payload.audience.rstrip("/") != _registration_audience(registration):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP credential audience does not match the reviewed server registration.",
        )
    if payload.credential_type == "oauth_user_delegated":
        expires_at = _as_utc(payload.expires_at)
        now = datetime.now(UTC)
        if expires_at <= now or expires_at > now + MAX_USER_DELEGATED_TOKEN_LIFETIME:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="User-delegated MCP access tokens must expire within one hour.",
            )


def _registration_audience(registration: MCPServerRegistration) -> str:
    parsed = urlparse(registration.base_url)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _get_credential(
    db: Session,
    workspace_id: uuid.UUID,
    registration_id: uuid.UUID,
) -> MCPServerCredential | None:
    return db.scalar(
        select(MCPServerCredential).where(
            MCPServerCredential.workspace_id == workspace_id,
            MCPServerCredential.server_registration_id == registration_id,
        )
    )


def _clear_secret_fields(credential: MCPServerCredential) -> None:
    for field in (
        "access_token_ciphertext",
        "access_token_nonce",
        "access_token_key_version",
        "refresh_token_ciphertext",
        "refresh_token_nonce",
        "refresh_token_key_version",
        "client_secret_ciphertext",
        "client_secret_nonce",
        "client_secret_key_version",
        "client_id",
    ):
        setattr(credential, field, None)


def _store_encrypted(
    credential: MCPServerCredential,
    field_prefix: str,
    encrypted: EncryptedValue,
) -> None:
    setattr(credential, f"{field_prefix}_ciphertext", encrypted.ciphertext)
    setattr(credential, f"{field_prefix}_nonce", encrypted.nonce)
    setattr(credential, f"{field_prefix}_key_version", encrypted.key_version)


def _decrypt_secret(
    encryption,
    db: Session,
    workspace_id: uuid.UUID,
    registration_id: uuid.UUID,
    credential: MCPServerCredential,
    field_prefix: str,
    purpose_suffix: str,
) -> SecretStr | None:
    ciphertext = getattr(credential, f"{field_prefix}_ciphertext")
    nonce = getattr(credential, f"{field_prefix}_nonce")
    key_version = getattr(credential, f"{field_prefix}_key_version")
    if ciphertext is None or nonce is None or key_version is None:
        return None
    return SecretStr(
        encryption.decrypt(
            db,
            workspace_id=workspace_id,
            encrypted=EncryptedValue(
                ciphertext=ciphertext,
                nonce=nonce,
                key_version=key_version,
            ),
            purpose=_credential_purpose(registration_id, purpose_suffix),
        )
    )


def _credential_purpose(registration_id: uuid.UUID, value_type: str) -> str:
    return f"mcp-server-credential:{registration_id}:{value_type}"


def _as_utc(value: datetime | None) -> datetime:
    if value is None or value.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MCP credential expiry must include a timezone.",
        )
    return value.astimezone(UTC)


def _stored_as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
