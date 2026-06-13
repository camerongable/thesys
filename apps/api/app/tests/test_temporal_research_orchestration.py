import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ResearchSprint


def _enable_temporal(monkeypatch) -> None:
    monkeypatch.setenv("TEMPORAL_ENABLED", "true")
    get_settings.cache_clear()


async def _fake_start(settings, payload):
    return "temporal-run-test"


async def _fake_signal(settings, workflow_id, signal_name):
    return None


async def _fake_cancel(settings, workflow_id):
    return None


def _create_planned_sprint(client: TestClient) -> tuple[str, dict]:
    project_response = client.post(
        "/api/projects",
        json={
            "name": "Durable research idea",
            "short_description": "AI workspace for validating a niche business idea.",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={"objective": "Investigate sources, competitors, and validation risk."},
    )
    assert plan_response.status_code == 200
    return project_id, plan_response.json()["sprint"]


def test_temporal_enabled_plan_start_stores_workflow_metadata(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    _enable_temporal(monkeypatch)
    monkeypatch.setattr(
        "app.services.temporal_research_service._start_temporal_workflow",
        _fake_start,
    )

    project_id, sprint = _create_planned_sprint(client)

    assert sprint["status"] == "waiting_for_approval"
    assert sprint["temporal_workflow_id"].startswith("research-sprint-")
    assert sprint["temporal_run_id"] == "temporal-run-test"
    assert sprint["current_step"] == "wait_for_research_plan_approval"

    persisted = db_session.scalar(
        select(ResearchSprint).where(ResearchSprint.id == uuid.UUID(sprint["id"]))
    )
    assert persisted is not None
    assert persisted.temporal_workflow_id == sprint["temporal_workflow_id"]

    status_response = client.get(
        f"/api/projects/{project_id}/research-sprints/{sprint['id']}/durable/status"
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["temporal_enabled"] is True
    assert status_body["action_required"] == "Approve research plan"


def test_research_plan_approval_signals_temporal_workflow(
    client: TestClient,
    monkeypatch,
) -> None:
    _enable_temporal(monkeypatch)
    signals: list[tuple[str, str]] = []

    async def capture_signal(settings, workflow_id, signal_name):
        signals.append((workflow_id, signal_name))

    monkeypatch.setattr(
        "app.services.temporal_research_service._start_temporal_workflow",
        _fake_start,
    )
    monkeypatch.setattr(
        "app.services.temporal_research_service._signal_temporal_workflow",
        capture_signal,
    )
    project_id, sprint = _create_planned_sprint(client)

    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint['id']}/approve",
        json={},
    )

    assert approve_response.status_code == 200
    approved = approve_response.json()["sprint"]
    assert approved["status"] == "approved"
    assert (sprint["temporal_workflow_id"], "approve_research_plan") in signals


def test_failed_temporal_workflow_can_be_retried(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    _enable_temporal(monkeypatch)
    monkeypatch.setattr(
        "app.services.temporal_research_service._start_temporal_workflow",
        _fake_start,
    )
    project_id, sprint = _create_planned_sprint(client)
    persisted = db_session.scalar(
        select(ResearchSprint).where(ResearchSprint.id == uuid.UUID(sprint["id"]))
    )
    assert persisted is not None
    persisted.status = "failed"
    persisted.failed_step = "ingest_sources"
    persisted.failure_message = "fetch failed"
    db_session.commit()

    retry_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint['id']}/durable/retry"
    )

    assert retry_response.status_code == 200
    retried = retry_response.json()["sprint"]
    assert retried["status"] == "waiting_for_approval"
    assert "-retry-" in retried["temporal_workflow_id"]
    assert retried["failed_step"] is None
    assert retried["failure_message"] is None


def test_temporal_workflow_can_be_cancelled(
    client: TestClient,
    monkeypatch,
) -> None:
    _enable_temporal(monkeypatch)
    cancelled: list[str] = []

    async def capture_cancel(settings, workflow_id):
        cancelled.append(workflow_id)

    monkeypatch.setattr(
        "app.services.temporal_research_service._start_temporal_workflow",
        _fake_start,
    )
    monkeypatch.setattr(
        "app.services.temporal_research_service._cancel_temporal_workflow",
        capture_cancel,
    )
    project_id, sprint = _create_planned_sprint(client)

    cancel_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint['id']}/durable/cancel"
    )

    assert cancel_response.status_code == 200
    cancelled_body = cancel_response.json()["sprint"]
    assert cancelled_body["status"] == "cancelled"
    assert cancelled == [sprint["temporal_workflow_id"]]


def test_durable_status_is_available_when_temporal_is_disabled(client: TestClient) -> None:
    project_id, sprint = _create_planned_sprint(client)

    status_response = client.get(
        f"/api/projects/{project_id}/research-sprints/{sprint['id']}/durable/status"
    )

    assert status_response.status_code == 200
    body = status_response.json()
    assert body["temporal_enabled"] is False
    assert body["temporal_workflow_id"] is None
    assert body["status"] == "planned"
