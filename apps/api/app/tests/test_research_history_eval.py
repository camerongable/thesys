from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assumption, Risk
from app.tests.test_agentic_research import _approved_research_sprint_with_evidence


def test_research_history_tracks_approved_memory_updates(
    client: TestClient,
    monkeypatch,
) -> None:
    project_id, sprint_id = _approved_research_sprint_with_evidence(client, monkeypatch)
    run_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run"
    )
    assert run_response.status_code == 200
    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/approve"
    )
    assert approve_response.status_code == 200

    response = client.get(f"/api/projects/{project_id}/research-history")

    assert response.status_code == 200
    body = response.json()
    assert body["sprint_count"] == 1
    assert body["completed_sprint_count"] == 1
    history = body["sprints"][0]
    assert history["sprint"]["id"] == sprint_id
    assert history["sprint"]["langsmith_trace_id"]
    assert history["sprint"]["langsmith_trace_url"]
    assert history["ingested_source_count"] >= 1
    assert history["merged_competitor_count"] >= 1
    assert history["memory_update_status"] == "approved"
    assert history["memory_update_summary"]["assumption_ids"]
    event_types = {event["event_type"] for event in history["events"]}
    assert "memo_generated" in event_types
    assert "memory_update_approved" in event_types
    assert "sprint_completed" in event_types


def test_research_memo_memory_updates_can_be_rejected(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    project_id, sprint_id = _approved_research_sprint_with_evidence(client, monkeypatch)
    run_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run"
    )
    assert run_response.status_code == 200

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/reject"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sprint"]["status"] == "completed"
    assert body["version"]["structured_content"]["memory_update_status"] == "rejected"
    assert body["version"]["structured_content"]["memory_updates_written"] is False
    assert db_session.scalar(select(Assumption)) is None
    assert db_session.scalar(select(Risk)) is None

    history_response = client.get(f"/api/projects/{project_id}/research-history")
    assert history_response.status_code == 200
    event_types = {
        event["event_type"]
        for event in history_response.json()["sprints"][0]["events"]
    }
    assert "memory_update_rejected" in event_types


def test_v1_research_eval_passes_for_completed_research_sprint(
    client: TestClient,
    monkeypatch,
) -> None:
    project_id, sprint_id = _approved_research_sprint_with_evidence(client, monkeypatch)
    run_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run"
    )
    assert run_response.status_code == 200
    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/approve"
    )
    assert approve_response.status_code == 200

    response = client.get(f"/api/projects/{project_id}/evals/v1-research")

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["score"] == body["total"]
    assert body["dataset_case_count"] == 10
    assert body["demo_ready_case_count"] >= 5
    metrics = {metric["key"]: metric for metric in body["metrics"]}
    assert metrics["research_memo_completeness"]["passed"] is True
    assert metrics["langsmith_trace_ids"]["passed"] is True
    assert metrics["langsmith_span_coverage"]["passed"] is True
    assert metrics["secret_redaction"]["passed"] is True
