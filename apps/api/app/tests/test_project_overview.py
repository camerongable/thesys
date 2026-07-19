import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvidenceSource


def test_project_overview_guides_new_project(client: TestClient) -> None:
    project_response = client.post(
        "/api/projects",
        json={
            "name": "Plant care idea",
            "short_description": "AI guidance for beginner houseplant owners.",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    overview_response = client.get(f"/api/projects/{project_id}/overview")
    assert overview_response.status_code == 200
    overview = overview_response.json()

    assert overview["strategic_snapshot"]["current_stage"] == "draft_idea"
    assert overview["current_recommendation"]["recommendation"] == (
        "Do not judge the idea yet. First define the target user, problem, and riskiest belief."
    )
    assert overview["next_best_action"]["label"] == "Define the thesis"
    assert overview["idea_readiness"]["score"] < 50
    assert "checks" not in overview["idea_readiness"]
    assert overview["evidence_health"]["source_count"] == 0
    playbook = {step["key"]: step for step in overview["playbook_steps"]}
    assert list(playbook) == ["guide", "thesis", "research", "test", "decision", "history"]
    assert playbook["thesis"]["label"] == "Thesis"
    assert playbook["thesis"]["purpose"] == "Shape the idea"
    assert playbook["thesis"]["status"] == "current"
    assert playbook["thesis"]["is_current_stage"] is True
    assert playbook["research"]["status"] == "blocked"
    assert playbook["test"]["status"] == "blocked"
    assert playbook["decision"]["status"] == "blocked"
    assert playbook["history"]["status"] == "available"

    action_response = client.post(f"/api/projects/{project_id}/next-action")
    assert action_response.status_code == 200
    assert action_response.json()["action_type"] == "structure_idea"


def test_project_overview_summarizes_demo_project(client: TestClient) -> None:
    seed_response = client.post("/api/demo/seed")
    assert seed_response.status_code == 200
    project_id = seed_response.json()["project"]["id"]

    overview_response = client.get(f"/api/projects/{project_id}/overview")
    assert overview_response.status_code == 200
    overview = overview_response.json()

    assert overview["strategic_snapshot"]["current_stage"] == "decision_ready"
    assert overview["next_best_action"]["label"] == "Review validation evidence"
    assert overview["idea_readiness"]["status"] == "decision_ready"
    assert overview["idea_readiness"]["score"] == 100
    assert overview["evidence_health"]["source_count"] >= 3
    assert overview["evidence_health"]["cited_claim_count"] >= 1
    assert overview["current_recommendation"]["source_artifact_ids"]
    assert overview["key_assumptions"]
    assert overview["key_risks"]
    playbook = {step["key"]: step for step in overview["playbook_steps"]}
    assert playbook["guide"]["status"] == "available"
    assert playbook["thesis"]["status"] == "complete"
    assert playbook["research"]["status"] == "complete"
    assert playbook["test"]["status"] == "complete"
    assert playbook["decision"]["status"] == "current"
    assert playbook["decision"]["is_current_stage"] is True
    assert playbook["history"]["status"] == "available"
    assert playbook["history"]["target_route"].endswith("#history")

    updates_response = client.get(f"/api/projects/{project_id}/strategic-updates")
    assert updates_response.status_code == 200
    updates = updates_response.json()
    assert updates
    assert any(update["title"] == "Decision recorded" for update in updates)
    assert all("why_it_matters" in update for update in updates)

    readiness_response = client.get(f"/api/projects/{project_id}/readiness")
    assert readiness_response.status_code == 200
    assert readiness_response.json()["recommended_next_action"] == "Review validation evidence"


def test_project_updates_hide_quarantined_source_workflow_summary(
    client: TestClient,
    db_session: Session,
) -> None:
    project_response = client.post("/api/projects", json={"name": "Overview trace policy"})
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    source_text = "overview trace content must not replay after source quarantine"
    source_response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Overview source", "text": source_text},
    )
    assert source_response.status_code == 201

    source = db_session.scalar(
        select(EvidenceSource).where(EvidenceSource.id == uuid.UUID(source_response.json()["id"]))
    )
    assert source is not None
    source.source_metadata = {
        **source.source_metadata,
        "security": {
            **source.source_metadata["security"],
            "security_status": "quarantined",
        },
        "source_trust": {
            **source.source_metadata["source_trust"],
            "security_status": "quarantined",
        },
    }
    db_session.commit()

    updates_response = client.get(f"/api/projects/{project_id}/strategic-updates")
    overview_response = client.get(f"/api/projects/{project_id}/overview")

    assert updates_response.status_code == 200
    assert overview_response.status_code == 200
    assert source_text not in updates_response.text
    assert source_text not in overview_response.text
