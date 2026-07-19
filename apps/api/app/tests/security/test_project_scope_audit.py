import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuthenticationEvent, SecurityAlert, SecurityEvent


def test_cross_workspace_project_lookup_is_non_enumerating_and_audited(
    client: TestClient,
    db_session: Session,
) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}
    project = client.post("/api/projects", headers=user_a_headers, json={"name": "Private"})
    project_id = project.json()["id"]
    user_b = client.get("/api/me", headers=user_b_headers)
    user_b_id = uuid.UUID(user_b.json()["user"]["id"])
    workspace_b_id = uuid.UUID(user_b.json()["workspace"]["id"])

    response = client.get(f"/api/projects/{project_id}", headers=user_b_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Project not found."}
    event = db_session.scalar(
        select(AuthenticationEvent).where(
            AuthenticationEvent.event_type == "cross_tenant_access_attempt",
            AuthenticationEvent.reason_code == "project_scope_denied",
        )
    )
    assert event is not None
    assert event.workspace_id == workspace_b_id
    assert event.user_id == user_b_id
    assert project_id not in str(event.__dict__)

    security_event = db_session.scalar(
        select(SecurityEvent).where(SecurityEvent.event_type == "cross_project_access_denied")
    )
    assert security_event is not None
    assert security_event.workspace_id == workspace_b_id
    assert security_event.user_id == user_b_id
    assert security_event.project_id is None
    assert security_event.attributes == {"reason_code": "project_scope_denied"}
    assert project_id not in str(security_event.__dict__)


def test_repeated_cross_workspace_project_lookups_raise_one_enumeration_alert(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SECURITY_CROSS_PROJECT_ENUMERATION_THRESHOLD", "3")
    get_settings.cache_clear()
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}
    project_id = client.post(
        "/api/projects", headers=user_a_headers, json={"name": "Private"}
    ).json()["id"]
    user_b = client.get("/api/me", headers=user_b_headers)
    user_b_id = uuid.UUID(user_b.json()["user"]["id"])
    workspace_b_id = uuid.UUID(user_b.json()["workspace"]["id"])

    for _ in range(4):
        response = client.get(f"/api/projects/{project_id}", headers=user_b_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    denials = list(
        db_session.scalars(
            select(SecurityEvent).where(SecurityEvent.event_type == "cross_project_access_denied")
        )
    )
    escalations = list(
        db_session.scalars(
            select(SecurityEvent).where(
                SecurityEvent.event_type == "cross_project_enumeration_attempts"
            )
        )
    )
    alerts = list(
        db_session.scalars(
            select(SecurityAlert)
            .join(SecurityEvent, SecurityAlert.security_event_id == SecurityEvent.id)
            .where(SecurityEvent.event_type == "cross_project_enumeration_attempts")
        )
    )

    assert len(denials) == 4
    assert all(event.workspace_id == workspace_b_id for event in denials)
    assert all(event.user_id == user_b_id for event in denials)
    assert all(event.project_id is None for event in denials)
    assert all(project_id not in str(event.__dict__) for event in denials)
    assert len(escalations) == 1
    assert escalations[0].severity == "high"
    assert escalations[0].source == "auth"
    assert escalations[0].project_id is None
    assert escalations[0].attributes == {"observed_count": 3, "window_seconds": 900}
    assert project_id not in str(escalations[0].__dict__)
    assert len(alerts) == 1
    assert alerts[0].severity == "high"
    assert alerts[0].project_id is None
    get_settings.cache_clear()
