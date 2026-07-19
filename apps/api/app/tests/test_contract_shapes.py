import uuid

from fastapi.testclient import TestClient


def test_evidence_source_response_contract_preserves_metadata_shape(
    client: TestClient,
) -> None:
    project = client.post("/api/projects", json={"name": "Contract evidence"}).json()

    response = client.post(
        f"/api/projects/{project['id']}/evidence/note",
        json={
            "title": "Pricing note",
            "text": "Competitor pricing suggests coaches already pay for workflow tools.",
            "source_type": "note",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) >= {
        "id",
        "project_id",
        "source_type",
        "title",
        "summary",
        "classification",
        "credibility_score",
        "metadata",
        "ingestion_status",
        "chunk_count",
        "text_preview",
    }
    assert body["source_type"] == "note"
    assert body["ingestion_status"] == "ready"
    assert body["chunk_count"] == 1
    assert body["metadata"]["content_hash"]
    assert body["metadata"]["source_quality"]["policy_version"]
    assert body["metadata"]["extraction_method"] == "normalized_text"


def test_artifact_list_response_contract_preserves_version_structured_content(
    client: TestClient,
) -> None:
    seed = client.post("/api/demo/seed")
    assert seed.status_code == 200
    project_id = seed.json()["project"]["id"]

    response = client.get(f"/api/projects/{project_id}/artifacts")

    assert response.status_code == 200
    artifacts = response.json()["artifacts"]
    assert artifacts
    by_type = {artifact["artifact_type"]: artifact for artifact in artifacts}
    assert {"opportunity_brief", "competitor_landscape", "validation_plan"}.issubset(by_type)

    brief = by_type["opportunity_brief"]
    current = brief["current_version"]
    assert current["version"] == 1
    assert current["markdown_content"]
    assert current["structured_content"]["unsupported_claims"]
    assert isinstance(current["claims"], list)
    assert brief["versions"][0]["id"] == current["id"]

    validation = by_type["validation_plan"]["current_version"]
    assert validation["structured_content"]["plans"]


def test_decision_recommendation_contract_preserves_evidence_labels(
    client: TestClient,
) -> None:
    project = client.post("/api/projects", json={"name": "Contract decision"}).json()

    response = client.get(f"/api/projects/{project['id']}/decisions/recommendation")

    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {
        "recommendation",
        "rationale",
        "supporting_evidence",
        "missing_evidence",
        "risks",
        "evidence_labels",
        "suggested_decision_record",
        "action_cards",
        "context_pack",
    }
    assert body["recommendation"] == "continue_research"
    assert [(label["id"], label["severity"]) for label in body["evidence_labels"]] == [
        ("no_supporting_evidence", "warning")
    ]
    assert set(body["suggested_decision_record"]) >= {
        "decision_type",
        "title",
        "rationale",
        "expected_outcome",
        "revisit_trigger",
        "linked_assumption_ids",
        "linked_evidence_source_ids",
        "linked_experiment_ids",
    }


def test_governance_tool_and_memory_route_contracts_preserve_public_keys(
    client: TestClient,
) -> None:
    project = client.post("/api/projects", json={"name": "Contract governance"}).json()
    project_id = project["id"]

    sprint_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={"objective": "Investigate the highest-risk assumption."},
    )
    assert sprint_response.status_code == 200
    sprint_id = sprint_response.json()["sprint"]["id"]

    invocation_response = client.get(
        f"/api/projects/{project_id}/tool-invocations",
        params={"research_sprint_id": sprint_id},
    )
    assert invocation_response.status_code == 200
    invocation = next(
        item
        for item in invocation_response.json()["invocations"]
        if item["tool_name"] == "propose_research_plan"
    )
    assert set(invocation) >= {
        "id",
        "project_id",
        "research_sprint_id",
        "tool_name",
        "access_mode",
        "risk_level",
        "input_json",
        "output_json",
        "output_summary",
        "status",
        "requested_by",
        "approved_by_user_id",
        "created_at",
        "updated_at",
        "executed_at",
    }
    assert invocation["access_mode"] == "proposal"
    assert invocation["status"] == "requested"
    assert invocation["output_json"]["proposal"]["research_sprint_id"] == sprint_id

    approvals_response = client.get(
        f"/api/projects/{project_id}/approvals",
        params={"status_filter": "pending"},
    )
    assert approvals_response.status_code == 200
    approval = next(
        item
        for item in approvals_response.json()["approvals"]
        if item["entity_type"] == "tool_invocation" and item["entity_id"] == invocation["id"]
    )
    assert set(approval) >= {
        "id",
        "project_id",
        "request_type",
        "status",
        "requested_by",
        "approved_by_user_id",
        "risk_level",
        "summary",
        "proposed_change",
        "entity_type",
        "entity_id",
        "created_at",
        "updated_at",
        "resolved_at",
    }
    assert approval["request_type"] == "research_plan"
    assert approval["proposed_change"]["tool_name"] == "propose_research_plan"
    assert approval["proposed_change"]["tool_invocation_id"] == invocation["id"]

    reject_response = client.post(
        f"/api/projects/{project_id}/approvals/{approval['id']}/reject"
    )
    assert reject_response.status_code == 200
    rejected_approval = reject_response.json()["approval"]
    assert rejected_approval["status"] == "rejected"
    assert rejected_approval["resolved_at"]

    audit_response = client.get(f"/api/projects/{project_id}/audit-events")
    assert audit_response.status_code == 200
    audit_event = next(
        item
        for item in audit_response.json()["events"]
        if item["event_type"] == "tool_invocation_denied"
    )
    assert set(audit_event) >= {
        "id",
        "project_id",
        "user_id",
        "event_type",
        "actor_type",
        "actor_identity",
        "policy_decision",
        "resource_identifier",
        "entity_type",
        "entity_id",
        "summary",
        "risk_level",
        "event_metadata",
        "created_at",
        "previous_event_hash",
        "event_hash",
    }
    assert audit_event["entity_id"] == invocation["id"]
    assert audit_event["event_metadata"] == {
        "tool_name": "propose_research_plan",
        "status": "rejected",
        "request_id": audit_event["event_metadata"]["request_id"],
    }
    assert str(uuid.UUID(audit_event["event_metadata"]["request_id"])) == audit_event[
        "event_metadata"
    ]["request_id"]

    preference_response = client.post(
        f"/api/projects/{project_id}/memory/preferences",
        json={
            "title": "Validation preference",
            "summary": "Prefer concierge interviews before surveys.",
            "content": {"preference": "concierge first"},
        },
    )
    assert preference_response.status_code == 200
    memory_item = preference_response.json()
    assert set(memory_item) >= {
        "id",
        "project_id",
        "memory_type",
        "status",
        "write_policy",
        "entity_type",
        "entity_id",
        "source_entity_type",
        "source_entity_id",
        "title",
        "summary",
        "content",
        "provenance_metadata",
        "confidence_score",
        "expires_at",
        "superseded_by_id",
        "created_at",
        "updated_at",
    }
    assert memory_item["memory_type"] == "preference"
    assert memory_item["status"] == "proposed"
    assert memory_item["provenance_metadata"]["requires_human_approval"] is True

    inspect_response = client.get(
        f"/api/projects/{project_id}/memory/inspect",
        params={"workflow_type": "guide_chat"},
    )
    assert inspect_response.status_code == 200
    inspect = inspect_response.json()
    assert set(inspect) >= {
        "workflow_type",
        "selected_memory",
        "excluded_memory",
        "proposed_memory",
        "conflicts",
        "policy",
    }
    assert inspect["workflow_type"] == "guide_chat"
    assert inspect["proposed_memory"][0]["id"] == memory_item["id"]
    assert inspect["excluded_memory"][0]["reason"] == "pending_human_review"
