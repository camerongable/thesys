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
    assert seed_body["project"]["name"] == "AI Assistant for Independent Fitness Coaches"
    assert seed_body["next_url"].endswith("#guide")
    assert seed_body["counts"]["thesis_canvas"] == 1
    assert seed_body["counts"]["thesis_evolution_events"] >= 5
    assert seed_body["counts"]["wedge_options"] >= 4
    assert seed_body["counts"]["validation_missions"] >= 1
    assert seed_body["counts"]["validation_interpretations"] >= 1
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


def test_seed_demo_project_contains_guided_sprint_28_journey(
    client: TestClient,
) -> None:
    seed_body = client.post("/api/demo/seed").json()
    project_id = seed_body["project"]["id"]

    guide = client.post(f"/api/projects/{project_id}/guide/recommend")
    assert guide.status_code == 200
    guide_body = guide.json()
    assert guide_body["current_focus"]
    assert guide_body["recommended_action"]["target_route"]

    thesis = client.get(f"/api/projects/{project_id}/thesis-canvas")
    assert thesis.status_code == 200
    thesis_body = thesis.json()
    canvas = thesis_body["canvas"]
    assert canvas["original_idea"].startswith("I want an AI assistant")
    assert canvas["wedge"] == "Cited weekly check-in triage"
    assert "Generic workout plan generator" in canvas["rejected_directions"]
    evolution_titles = {event["title"] for event in thesis_body["evolution"]}
    assert {
        "Original idea captured",
        "Thesis Canvas generated",
        "Narrow wedge selected",
        "Validation result interpreted",
        "Decision Coach recommended continuing research",
    }.issubset(evolution_titles)

    wedges = client.get(f"/api/projects/{project_id}/wedges")
    assert wedges.status_code == 200
    wedge_body = wedges.json()
    assert len(wedge_body["wedges"]) >= 4
    recommended = next(
        wedge for wedge in wedge_body["wedges"] if wedge["id"] == wedge_body["recommended_wedge_id"]
    )
    assert recommended["name"] == "Cited weekly check-in triage"
    assert recommended["recommendation"] == "recommended"

    mission = client.get(f"/api/projects/{project_id}/experiments/missions/current")
    assert mission.status_code == 200
    mission_body = mission.json()["mission"]
    assert mission_body is not None
    assert mission_body["status"] == "interpreted"
    assert mission_body["latest_interpretation"] is not None
    assert mission_body["latest_interpretation"]["decision_recommendation"] == "continue_research"
    assert mission_body["latest_interpretation"]["recommended_next_action"].startswith(
        "Run a pricing-specific"
    )

    decision = client.get(f"/api/projects/{project_id}/decisions/recommendation")
    assert decision.status_code == 200
    decision_body = decision.json()
    assert decision_body["recommendation"] == "continue_research"
    assert decision_body["suggested_decision_record"]["validation_mission_id"] == mission_body["id"]
    assert decision_body["suggested_decision_record"]["linked_experiment_ids"]

    overview = client.get(f"/api/projects/{project_id}/overview")
    assert overview.status_code == 200
    overview_body = overview.json()
    assert overview_body["strategic_snapshot"]["current_stage"] == "decision_ready"
    assert overview_body["idea_readiness"]["status"] == "decision_ready"


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
