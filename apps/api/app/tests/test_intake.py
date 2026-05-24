import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.structured_output import StructuredOutputError
from app.core.config import get_settings
from app.db.models import AIRun, AIStep, CustomerSegment, Problem, ProjectIntake, ProjectThesis


def test_structured_intake_analyze_uses_stub_and_logs_step(
    client: TestClient,
    db_session: Session,
) -> None:
    create_response = client.post("/api/projects", json={"name": "Fitness coach OS"})
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/intake/analyze",
        json={
            "raw_idea": (
                "An AI platform for independent fitness coaches that turns check-ins "
                "and wearable data into adaptive coaching recommendations."
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is True
    assert body["model_provider"] == "stub"
    assert body["intake"]["project_name"] == "Fitness Coach Intelligence OS"
    assert "JSON fields" not in body["intake"]["one_sentence_summary"]
    assert body["intake"]["target_users"] == [
        "Independent online fitness coaches",
        "Solo personal trainers",
    ]
    assert len(body["intake"]["clarifying_questions"]) == 3
    assert body["total_tokens"] > 0

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.workflow_type == "structured_intake"
    assert run.status == "succeeded"
    assert run.project_id == uuid.UUID(project_id)

    step = db_session.scalar(select(AIStep).where(AIStep.id == uuid.UUID(body["ai_step_id"])))
    assert step is not None
    assert step.ai_run_id == run.id
    assert step.step_name == "analyze_idea"
    assert step.status == "succeeded"


def test_structured_intake_answer_refines_existing_intake(client: TestClient) -> None:
    create_response = client.post("/api/projects", json={"name": "Fitness coach OS"})
    project_id = create_response.json()["id"]

    analyze_response = client.post(
        f"/api/projects/{project_id}/intake/analyze",
        json={"raw_idea": "AI workflow for independent fitness coaches."},
    )
    initial_intake = analyze_response.json()["intake"]

    response = client.post(
        f"/api/projects/{project_id}/intake/answer",
        json={
            "raw_idea": "AI workflow for independent fitness coaches.",
            "initial_intake": initial_intake,
            "answers": [
                {
                    "question": initial_intake["clarifying_questions"][0],
                    "answer": "Start with solo online coaches who handle weekly check-ins.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intake"]["project_name"] == "Fitness Coach Intelligence OS"
    assert initial_intake["clarifying_questions"][0] not in body["intake"]["clarifying_questions"]
    assert body["ai_step_id"]


def test_structured_intake_answer_can_force_local_fallback_with_always_policy(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("LITELLM_MODEL", "dev-local-qwen")
    monkeypatch.setenv("LLM_FALLBACK_POLICY", "always")
    get_settings.cache_clear()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("local fallback should not call structured output")

    monkeypatch.setattr(
        "app.services.intake_service.generate_structured_output",
        fail_if_called,
    )
    create_response = client.post("/api/projects", json={"name": "Local intake answer"})
    project_id = create_response.json()["id"]
    initial_intake = {
        "project_name": "Plant Care Learning",
        "one_sentence_summary": "New plant owners need clearer care routines.",
        "target_users": ["New indoor plant owners"],
        "buyer_type": "consumer",
        "problem_hypotheses": ["Plant owners do not know which care advice to trust."],
        "proposed_solution": "A source-backed care workflow for indoor plants.",
        "market_category": "Plant care education",
        "business_model_guess": "Subscription",
        "suspected_competitors": ["Plant.id"],
        "key_uncertainties": ["Whether users repeat the workflow."],
        "clarifying_questions": ["Who is the first user segment?"],
    }

    response = client.post(
        f"/api/projects/{project_id}/intake/answer",
        json={
            "raw_idea": "Plant care learning workflow.",
            "initial_intake": initial_intake,
            "answers": [
                {
                    "question": "Who is the first user segment?",
                    "answer": "New indoor plant owners who have killed a plant before.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model_provider"] == "local-fallback"
    assert body["used_stub"] is True
    assert body["intake"]["clarifying_questions"] == []


def test_structured_intake_uses_emergency_fallback_after_generation_failure(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("LITELLM_MODEL", "dev-local-qwen")
    monkeypatch.setenv("LLM_FALLBACK_POLICY", "emergency")
    get_settings.cache_clear()

    def fail_generation(*args, **kwargs):
        raise StructuredOutputError("forced live generation failure")

    monkeypatch.setattr(
        "app.services.intake_service.generate_structured_output",
        fail_generation,
    )
    create_response = client.post("/api/projects", json={"name": "Emergency intake"})
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/intake/analyze",
        json={"raw_idea": "Plant care learning workflow."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model_provider"] == "local-fallback"
    assert body["used_stub"] is True
    assert body["intake"]["project_name"] == "Emergency intake"


def test_structured_intake_finalize_persists_project_state(
    client: TestClient,
    db_session: Session,
) -> None:
    create_response = client.post("/api/projects", json={"name": "Rough placeholder"})
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    structured_intake = {
        "project_name": "Adaptive Coach Intelligence",
        "one_sentence_summary": (
            "Independent fitness coaches need a faster way to turn client check-ins into "
            "specific coaching actions."
        ),
        "target_users": ["Independent online fitness coaches", "Hybrid personal trainers"],
        "buyer_type": "prosumer",
        "problem_hypotheses": [
            "Coaches spend too much time reviewing check-ins manually.",
            "Clients expect faster and more personalized coaching responses.",
        ],
        "proposed_solution": (
            "A workspace that synthesizes check-ins, wearable data, and workout logs into "
            "recommended coaching actions."
        ),
        "market_category": "Fitness coaching software",
        "business_model_guess": "Monthly subscription",
        "suspected_competitors": ["Trainerize", "TrueCoach"],
        "key_uncertainties": [
            "Whether coaches trust AI-generated recommendations.",
            "Whether solo coaches will pay for another tool.",
        ],
        "clarifying_questions": ["Which coaching segment has budget?"],
    }

    response = client.post(
        f"/api/projects/{project_id}/intake/finalize",
        json={
            "structured_intake": structured_intake,
            "raw_idea": "AI for fitness coach check-ins.",
            "answers": [
                {
                    "question": "Which coaching segment has budget?",
                    "answer": "Independent online coaches.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["name"] == "Adaptive Coach Intelligence"
    assert body["project"]["current_thesis"]["version"] == 1
    assert len(body["customer_segments"]) == 2
    assert body["customer_segments"][0]["priority"] == "primary"
    assert len(body["problems"]) == 2
    assert body["intake_record"]["market_category"] == "Fitness coaching software"

    intake_record = db_session.scalar(select(ProjectIntake))
    assert intake_record is not None
    assert intake_record.project_name == "Adaptive Coach Intelligence"
    assert intake_record.user_answers[0]["answer"] == "Independent online coaches."

    thesis = db_session.scalar(
        select(ProjectThesis).where(ProjectThesis.project_id == uuid.UUID(project_id))
    )
    assert thesis is not None
    assert thesis.thesis_text == structured_intake["one_sentence_summary"]

    assert db_session.scalar(select(CustomerSegment)) is not None
    assert db_session.scalar(select(Problem)) is not None

    get_response = client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 200
    project = get_response.json()
    assert len(project["customer_segments"]) == 2
    assert len(project["problems"]) == 2


def test_structured_intake_endpoints_are_workspace_scoped(client: TestClient) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}

    create_response = client.post(
        "/api/projects",
        headers=user_a_headers,
        json={"name": "Private idea"},
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/intake/analyze",
        headers=user_b_headers,
        json={"raw_idea": "Analyze this private idea."},
    )

    assert response.status_code == 404
