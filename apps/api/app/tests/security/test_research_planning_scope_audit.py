import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthenticationEvent


def test_cross_workspace_research_plan_and_sprint_mutations_are_audited(
    client: TestClient,
    db_session: Session,
) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}
    project = client.post("/api/projects", headers=user_a_headers, json={"name": "Private"})
    project_id = project.json()["id"]
    plan = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        headers=user_a_headers,
        json={"objective": "Keep planning metadata private."},
    )
    sprint_id = plan.json()["sprint"]["id"]
    plan_id = plan.json()["sprint"]["plan"]["id"]
    user_b = client.get("/api/me", headers=user_b_headers)
    workspace_b_id = uuid.UUID(user_b.json()["workspace"]["id"])
    user_b_id = uuid.UUID(user_b.json()["user"]["id"])

    plan_response = client.patch(
        f"/api/projects/{project_id}/research-plans/{plan_id}",
        headers=user_b_headers,
        json={"objective": "Change another workspace plan."},
    )
    sprint_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/approve",
        headers=user_b_headers,
        json={},
    )

    assert plan_response.status_code == status.HTTP_404_NOT_FOUND
    assert plan_response.json() == {"detail": "Research plan not found."}
    assert sprint_response.status_code == status.HTTP_404_NOT_FOUND
    assert sprint_response.json() == {"detail": "Research sprint not found."}
    events = {
        event.reason_code: event
        for event in db_session.scalars(
            select(AuthenticationEvent).where(
                AuthenticationEvent.event_type == "cross_tenant_access_attempt"
            )
        )
    }
    assert set(events) == {"research_plan_scope_denied", "research_sprint_scope_denied"}
    for event in events.values():
        assert event.workspace_id == workspace_b_id
        assert event.user_id == user_b_id
        persisted_event = str(event.__dict__)
        assert project_id not in persisted_event
        assert plan_id not in persisted_event
        assert sprint_id not in persisted_event
