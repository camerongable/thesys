import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthenticationEvent


def test_cross_workspace_workflow_lookup_is_non_enumerating_and_audited(
    client: TestClient,
    db_session: Session,
) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}
    project = client.post("/api/projects", headers=user_a_headers, json={"name": "Private"})
    plan = client.post(
        f"/api/projects/{project.json()['id']}/research-sprints/plan",
        headers=user_a_headers,
        json={"objective": "Keep workflow metadata private."},
    )
    run_id = plan.json()["ai_run_id"]
    user_b = client.get("/api/me", headers=user_b_headers)
    workspace_b_id = uuid.UUID(user_b.json()["workspace"]["id"])
    user_b_id = uuid.UUID(user_b.json()["user"]["id"])

    response = client.get(f"/api/workflows/{run_id}", headers=user_b_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Workflow run not found."}
    event = db_session.scalar(
        select(AuthenticationEvent).where(
            AuthenticationEvent.event_type == "cross_tenant_access_attempt",
            AuthenticationEvent.reason_code == "workflow_run_scope_denied",
        )
    )
    assert event is not None
    assert event.workspace_id == workspace_b_id
    assert event.user_id == user_b_id
    assert run_id not in str(event.__dict__)
