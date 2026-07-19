import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditEvent, MCPServerRegistration


def test_workspace_owner_registers_disabled_reviewed_mcp_server(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/mcp/servers",
            json={
                "name": "Approved research connector",
                "base_url": "https://mcp.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "a" * 64,
                "approved_version": "2026.07.18",
                "allowed_tools": ["get_project_summary", "search_project_evidence"],
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 201
    body = response.json()
    assert body["enabled"] is False
    assert body["allowed_tools"] == ["get_project_summary", "search_project_evidence"]
    assert body["tool_schema_snapshot"]["get_project_summary"]["version"] == "1.0.0"
    registration = db_session.scalar(
        select(MCPServerRegistration).where(MCPServerRegistration.id == uuid.UUID(body["id"]))
    )
    assert registration is not None
    assert registration.enabled is False
    audit = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "mcp_server_registered",
            AuditEvent.entity_id == registration.id,
        )
    )
    assert audit is not None
    assert audit.event_metadata["host"] == "mcp.example.test"
    assert audit.event_metadata["enabled"] is False


def test_non_owner_cannot_register_external_mcp_server(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/mcp/servers",
            headers={"X-Dev-User-Role": "editor"},
            json={
                "name": "Unapproved connector",
                "base_url": "https://mcp.example.test/v1",
                "transport": "sse",
                "server_fingerprint": "b" * 64,
                "approved_version": "1",
                "allowed_tools": [],
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 403


def test_mcp_registration_rejects_unapproved_hosts_and_tools(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test")
    get_settings.cache_clear()
    try:
        host_response = client.post(
            "/api/mcp/servers",
            json={
                "name": "Unapproved host",
                "base_url": "https://other.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "c" * 64,
                "approved_version": "1",
                "allowed_tools": [],
            },
        )
        tool_response = client.post(
            "/api/mcp/servers",
            json={
                "name": "Unknown tool",
                "base_url": "https://mcp.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "d" * 64,
                "approved_version": "1",
                "allowed_tools": ["remote_shell"],
            },
        )
    finally:
        get_settings.cache_clear()

    assert host_response.status_code == 422
    assert tool_response.status_code == 422
