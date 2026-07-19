import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditEvent, MCPServerRegistration
from app.services import mcp_registry_service, remote_mcp_review_service


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


def test_external_mcp_kill_switch_blocks_remote_server_registration(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test")
    get_settings.cache_clear()
    try:
        update_response = client.patch(
            "/api/security/kill-switches",
            json={"disable_external_mcp": True},
        )
        response = client.post(
            "/api/mcp/servers",
            json={
                "name": "Blocked connector",
                "base_url": "https://mcp.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "e" * 64,
                "approved_version": "1",
                "allowed_tools": [],
            },
        )
    finally:
        get_settings.cache_clear()

    assert update_response.status_code == 200
    assert response.status_code == 403
    assert response.json() == {"detail": "External MCP access is temporarily unavailable."}
    assert db_session.scalar(select(MCPServerRegistration)) is None
    denial = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert denial is not None
    assert denial.event_metadata["workflow_type"] == "external_mcp_registration"


def test_workspace_owner_can_enable_a_live_reviewed_mcp_server(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test")
    get_settings.cache_clear()
    try:
        registration_response = client.post(
            "/api/mcp/servers",
            json={
                "name": "Reviewed connector",
                "base_url": "https://mcp.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "f" * 64,
                "approved_version": "2026.07.18",
                "allowed_tools": ["get_project_summary"],
            },
        )
        registration_id = registration_response.json()["id"]
        monkeypatch.setattr(
            mcp_registry_service.remote_mcp_review_service,
            "review_registration",
            lambda _settings, _registration: remote_mcp_review_service.RemoteMcpReview(
                server_name="reviewed-mcp",
                server_version="2026.07.18",
                certificate_fingerprint="f" * 64,
                tool_count=1,
            ),
        )
        response = client.post(f"/api/mcp/servers/{registration_id}/enable")
    finally:
        get_settings.cache_clear()

    assert registration_response.status_code == 201
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    registration = db_session.scalar(
        select(MCPServerRegistration).where(MCPServerRegistration.id == uuid.UUID(registration_id))
    )
    assert registration is not None
    assert registration.enabled is True
    audit = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "mcp_server_enabled",
            AuditEvent.entity_id == registration.id,
        )
    )
    assert audit is not None
    assert audit.event_metadata["server_version"] == "2026.07.18"


def test_schema_drift_disables_remote_mcp_server_during_enablement(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MCP_SERVER_ALLOWED_HOSTS", "mcp.example.test")
    get_settings.cache_clear()
    try:
        registration_response = client.post(
            "/api/mcp/servers",
            json={
                "name": "Drifted connector",
                "base_url": "https://mcp.example.test/v1",
                "transport": "streamable_http",
                "server_fingerprint": "1" * 64,
                "approved_version": "2026.07.18",
                "allowed_tools": ["get_project_summary"],
            },
        )
        registration_id = registration_response.json()["id"]

        def _drifted_review(*_args, **_kwargs):
            raise remote_mcp_review_service.RemoteMcpReviewError("tool_schema_drift")

        monkeypatch.setattr(
            mcp_registry_service.remote_mcp_review_service,
            "review_registration",
            _drifted_review,
        )
        response = client.post(f"/api/mcp/servers/{registration_id}/enable")
    finally:
        get_settings.cache_clear()

    assert registration_response.status_code == 201
    assert response.status_code == 409
    assert response.json() == {"detail": "Remote MCP server review failed; it remains disabled."}
    registration = db_session.scalar(
        select(MCPServerRegistration).where(MCPServerRegistration.id == uuid.UUID(registration_id))
    )
    assert registration is not None
    assert registration.enabled is False
    audit = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "mcp_server_review_failed",
            AuditEvent.entity_id == registration.id,
        )
    )
    assert audit is not None
    assert audit.event_metadata["reason_code"] == "tool_schema_drift"


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
