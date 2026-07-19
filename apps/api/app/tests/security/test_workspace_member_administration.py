import uuid

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, AuthenticationEvent, User, WorkspaceMember


def test_workspace_owner_updates_member_role_and_records_attributable_audit_events(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = client.get("/api/me")
    workspace_id = uuid.UUID(owner.json()["workspace"]["id"])
    owner_id = uuid.UUID(owner.json()["user"]["id"])
    member = User(
        external_auth_id="test:member@example.com",
        email="member@example.com",
        display_name="Member",
    )
    db_session.add(member)
    db_session.flush()
    membership = WorkspaceMember(workspace_id=workspace_id, user_id=member.id, role="viewer")
    db_session.add(membership)
    db_session.commit()

    response = client.patch(
        f"/api/workspace/members/{member.id}/role",
        json={"role": "admin"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"user_id": str(member.id), "role": "admin"}
    db_session.refresh(membership)
    assert membership.role == "admin"
    authentication_event = db_session.scalar(
        select(AuthenticationEvent).where(AuthenticationEvent.event_type == "role_change")
    )
    assert authentication_event is not None
    assert authentication_event.workspace_id == workspace_id
    assert authentication_event.user_id == owner_id
    assert authentication_event.authentication_method == "dev"
    assert authentication_event.reason_code == "workspace_member_role_updated"
    governance_event = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "workspace_member_role_changed")
    )
    assert governance_event is not None
    assert governance_event.workspace_id == workspace_id
    assert governance_event.user_id == owner_id
    assert governance_event.entity_id == membership.id
    assert governance_event.event_metadata == {
        "previous_role": "viewer",
        "new_role": "admin",
        "request_id": governance_event.event_metadata["request_id"],
    }
    assert (
        str(uuid.UUID(governance_event.event_metadata["request_id"]))
        == governance_event.event_metadata["request_id"]
    )


def test_non_owner_cannot_update_workspace_member_role(
    client: TestClient,
    db_session: Session,
) -> None:
    viewer = client.get(
        "/api/me",
        headers={
            "X-Dev-User-Email": "viewer@example.com",
            "X-Dev-User-Name": "Viewer",
            "X-Dev-User-Role": "viewer",
        },
    )
    target_user_id = viewer.json()["user"]["id"]

    response = client.patch(
        f"/api/workspace/members/{target_user_id}/role",
        json={"role": "admin"},
        headers={
            "X-Dev-User-Email": "viewer@example.com",
            "X-Dev-User-Name": "Viewer",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Only workspace owners can manage workspace membership."}
    assert db_session.scalar(
        select(AuthenticationEvent).where(AuthenticationEvent.event_type == "role_change")
    ) is None


def test_role_update_cannot_demote_the_last_workspace_owner(client: TestClient) -> None:
    owner = client.get("/api/me")
    owner_id = owner.json()["user"]["id"]

    response = client.patch(
        f"/api/workspace/members/{owner_id}/role",
        json={"role": "admin"},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "A workspace must retain at least one owner."}


def test_cross_workspace_member_update_is_non_enumerating_and_audited(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_a = client.get(
        "/api/me",
        headers={"X-Dev-User-Email": "owner-a@example.com", "X-Dev-User-Name": "Owner A"},
    )
    owner_a_id = uuid.UUID(owner_a.json()["user"]["id"])
    workspace_a_id = uuid.UUID(owner_a.json()["workspace"]["id"])
    owner_b = client.get(
        "/api/me",
        headers={"X-Dev-User-Email": "owner-b@example.com", "X-Dev-User-Name": "Owner B"},
    )
    owner_b_id = owner_b.json()["user"]["id"]

    response = client.patch(
        f"/api/workspace/members/{owner_b_id}/role",
        json={"role": "viewer"},
        headers={"X-Dev-User-Email": "owner-a@example.com", "X-Dev-User-Name": "Owner A"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Workspace member not found."}
    event = db_session.scalar(
        select(AuthenticationEvent).where(
            AuthenticationEvent.event_type == "cross_tenant_access_attempt"
        )
    )
    assert event is not None
    assert event.workspace_id == workspace_a_id
    assert event.user_id == owner_a_id
    assert event.reason_code == "workspace_member_outside_scope"
    assert owner_b_id not in str(event.__dict__)
