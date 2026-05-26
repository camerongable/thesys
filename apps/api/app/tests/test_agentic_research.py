import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    Assumption,
    AssumptionEvidenceLink,
    Claim,
    ClaimEvidenceLink,
    ResearchSprint,
    Risk,
)
from app.services.evidence_service import ParsedSource


def _approved_research_sprint_with_evidence(
    client: TestClient,
    monkeypatch,
) -> tuple[str, str]:
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
    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={
            "objective": (
                "Investigate competitors, substitutes, customer pain, and validation "
                "risks for online fitness coaches."
            )
        },
    )
    assert plan_response.status_code == 200
    sprint_id = plan_response.json()["sprint"]["id"]
    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/approve",
        json={},
    )
    assert approve_response.status_code == 200

    monkeypatch.setattr(
        "app.services.evidence_service._fetch_url",
        lambda settings, url: ParsedSource(
            title="Fetched research source",
            text=(
                "Independent fitness coaches spend hours reviewing client check-ins, "
                "workout logs, wearable data, pricing pages, and competitor reviews. "
                "Many coaches pay for coaching software but still use manual notes and "
                "spreadsheets for synthesis before client calls."
            ),
            content_type="text/html",
        ),
    )
    sources_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover"
    )
    assert sources_response.status_code == 200
    source_id = sources_response.json()["sources"][0]["id"]
    source_approval = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/approve"
    )
    assert source_approval.status_code == 200
    competitors_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/discover"
    )
    assert competitors_response.status_code == 200
    candidate_id = competitors_response.json()["candidates"][0]["id"]
    candidate_approval = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/approve"
    )
    assert candidate_approval.status_code == 200
    return project_id, sprint_id


def test_agentic_research_runs_multi_step_rag_and_writes_reviewable_memo(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    project_id, sprint_id = _approved_research_sprint_with_evidence(client, monkeypatch)

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is True
    assert body["prompt_version"].endswith("agentic-research:v1")
    assert body["retrieval_tool_call_count"] >= 2
    assert body["additional_retrieval_passes"] == 1
    assert body["evidence_gap_count"] >= 1
    assert body["artifact"]["artifact_type"] == "research_memo"
    assert body["version"]["structured_content"]["research_sprint_id"] == sprint_id
    assert "## Market Landscape" in body["version"]["markdown_content"]
    assert "## Riskiest Assumptions" in body["version"]["markdown_content"]
    assert body["version"]["structured_content"]["memo"]["riskiest_assumptions"]
    assert body["version"]["structured_content"]["memory_update_preview"]["assumptions"]
    assert body["version"]["structured_content"]["memory_update_status"] == (
        "pending_human_approval"
    )
    assert body["claims"]
    assert body["citations"]

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.workflow_type == "agentic_research"
    assert run.status == "waiting_for_human"

    step_names = [
        step.step_name
        for step in db_session.scalars(
            select(AIStep).where(AIStep.ai_run_id == run.id).order_by(AIStep.created_at)
        )
    ]
    assert step_names == [
        "load_research_context",
        "research_planner",
        "retrieval_strategy_selector",
        "tool_executor",
        "evidence_selector",
        "gap_detector",
        "follow_up_retriever",
        "synthesizer",
        "critic",
        "final_memo_writer",
        "human_approval_interrupt",
    ]

    sprint = db_session.scalar(
        select(ResearchSprint).where(ResearchSprint.id == uuid.UUID(sprint_id))
    )
    assert sprint is not None
    assert sprint.status == "needs_review"

    artifact = db_session.scalar(
        select(Artifact).where(Artifact.id == uuid.UUID(body["artifact"]["id"]))
    )
    assert artifact is not None
    assert artifact.current_version_id == uuid.UUID(body["version"]["id"])
    assert db_session.scalar(
        select(Claim).where(Claim.artifact_version_id == artifact.current_version_id)
    )
    assert db_session.scalar(select(ClaimEvidenceLink)) is not None


def test_agentic_research_memo_can_be_approved_after_review(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    project_id, sprint_id = _approved_research_sprint_with_evidence(client, monkeypatch)
    run_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run"
    )
    assert run_response.status_code == 200
    run_body = run_response.json()

    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/approve"
    )

    assert approve_response.status_code == 200
    body = approve_response.json()
    assert body["sprint"]["status"] == "completed"
    assert body["sprint"]["completed_at"] is not None
    assert body["sprint"]["plan"]["status"] == "completed"
    assert body["version"]["id"] == run_body["version"]["id"]
    assert body["version"]["structured_content"]["memory_update_status"] == "approved"
    assert body["version"]["structured_content"]["memory_updates_written"] is True
    assert body["version"]["structured_content"]["memory_update_approved_by"] is not None
    assert body["version"]["structured_content"]["memory_update_summary"]["assumption_ids"]
    assert body["version"]["structured_content"]["memory_update_summary"]["risk_ids"]
    assert db_session.scalar(select(Assumption)) is not None
    assert db_session.scalar(select(Risk)) is not None
    assert db_session.scalar(select(AssumptionEvidenceLink)) is not None

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.status == "succeeded"
    assert run.completed_at is not None

    step_names = [
        step.step_name
        for step in db_session.scalars(
            select(AIStep).where(AIStep.ai_run_id == run.id).order_by(AIStep.created_at)
        )
    ]
    assert step_names[-1] == "approve_research_memo"


def test_agentic_research_requires_approved_plan(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Unapproved research"}).json()["id"]
    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={},
    )
    sprint_id = plan_response.json()["sprint"]["id"]

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run"
    )

    assert response.status_code == 409
