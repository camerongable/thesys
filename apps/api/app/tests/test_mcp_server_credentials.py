import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditEvent, MCPServerCredential, MCPServerRegistration
from app.services import mcp_credential_service
from app.services.identity_service import ensure_dev_identity


def test_user_delegated_mcp_credentials_are_encrypted_scoped_and_revocable(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test,issuer.example.test")
    get_settings.cache_clear()
    access_token = "short-lived-access-token"
    refresh_token = "encrypted-refresh-token"
    try:
        registration_response = client.post(
            "/api/mcp/servers",
            json={
                "name": "OAuth connector",
                "base_url": "https://mcp.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "a" * 64,
                "approved_version": "1",
                "allowed_tools": [],
                "oauth_issuer": "https://issuer.example.test",
            },
        )
        registration_id = registration_response.json()["id"]
        credential_response = client.put(
            f"/api/mcp/servers/{registration_id}/credentials",
            json={
                "credential_type": "oauth_user_delegated",
                "issuer": "https://issuer.example.test",
                "audience": "https://mcp.example.test",
                "scopes": ["mcp.tools.read"],
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
            },
        )
    finally:
        get_settings.cache_clear()

    assert registration_response.status_code == 201
    assert credential_response.status_code == 200
    assert credential_response.json()["credential_type"] == "oauth_user_delegated"
    assert access_token not in credential_response.text
    assert refresh_token not in credential_response.text
    registration = db_session.scalar(
        select(MCPServerRegistration).where(MCPServerRegistration.id == uuid.UUID(registration_id))
    )
    credential = db_session.scalar(
        select(MCPServerCredential).where(
            MCPServerCredential.server_registration_id == uuid.UUID(registration_id)
        )
    )
    assert registration is not None
    assert credential is not None
    assert access_token not in credential.access_token_ciphertext
    assert refresh_token not in credential.refresh_token_ciphertext
    assert credential.client_secret_ciphertext is None

    settings = get_settings()
    auth = ensure_dev_identity(
        db_session,
        email=settings.dev_auth_default_email,
        display_name=settings.dev_auth_default_name,
        role="owner",
    )
    material = mcp_credential_service.resolve_credential_material(
        db_session,
        auth,
        settings,
        registration,
    )

    assert material.access_token is not None
    assert material.access_token.get_secret_value() == access_token
    assert material.refresh_token is not None
    assert material.refresh_token.get_secret_value() == refresh_token
    assert access_token not in repr(material)
    audit = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "mcp_server_credential_configured",
            AuditEvent.entity_id == registration.id,
        )
    )
    assert audit is not None
    assert access_token not in str(audit.event_metadata)
    assert refresh_token not in str(audit.event_metadata)

    registration.enabled = True
    db_session.commit()
    revoke_response = client.delete(f"/api/mcp/servers/{registration_id}/credentials")

    assert revoke_response.status_code == 204
    assert db_session.scalar(select(MCPServerCredential)) is None
    db_session.refresh(registration)
    assert registration.enabled is False


def test_client_credentials_are_isolated_to_the_reviewed_server(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test,issuer.example.test")
    get_settings.cache_clear()
    client_secret = "client-secret-for-one-server"
    try:
        registration_response = client.post(
            "/api/mcp/servers",
            json={
                "name": "Client credential connector",
                "base_url": "https://mcp.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "b" * 64,
                "approved_version": "1",
                "allowed_tools": [],
                "oauth_issuer": "https://issuer.example.test",
            },
        )
        registration_id = registration_response.json()["id"]
        response = client.put(
            f"/api/mcp/servers/{registration_id}/credentials",
            json={
                "credential_type": "oauth_client_credentials",
                "issuer": "https://issuer.example.test",
                "audience": "https://mcp.example.test",
                "scopes": ["mcp.tools.read"],
                "client_id": "connector-client",
                "client_secret": client_secret,
            },
        )
    finally:
        get_settings.cache_clear()

    assert registration_response.status_code == 201
    assert response.status_code == 200
    registration = db_session.scalar(
        select(MCPServerRegistration).where(MCPServerRegistration.id == uuid.UUID(registration_id))
    )
    credential = db_session.scalar(
        select(MCPServerCredential).where(
            MCPServerCredential.server_registration_id == uuid.UUID(registration_id)
        )
    )
    assert registration is not None
    assert credential is not None
    assert credential.access_token_ciphertext is None
    assert credential.client_secret_ciphertext is not None
    assert client_secret not in credential.client_secret_ciphertext

    settings = get_settings()
    auth = ensure_dev_identity(
        db_session,
        email=settings.dev_auth_default_email,
        display_name=settings.dev_auth_default_name,
        role="owner",
    )
    material = mcp_credential_service.resolve_credential_material(
        db_session,
        auth,
        settings,
        registration,
    )
    assert material.client_secret is not None
    assert material.client_secret.get_secret_value() == client_secret
    assert material.access_token is None


def test_mcp_credential_rejects_an_unreviewed_issuer_or_audience(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test,issuer.example.test")
    get_settings.cache_clear()
    try:
        registration_response = client.post(
            "/api/mcp/servers",
            json={
                "name": "Bound connector",
                "base_url": "https://mcp.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "c" * 64,
                "approved_version": "1",
                "allowed_tools": [],
                "oauth_issuer": "https://issuer.example.test",
            },
        )
        registration_id = registration_response.json()["id"]
        response = client.put(
            f"/api/mcp/servers/{registration_id}/credentials",
            json={
                "credential_type": "oauth_client_credentials",
                "issuer": "https://issuer.example.test",
                "audience": "https://other.example.test",
                "scopes": ["mcp.tools.read"],
                "client_id": "connector-client",
                "client_secret": "must-not-persist",
            },
        )
    finally:
        get_settings.cache_clear()

    assert registration_response.status_code == 201
    assert response.status_code == 422
    assert db_session.scalar(select(MCPServerCredential)) is None
