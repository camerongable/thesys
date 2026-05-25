import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIRun, AIStep, ResearchPlan, ResearchSprint


def test_research_sprint_plan_generation_waits_for_human_approval(
    client: TestClient,
    db_session: Session,
) -> None:
    project_response = client.post(
        "/api/projects",
        json={
            "name": "Fitness coach OS",
            "short_description": "AI workspace for independent fitness coaches.",
            "initial_thesis": "Coaches need faster check-in synthesis before client calls.",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={
            "objective": (
                "Investigate the market, competitors, and validation risks for online "
                "fitness coaches."
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is True
    assert body["prompt_version"].endswith("research-sprint-planning:v1")
    assert body["sprint"]["status"] == "planned"
    assert body["sprint"]["plan"]["status"] == "draft"
    assert body["sprint"]["plan"]["research_questions"]
    assert body["sprint"]["plan"]["competitor_queries"]
    assert body["sprint"]["plan"]["expected_outputs"]

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.workflow_type == "research_sprint_planning"
    assert run.status == "waiting_for_human"
    assert run.project_id == uuid.UUID(project_id)

    step = db_session.scalar(select(AIStep).where(AIStep.id == uuid.UUID(body["ai_step_id"])))
    assert step is not None
    assert step.step_name == "generate_research_plan"
    assert step.status == "succeeded"

    assert db_session.scalar(select(ResearchPlan)) is not None
    assert db_session.scalar(select(ResearchSprint)) is not None


def test_research_sprint_plan_can_be_edited_and_approved(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Plant care idea"}).json()["id"]
    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={},
    )
    sprint = plan_response.json()["sprint"]

    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint['id']}/approve",
        json={
            "objective": "Validate the beginner houseplant owner wedge first.",
            "research_questions": [
                "Which plant care pain is frequent enough to pay for?",
                "Which substitutes already solve reminders or diagnosis?",
            ],
        },
    )

    assert approve_response.status_code == 200
    approved = approve_response.json()["sprint"]
    assert approved["status"] == "approved"
    assert approved["plan"]["status"] == "approved"
    assert approved["plan"]["objective"] == "Validate the beginner houseplant owner wedge first."
    assert approved["plan"]["approved_at"] is not None

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(approved["ai_run_id"])))
    assert run is not None
    assert run.status == "succeeded"
    steps = list(db_session.scalars(select(AIStep).where(AIStep.ai_run_id == run.id)))
    assert [step.step_name for step in steps] == [
        "generate_research_plan",
        "approve_research_plan",
    ]

    list_response = client.get(f"/api/projects/{project_id}/research-sprints")
    assert list_response.status_code == 200
    assert list_response.json()["sprints"][0]["status"] == "approved"


def test_research_sprint_plan_can_be_rejected(client: TestClient, db_session: Session) -> None:
    project_id = client.post("/api/projects", json={"name": "Developer tool idea"}).json()["id"]
    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={"objective": "Plan research for a developer tool."},
    )
    sprint = plan_response.json()["sprint"]

    reject_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint['id']}/reject"
    )

    assert reject_response.status_code == 200
    rejected = reject_response.json()["sprint"]
    assert rejected["status"] == "rejected"
    assert rejected["plan"]["status"] == "rejected"
    assert rejected["plan"]["rejected_at"] is not None

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(rejected["ai_run_id"])))
    assert run is not None
    assert run.status == "cancelled"


def test_research_sprints_are_workspace_scoped(client: TestClient) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}

    create_response = client.post(
        "/api/projects",
        headers=user_a_headers,
        json={"name": "Private research idea"},
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        headers=user_b_headers,
        json={"objective": "Try to plan against another workspace."},
    )

    assert response.status_code == 404
