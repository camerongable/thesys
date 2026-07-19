import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthenticationEvent, SecurityAlert, SecurityEvent, ToolInvocation


def test_cross_workspace_decision_and_tool_lookups_are_non_enumerating_and_audited(
    client: TestClient,
    db_session: Session,
) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}
    owner_a = client.get("/api/me", headers=user_a_headers)
    workspace_a_id = uuid.UUID(owner_a.json()["workspace"]["id"])
    project = client.post("/api/projects", headers=user_a_headers, json={"name": "Private"})
    project_id = uuid.UUID(project.json()["id"])
    decision = client.post(
        f"/api/projects/{project_id}/decisions",
        headers=user_a_headers,
        json={"decision_type": "build", "title": "Keep private"},
    )
    decision_id = decision.json()["id"]
    invocation = ToolInvocation(
        workspace_id=workspace_a_id,
        project_id=project_id,
        tool_name="propose_decision",
        access_mode="proposal",
        risk_level="high",
        input_json={},
        status="requested",
        requested_by="user",
    )
    db_session.add(invocation)
    db_session.commit()
    user_b = client.get("/api/me", headers=user_b_headers)
    workspace_b_id = uuid.UUID(user_b.json()["workspace"]["id"])
    user_b_id = uuid.UUID(user_b.json()["user"]["id"])

    decision_response = client.get(
        f"/api/projects/{project_id}/decisions/{decision_id}",
        headers=user_b_headers,
    )
    tool_response = client.post(
        f"/api/projects/{project_id}/tool-invocations/{invocation.id}/approve",
        headers=user_b_headers,
    )

    assert decision_response.status_code == status.HTTP_404_NOT_FOUND
    assert decision_response.json() == {"detail": "Decision not found."}
    assert tool_response.status_code == status.HTTP_404_NOT_FOUND
    assert tool_response.json() == {"detail": "Tool invocation not found."}
    events = {
        event.reason_code: event
        for event in db_session.scalars(
            select(AuthenticationEvent).where(
                AuthenticationEvent.event_type == "cross_tenant_access_attempt"
            )
        )
    }
    assert set(events) == {"decision_scope_denied", "tool_invocation_scope_denied"}
    for event in events.values():
        assert event.workspace_id == workspace_b_id
        assert event.user_id == user_b_id
        persisted_event = str(event.__dict__)
        assert str(project_id) not in persisted_event
        assert decision_id not in persisted_event
        assert str(invocation.id) not in persisted_event


def test_cross_tenant_evidence_source_id_lookup_creates_redacted_security_alert(
    client: TestClient,
    db_session: Session,
) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}
    project_a_id = client.post(
        "/api/projects", headers=user_a_headers, json={"name": "Private source"}
    ).json()["id"]
    source_id = client.post(
        f"/api/projects/{project_a_id}/evidence/note",
        headers=user_a_headers,
        json={"title": "Private note", "text": "Private founder research."},
    ).json()["id"]
    user_b = client.get("/api/me", headers=user_b_headers)
    workspace_b_id = uuid.UUID(user_b.json()["workspace"]["id"])
    user_b_id = uuid.UUID(user_b.json()["user"]["id"])
    project_b_id = client.post(
        "/api/projects", headers=user_b_headers, json={"name": "User B project"}
    ).json()["id"]

    response = client.get(
        f"/api/projects/{project_b_id}/evidence/{source_id}", headers=user_b_headers
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Evidence source not found."}
    auth_event = db_session.scalar(
        select(AuthenticationEvent).where(
            AuthenticationEvent.event_type == "cross_tenant_access_attempt",
            AuthenticationEvent.reason_code == "evidence_source_scope_denied",
        )
    )
    assert auth_event is not None
    assert auth_event.workspace_id == workspace_b_id
    assert auth_event.user_id == user_b_id
    assert source_id not in str(auth_event.__dict__)
    assert project_a_id not in str(auth_event.__dict__)

    security_event = db_session.scalar(
        select(SecurityEvent).where(SecurityEvent.event_type == "cross_tenant_source_id_access")
    )
    assert security_event is not None
    assert security_event.workspace_id == workspace_b_id
    assert security_event.project_id == uuid.UUID(project_b_id)
    assert security_event.user_id == user_b_id
    assert security_event.severity == "high"
    assert security_event.source == "auth"
    assert security_event.attributes == {"reason_code": "evidence_source_scope_denied"}
    assert source_id not in str(security_event.__dict__)
    assert project_a_id not in str(security_event.__dict__)
    alert = db_session.scalar(
        select(SecurityAlert).where(SecurityAlert.security_event_id == security_event.id)
    )
    assert alert is not None
    assert alert.workspace_id == workspace_b_id
    assert alert.project_id == uuid.UUID(project_b_id)
    assert alert.severity == "high"
