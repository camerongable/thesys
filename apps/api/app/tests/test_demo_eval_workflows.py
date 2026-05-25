import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.db.models import AIRun
from app.routers import workflows


def test_seed_demo_project_runs_mvp_eval_and_exposes_workflow_events(
    client: TestClient,
) -> None:
    seed_response = client.post("/api/demo/seed")

    assert seed_response.status_code == 200
    seed_body = seed_response.json()
    assert seed_body["created"] is True
    assert seed_body["project"]["name"] == "[Demo] Fitness Coach Intelligence OS"
    assert seed_body["counts"]["evidence_sources"] >= 3
    assert seed_body["counts"]["artifacts"] >= 3
    assert seed_body["counts"]["competitors"] >= 3
    assert seed_body["counts"]["assumptions"] >= 3
    assert seed_body["counts"]["experiments"] >= 1
    assert seed_body["counts"]["decisions"] >= 1

    project_id = seed_body["project"]["id"]
    eval_response = client.get(f"/api/projects/{project_id}/evals/mvp")
    assert eval_response.status_code == 200
    eval_body = eval_response.json()
    assert eval_body["passed"] is True
    assert eval_body["score"] == eval_body["total"]

    workflows_response = client.get(f"/api/projects/{project_id}/workflows")
    assert workflows_response.status_code == 200
    runs = workflows_response.json()["runs"]
    assert runs
    demo_run = next(run for run in runs if run["workflow_type"] == "demo_seed")
    assert demo_run["status"] == "succeeded"
    assert demo_run["steps"]

    run_response = client.get(f"/api/workflows/{demo_run['id']}")
    assert run_response.status_code == 200
    assert run_response.json()["workflow_type"] == "demo_seed"

    with client.stream("GET", f"/api/workflows/{demo_run['id']}/events") as event_response:
        assert event_response.status_code == 200
        body = "".join(event_response.iter_text())
    assert "demo_seed" in body
    assert "write_demo_workspace" in body


def test_workflow_event_stream_heartbeats_until_terminal(monkeypatch) -> None:
    run_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    created_at = datetime.now(UTC)
    statuses = iter(["running", "running", "succeeded"])
    times = iter([0.0, 0.0, 11.0, 12.0])

    def fake_get_run(_db, _auth, _run_id):
        run = AIRun(
            id=run_id,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_type="competitor_analysis",
            status=next(statuses),
            model_provider="litellm",
            model_name="test-model",
            prompt_version="test",
            input_summary="test",
            output_summary=None,
            total_tokens=None,
            total_cost=None,
            error=None,
            started_at=created_at,
            completed_at=None,
            created_at=created_at,
        )
        run.steps = []
        return run

    monkeypatch.setattr(workflows.workflow_service, "get_run", fake_get_run)
    monkeypatch.setattr(workflows.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(workflows.time, "monotonic", lambda: next(times))

    stream = workflows._event_stream(
        SimpleNamespace(expire_all=lambda: None),
        SimpleNamespace(),
        run_id,
    )

    first_event = next(stream)
    heartbeat = next(stream)
    terminal_event = next(stream)

    assert '"status":"running"' in first_event
    assert heartbeat == ": workflow heartbeat\n\n"
    assert '"status":"succeeded"' in terminal_event


def test_seed_demo_project_is_workspace_scoped_and_idempotent(client: TestClient) -> None:
    first = client.post("/api/demo/seed")
    second = client.post("/api/demo/seed")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["project"]["id"] == second.json()["project"]["id"]
    assert second.json()["created"] is False

    other_workspace = client.post(
        "/api/demo/seed",
        headers={"X-Dev-User-Email": "other@example.com", "X-Dev-User-Name": "Other"},
    )
    assert other_workspace.status_code == 200
    assert other_workspace.json()["created"] is True
    assert other_workspace.json()["project"]["id"] != first.json()["project"]["id"]
