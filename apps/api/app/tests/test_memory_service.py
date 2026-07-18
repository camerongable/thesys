import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditEvent, ProjectMemoryItem, ToolInvocation
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


def test_project_memory_redacts_secret_values_before_persistence(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    sentinel = "sk-memory-secret-value"

    item = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="project",
        write_policy="direct",
        title=f"Credential {sentinel}",
        summary=f"api_key={sentinel}",
        content={"api_key": sentinel, "safe": "visible"},
        provenance_metadata={"authorization": f"Bearer {sentinel}"},
    )
    db_session.flush()

    assert sentinel not in item.title
    assert sentinel not in item.summary
    assert item.content == {"api_key": "[redacted]", "safe": "visible"}
    assert item.provenance_metadata["authorization"] == "[redacted]"
    assert item.provenance_metadata["policy_version"] == "secure-memory:v1"
    assert item.provenance_metadata["content_hash"]
    assert item.provenance_metadata["origin"] == "user"
    assert item.provenance_metadata["security_status"] == "approved"


def test_evidence_derived_agent_memory_requires_approval_before_recall(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    source_id = uuid.uuid4()
    expiry = datetime.now(UTC) + timedelta(days=1)

    item = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        title="Retrieved recommendation",
        summary="A retrieved source claims coach demand is immediate.",
        content={"claim": "coach demand is immediate"},
        source_entity_type="evidence_source",
        source_entity_id=source_id,
        provenance_metadata={"origin": "agent", "trust_score": 0.8},
        expires_at=expiry,
    )
    db_session.commit()

    assert item.status == "proposed"
    assert item.provenance_metadata["source_ids"] == [str(source_id)]
    assert memory_service.select_memory_for_workflow(
        db_session,
        auth,
        project_id,
        workflow_type="guide_chat",
    ) == []

    approved = memory_service.approve_memory_proposal(db_session, auth, project_id, item.id)
    assert approved.status == "active"
    assert approved.provenance_metadata["approved_at"]
    assert approved.provenance_metadata["security_status"] == "approved"
    assert approved.provenance_metadata["expires_at"] == expiry.isoformat()
    selected = memory_service.select_memory_for_workflow(
        db_session,
        auth,
        project_id,
        workflow_type="guide_chat",
    )
    assert [candidate.id for candidate in selected] == [item.id]


def test_working_memory_has_bounded_ttl_and_expired_memory_is_inspectable(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    now = datetime.now(UTC)
    working = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="working",
        write_policy="transient",
        title="Current guide context",
        summary="The current conversation is evaluating concierge validation.",
        content={"topic": "concierge validation"},
    )
    expired = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="direct",
        title="Expired finding",
        summary="An outdated willingness-to-pay finding.",
        content={"claim": "outdated finding"},
        expires_at=now - timedelta(seconds=1),
    )
    db_session.commit()

    assert working.expires_at is not None
    metadata_expiry = datetime.fromisoformat(working.provenance_metadata["expires_at"])
    last_verified_at = datetime.fromisoformat(working.provenance_metadata["last_verified_at"])
    assert timedelta(0) < metadata_expiry - last_verified_at <= memory_service.WORKING_MEMORY_TTL
    assert expired.expires_at is not None
    assert expired.provenance_metadata["expires_at"] == (now - timedelta(seconds=1)).isoformat()
    selected = memory_service.select_memory_for_workflow(
        db_session,
        auth,
        project_id,
        workflow_type="guide_chat",
    )
    assert [item.id for item in selected] == [working.id]
    inspect = memory_service.inspect_memory(
        db_session,
        auth,
        project_id,
        workflow_type="guide_chat",
    )
    assert {item["id"] for item in inspect["selected_memory"]} == {str(working.id)}
    assert {item["id"] for item in inspect["excluded_memory"] if item["reason"] == "expired"} == {
        expired.id
    }


def test_conflicting_memory_proposal_preserves_active_version_until_approval(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    subject_id = uuid.uuid4()
    active = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="direct",
        entity_type="assumption",
        entity_id=subject_id,
        title="Current buyer belief",
        summary="Independent coaches will pay for check-in triage.",
        content={"claim": "coaches will pay"},
    )
    db_session.commit()

    duplicate = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        entity_type="assumption",
        entity_id=subject_id,
        title="Repeated buyer belief",
        summary="Independent coaches will pay for check-in triage.",
        content={"claim": "coaches will pay"},
        provenance_metadata={"origin": "agent", "trust_score": 0.8},
        status_value="proposed",
    )
    assert duplicate.id == active.id
    assert active.status == "active"

    proposal = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        entity_type="assumption",
        entity_id=subject_id,
        title="Conflicting buyer belief",
        summary="Independent coaches will not pay for check-in triage.",
        content={"claim": "coaches will not pay"},
        provenance_metadata={"origin": "agent", "trust_score": 0.8},
        status_value="proposed",
    )
    db_session.commit()

    assert proposal.id != active.id
    assert active.status == "active"
    assert active.summary == "Independent coaches will pay for check-in triage."
    assert proposal.status == "proposed"
    assert proposal.provenance_metadata["contradicts_memory_ids"] == [str(active.id)]
    assert active.provenance_metadata["contradicts_memory_ids"] == [str(proposal.id)]
    assert active.provenance_metadata["conflict_group_id"] == (
        proposal.provenance_metadata["conflict_group_id"]
    )

    inspect = memory_service.inspect_memory(
        db_session,
        auth,
        project_id,
        workflow_type="guide_chat",
    )
    assert [item["id"] for item in inspect["selected_memory"]] == [str(active.id)]
    assert [item["id"] for item in inspect["proposed_memory"]] == [str(proposal.id)]
    assert inspect["conflicts"] == [
        {
            "conflict_group_id": proposal.provenance_metadata["conflict_group_id"],
            "reason": "Proposed memory conflicts with active memory and requires review.",
            "memory_item_ids": [proposal.id, active.id],
            "titles": [proposal.title, active.title],
        }
    ]

    approved = memory_service.approve_memory_proposal(db_session, auth, project_id, proposal.id)
    db_session.refresh(active)
    assert approved.status == "active"
    assert active.status == "superseded"
    assert active.superseded_by_id == approved.id
    assert approved.provenance_metadata["conflict_resolved_by_user_id"] == str(auth.user_id)


def test_low_trust_memory_is_excluded_from_recall_with_reason(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    item = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="project",
        write_policy="direct",
        title="Weak source",
        summary="This unsupported signal should not enter context.",
        content={"signal": "weak"},
        provenance_metadata={"trust_score": 0.1},
    )
    db_session.commit()

    selection = memory_service.select_memory_for_context(
        db_session,
        auth,
        project_id,
        workflow_type="guide_chat",
    )
    assert selection.selected == []
    assert selection.excluded == [
        {
            "id": item.id,
            "memory_type": "project",
            "status": "active",
            "title": "Weak source",
            "reason": "memory_trust_below_threshold",
        }
    ]


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


def test_memory_context_selection_explains_exclusions_and_conflicts(
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
        title="Target pain",
        summary="Coaches need triage before weekly check-ins.",
        content={"text": "Coaches need triage before weekly check-ins."},
    )
    memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="preference",
        write_policy="approval_required",
        title="Validation preference",
        summary="Prefer concierge tests.",
        content={"preference": "concierge"},
        status_value="proposed",
    )
    first_conflict = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="project",
        write_policy="direct",
        title="Current wedge",
        summary="Weekly check-in triage for independent coaches.",
        content={"wedge": "coaches"},
    )
    second_conflict = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="project",
        write_policy="direct",
        title="Current wedge",
        summary="Weekly scheduling automation for agencies.",
        content={"wedge": "agencies"},
    )
    db_session.commit()

    selection = memory_service.select_memory_for_context(
        db_session,
        auth,
        project_id,
        workflow_type="guide_chat",
    )

    assert active.id in {item.id for item in selection.selected}
    assert any(item["reason"] == "pending_human_review" for item in selection.excluded)
    assert selection.conflicts
    conflict = selection.conflicts[0]
    assert {first_conflict.id, second_conflict.id}.issubset(set(conflict["memory_item_ids"]))

    keeper = memory_service.resolve_memory_conflict(
        db_session,
        auth,
        project_id,
        conflict_group_id=conflict["conflict_group_id"],
        keeper_id=first_conflict.id,
        supersede_ids=[second_conflict.id],
        archive_ids=[],
        reason="Coach wedge is the approved current thesis.",
    )
    db_session.refresh(second_conflict)
    assert keeper.status == "active"
    assert second_conflict.status == "superseded"
    assert second_conflict.superseded_by_id == keeper.id


def test_memory_proposals_and_inspect_endpoint(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    source = memory_service.upsert_memory_item(
        db_session,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="direct",
        title="Research finding",
        summary="Two coaches asked for triage before calls.",
        content={"finding": "triage before calls"},
        source_entity_type="artifact_version",
        source_entity_id=uuid.uuid4(),
    )
    db_session.commit()

    preference_response = client.post(
        f"/api/projects/{project_id}/memory/preferences",
        json={
            "title": "Validation style",
            "summary": "Prefer concierge tests before surveys.",
            "content": {"preference": "concierge first"},
        },
    )
    assert preference_response.status_code == 200
    preference = preference_response.json()
    assert preference["memory_type"] == "preference"
    assert preference["status"] == "proposed"

    inspect_response = client.get(
        f"/api/projects/{project_id}/memory/inspect?workflow_type=guide_chat"
    )
    assert inspect_response.status_code == 200
    inspect = inspect_response.json()
    assert inspect["policy"]["workflow_type"] == "guide_chat"
    assert any(item["id"] == str(source.id) for item in inspect["selected_memory"])
    assert any(item["id"] == preference["id"] for item in inspect["proposed_memory"])
    assert any(item["reason"] == "pending_human_review" for item in inspect["excluded_memory"])

    approve_response = client.post(f"/api/projects/{project_id}/memory/{preference['id']}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "active"

    compact_response = client.post(
        f"/api/projects/{project_id}/memory/compact",
        json={
            "workflow_type": "guide_chat",
            "memory_type": "semantic",
            "source_memory_ids": [str(source.id)],
        },
    )
    assert compact_response.status_code == 200
    compacted = compact_response.json()
    assert compacted["status"] == "proposed"
    assert compacted["title"] == "Compacted guide_chat memory"
    assert compacted["summary"] == "Two coaches asked for triage before calls."
    assert compacted["content"] == {
        "summary": "Two coaches asked for triage before calls.",
        "source_memory_ids": [str(source.id)],
        "source_memory_titles": ["Research finding"],
        "workflow_type": "guide_chat",
    }
    assert compacted["provenance_metadata"]["source_memory_ids"] == [str(source.id)]
    assert compacted["provenance_metadata"]["source_entity_refs"] == [
        {
            "memory_id": str(source.id),
            "source_entity_type": "artifact_version",
            "source_entity_id": str(source.source_entity_id),
            "superseded_by_id": None,
        }
    ]

    reject_response = client.post(f"/api/projects/{project_id}/memory/{compacted['id']}/reject")
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "archived"
    rejected = db_session.scalar(
        select(ProjectMemoryItem).where(ProjectMemoryItem.id == uuid.UUID(compacted["id"]))
    )
    assert rejected is not None
    assert rejected.status == "archived"
    assert rejected.provenance_metadata["rejected_by_user_id"] == str(auth.user_id)
    assert rejected.provenance_metadata["rejected_at"]
    assert rejected.provenance_metadata["source"] == "memory_compaction"
    review_event = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "memory_update_rejected",
            AuditEvent.entity_type == "project_memory_item",
            AuditEvent.entity_id == rejected.id,
        )
    )
    assert review_event is not None
    assert review_event.risk_level == "medium"
    assert review_event.event_metadata == {
        "memory_item_id": str(rejected.id),
        "memory_type": "semantic",
        "status": "rejected",
        "proposal_kind": "memory_compaction",
        "source_entity_type": "memory_compaction",
        "source_entity_id": None,
    }

    inspect_after_reject_response = client.get(
        f"/api/projects/{project_id}/memory/inspect?workflow_type=guide_chat"
    )
    assert inspect_after_reject_response.status_code == 200
    inspect_after_reject = inspect_after_reject_response.json()
    assert all(
        item["id"] != compacted["id"] for item in inspect_after_reject["proposed_memory"]
    )
    assert all(
        item["id"] != compacted["id"] for item in inspect_after_reject["selected_memory"]
    )


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
