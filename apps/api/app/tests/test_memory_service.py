import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ProjectMemoryItem, ToolInvocation
from app.services import memory_service, tool_service
from app.services.identity_service import ensure_dev_identity


def test_memory_types_are_filtered_and_stale_memory_is_excluded(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    active = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        title="Riskiest assumption",
        summary="Coaches will pay for weekly check-in triage.",
        content={"text": "Coaches will pay for weekly check-in triage."},
        entity_type="assumption",
        entity_id=uuid.uuid4(),
        source_entity_type="artifact_version",
        source_entity_id=uuid.uuid4(),
        confidence_score=Decimal("0.55"),
    )
    stale = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="episodic",
        write_policy="derived_read_only",
        title="Old research event",
        summary="Early research event that has been superseded.",
        content={"event": "old"},
        status_value="stale",
    )
    db_session.commit()

    active_items = memory_service.list_memory(db_session, auth, project_id)
    assert [item.id for item in active_items] == [active.id]

    all_items = memory_service.list_memory(
        db_session,
        auth,
        project_id,
        include_stale=True,
    )
    assert {item.id for item in all_items} == {active.id, stale.id}

    selected = memory_service.select_memory_for_workflow(
        db_session,
        auth,
        project_id,
        workflow_type="agentic_research",
    )
    assert active.id in {item.id for item in selected}
    assert stale.id not in {item.id for item in selected}


def test_memory_explanation_and_duplicate_merge(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    source_id = uuid.uuid4()
    keeper = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="project",
        write_policy="direct",
        title="Current wedge",
        summary="Weekly check-in triage for independent coaches.",
        content={"wedge": "weekly check-in triage"},
        source_entity_type="thesis_canvas",
        source_entity_id=source_id,
        provenance_metadata={"source": "thesis_canvas", "source_entity_id": str(source_id)},
    )
    duplicate = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="project",
        write_policy="direct",
        title="Duplicate wedge",
        summary="Weekly check-in triage.",
        content={"wedge": "weekly check-in triage"},
    )
    db_session.commit()

    explanation = memory_service.explain_memory(db_session, auth, project_id, keeper.id)
    assert explanation["memory_item"]["id"] == str(keeper.id)
    assert "project memory" in explanation["explanation"]
    assert explanation["provenance"]["source"] == "thesis_canvas"

    memory_service.merge_duplicates(
        db_session,
        auth,
        project_id,
        keeper_id=keeper.id,
        duplicate_ids=[duplicate.id],
    )
    db_session.refresh(duplicate)
    assert duplicate.status == "superseded"
    assert duplicate.superseded_by_id == keeper.id


def test_project_memory_tool_uses_governed_read_boundary(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")
    memory_service.upsert_memory_item(
        db_session,
        owner_auth,
        project_id,
        memory_type="preference",
        write_policy="direct",
        title="Validation preference",
        summary="Prefer lightweight concierge tests before surveys.",
        content={"preference": "concierge tests"},
    )
    db_session.commit()

    viewer_auth = _dev_auth(db_session, "viewer")
    result = tool_service.execute_tool(
        db_session,
        viewer_auth,
        get_settings(),
        project_id,
        "list_project_memory",
        {"workflow_type": "guide_chat", "limit": 5},
        requested_by="agent",
    )

    assert result.output["memory_items"][0]["memory_type"] == "preference"
    invocation = db_session.scalar(
        select(ToolInvocation).where(ToolInvocation.tool_name == "list_project_memory")
    )
    assert invocation is not None
    assert invocation.access_mode == "read"
    assert invocation.status == "executed"


def test_memory_api_can_mark_items_stale(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    item = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        title="Assumption",
        summary="The target user has urgent pain.",
        content={"text": "The target user has urgent pain."},
    )
    db_session.commit()

    response = client.post(f"/api/projects/{project_id}/memory/{item.id}/stale")

    assert response.status_code == 200
    assert response.json()["status"] == "stale"
    active_response = client.get(f"/api/projects/{project_id}/memory")
    assert active_response.status_code == 200
    assert active_response.json()["memory_items"] == []


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "Memory architecture project"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _dev_auth(db_session: Session, role: str):
    settings = get_settings()
    return ensure_dev_identity(
        db_session,
        email=settings.dev_auth_default_email,
        display_name=settings.dev_auth_default_name,
        role=role,
    )
