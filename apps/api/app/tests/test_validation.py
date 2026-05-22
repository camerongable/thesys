import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    Decision,
    DecisionLink,
    Experiment,
    ExperimentResult,
)


def test_extract_assumptions_and_risks(client: TestClient, db_session: Session) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Founder research OS",
            "short_description": "A stateful workspace for source-backed founder research.",
            "initial_thesis": "Founders need evidence, assumptions, and decisions in one place.",
        },
    )
    project_id = create_response.json()["id"]

    response = client.post(f"/api/projects/{project_id}/assumptions/extract")

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is True
    assert len(body["assumptions"]) >= 3
    assert len(body["risks"]) >= 1
    assert body["assumptions"][0]["kill_risk"] is True
    assert body["assumptions"][0]["importance"] == "critical"

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.workflow_type == "assumption_extraction"
    assert run.status == "succeeded"
    step = db_session.scalar(select(AIStep).where(AIStep.ai_run_id == run.id))
    assert step is not None
    assert step.step_name == "extract_assumptions_risks"

    assumption_id = body["assumptions"][0]["id"]
    update_response = client.patch(
        f"/api/projects/{project_id}/assumptions/{assumption_id}",
        json={"status": "testing", "confidence_score": 0.42},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "testing"
    assert float(update_response.json()["confidence_score"]) == 0.42


def test_generate_validation_plan_and_log_result_updates_confidence(
    client: TestClient,
    db_session: Session,
) -> None:
    create_response = client.post("/api/projects", json={"name": "Validation project"})
    project_id = create_response.json()["id"]
    extract_response = client.post(f"/api/projects/{project_id}/assumptions/extract")
    assumption = extract_response.json()["assumptions"][0]
    old_confidence = float(assumption["confidence_score"])

    plan_response = client.post(
        f"/api/projects/{project_id}/experiments/validation-plan",
        json={"assumption_ids": [assumption["id"]], "max_plans": 1},
    )

    assert plan_response.status_code == 200
    plan_body = plan_response.json()
    assert plan_body["used_stub"] is True
    assert plan_body["artifact"]["artifact_type"] == "validation_plan"
    assert plan_body["artifact"]["current_version"]["version"] == 1
    assert len(plan_body["experiments"]) == 1
    experiment = plan_body["experiments"][0]
    assert experiment["assumption_id"] == assumption["id"]
    assert experiment["status"] == "planned"

    artifact = db_session.scalar(
        select(Artifact).where(Artifact.artifact_type == "validation_plan")
    )
    assert artifact is not None
    persisted_experiment = db_session.scalar(select(Experiment))
    assert persisted_experiment is not None

    result_response = client.post(
        f"/api/projects/{project_id}/experiments/{experiment['id']}/results",
        json={
            "result_summary": "Four of five founders described repeated pain and pilot interest.",
            "outcome": "positive",
            "raw_notes": "Strong signal from target respondents.",
        },
    )

    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["result"]["outcome"] == "positive"
    assert float(result_body["result"]["confidence_delta"]) == 0.15
    assert result_body["experiment"]["status"] == "completed"
    assert result_body["assumption"]["status"] == "validated"
    assert float(result_body["assumption"]["confidence_score"]) > old_confidence
    assert result_body["project_confidence_score"] is not None
    assert db_session.scalar(select(ExperimentResult)) is not None


def test_create_decision_with_links(client: TestClient, db_session: Session) -> None:
    create_response = client.post("/api/projects", json={"name": "Decision project"})
    project_id = create_response.json()["id"]
    evidence_response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Interview note", "text": "Founders want decision traceability."},
    )
    extract_response = client.post(f"/api/projects/{project_id}/assumptions/extract")
    assumption_id = extract_response.json()["assumptions"][0]["id"]
    plan_response = client.post(
        f"/api/projects/{project_id}/experiments/validation-plan",
        json={"assumption_ids": [assumption_id], "max_plans": 1},
    )
    artifact_id = plan_response.json()["artifact"]["id"]
    experiment_id = plan_response.json()["experiments"][0]["id"]

    response = client.post(
        f"/api/projects/{project_id}/decisions",
        json={
            "decision_type": "run_experiment",
            "title": "Validate founder decision traceability",
            "rationale": "The highest-risk assumption needs direct customer evidence.",
            "expected_outcome": "Decide whether to build the first workflow slice.",
            "review_date": "2026-06-15",
            "linked_assumption_ids": [assumption_id],
            "linked_evidence_source_ids": [evidence_response.json()["id"]],
            "linked_artifact_ids": [artifact_id],
            "linked_experiment_ids": [experiment_id],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["decision_type"] == "run_experiment"
    assert body["review_date"] == "2026-06-15"
    assert {link["linked_type"] for link in body["links"]} == {
        "assumption",
        "evidence",
        "artifact",
        "experiment",
    }
    assert db_session.scalar(select(Decision)) is not None
    assert len(list(db_session.scalars(select(DecisionLink)))) == 4

    list_response = client.get(f"/api/projects/{project_id}/decisions")
    assert list_response.status_code == 200
    assert list_response.json()["decisions"][0]["id"] == body["id"]
