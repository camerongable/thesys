import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIRun, AIStep


def test_structured_output_endpoint_uses_stub_and_logs_run(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/api/ai/test-structured-output",
        json={
            "idea": (
                "An AI platform for independent fitness coaches that summarizes check-ins "
                "and suggests adaptive training changes."
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is True
    assert body["model_provider"] == "stub"
    assert body["total_tokens"] > 0
    assert body["output"]["summary"].startswith("Deterministic summary for:")
    assert body["output"]["target_users"]
    assert body["output"]["confidence"] in ["low", "medium", "high"]

    run_id = uuid.UUID(body["ai_run_id"])
    step_id = uuid.UUID(body["ai_step_id"])

    run = db_session.scalar(select(AIRun).where(AIRun.id == run_id))
    assert run is not None
    assert run.workflow_type == "structured_output_smoke_test"
    assert run.status == "succeeded"
    assert run.total_tokens == body["total_tokens"]
    assert run.model_provider == "stub"
    assert run.prompt_version == body["prompt_version"]

    step = db_session.scalar(select(AIStep).where(AIStep.id == step_id))
    assert step is not None
    assert step.ai_run_id == run.id
    assert step.step_name == "structured_generation"
    assert step.status == "succeeded"
    assert step.output_json == body["output"]


def test_structured_output_project_id_is_workspace_scoped(client: TestClient) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}

    create_response = client.post(
        "/api/projects",
        headers=user_a_headers,
        json={"name": "Private project", "short_description": "Scoped project."},
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        "/api/ai/test-structured-output",
        headers=user_b_headers,
        json={"idea": "Analyze this", "project_id": project_id},
    )

    assert response.status_code == 404
