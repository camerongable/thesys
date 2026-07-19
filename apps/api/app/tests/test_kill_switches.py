from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditEvent, WorkspaceKillSwitchState


def _switches(body: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["name"]: item for item in body["switches"]}  # type: ignore[index]


def test_workspace_owner_can_change_and_view_audited_kill_switches(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.patch(
        "/api/security/kill-switches",
        json={"disable_model_provider": True, "disable_external_egress": True},
    )

    assert response.status_code == 200
    switches = _switches(response.json())
    assert switches["disable_model_provider"] == {
        "name": "disable_model_provider",
        "enabled": True,
        "workspace_enabled": True,
        "environment_enabled": False,
    }
    assert switches["disable_external_egress"]["enabled"] is True
    record = db_session.scalar(select(WorkspaceKillSwitchState))
    assert record is not None
    audit = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "security_kill_switch_changed")
    )
    assert audit is not None
    assert audit.event_metadata["changes"] == {
        "disable_model_provider": True,
        "disable_external_egress": True,
    }

    read_response = client.get("/api/security/kill-switches")
    assert read_response.status_code == 200
    assert _switches(read_response.json())["disable_model_provider"]["enabled"] is True


def test_environment_kill_switch_is_visible_as_an_effective_global_override(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DISABLE_EXTERNAL_MCP", "true")
    get_settings.cache_clear()
    try:
        response = client.get("/api/security/kill-switches")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    switch = _switches(response.json())["disable_external_mcp"]
    assert switch["enabled"] is True
    assert switch["workspace_enabled"] is False
    assert switch["environment_enabled"] is True


def test_only_workspace_owners_can_change_kill_switches(client: TestClient) -> None:
    admin_read = client.get(
        "/api/security/kill-switches",
        headers={"X-Dev-User-Role": "admin"},
    )
    response = client.patch(
        "/api/security/kill-switches",
        headers={"X-Dev-User-Role": "editor"},
        json={"disable_memory_writes": True},
    )
    editor_read = client.get(
        "/api/security/kill-switches",
        headers={"X-Dev-User-Role": "editor"},
    )

    assert admin_read.status_code == 200
    assert response.status_code == 403
    assert editor_read.status_code == 403
