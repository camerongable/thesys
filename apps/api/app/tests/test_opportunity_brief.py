import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.structured_output import StructuredOutputError
from app.core.config import get_settings
from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    ArtifactVersion,
    Assumption,
    Claim,
    ClaimEvidenceLink,
    Risk,
)


def test_generate_opportunity_brief_retrieves_cites_and_persists(
    client: TestClient,
    db_session: Session,
) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Fitness coach OS",
            "short_description": "AI for independent fitness coach check-ins.",
            "initial_thesis": (
                "Independent fitness coaches need faster synthesis of check-ins and "
                "wearable data."
            ),
        },
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    note_response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={
            "title": "Coach interview notes",
            "text": (
                "Independent fitness coaches spend hours reviewing weekly client check-ins. "
                "Wearable data and workout logs are scattered across tools. "
                "Coaches want faster recommendations but need to trust the rationale."
            ),
        },
    )
    assert note_response.status_code == 201

    response = client.post(
        f"/api/projects/{project_id}/artifacts/opportunity-brief/generate"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is True
    assert body["retrieval_result_count"] >= 1
    assert body["artifact"]["artifact_type"] == "opportunity_brief"
    assert body["version"]["version"] == 1
    assert "## Evidence Appendix" in body["version"]["markdown_content"]
    assert body["claims"]
    assert body["assumptions"]
    assert body["risks"]
    assert body["unsupported_claims"]

    supported_claim = next(
        claim for claim in body["claims"] if claim["support_level"] == "supported"
    )
    assert supported_claim["evidence_links"]
    assert supported_claim["evidence_links"][0]["evidence_source_id"] == note_response.json()["id"]
    assert supported_claim["evidence_links"][0]["evidence_chunk_id"] is not None

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.workflow_type == "opportunity_brief"
    assert run.status == "succeeded"

    steps = list(
        db_session.scalars(
            select(AIStep).where(AIStep.ai_run_id == run.id).order_by(AIStep.created_at)
        )
    )
    assert [step.step_name for step in steps] == [
        "load_project_state",
        "retrieve_existing_evidence",
        "generate_structured_brief",
        "citation_audit",
        "write_artifact_version",
    ]
    retrieve_step = next(step for step in steps if step.step_name == "retrieve_existing_evidence")
    retrieve_output = retrieve_step.output_json
    assert retrieve_output["diagnostics"]["query_plan"]["subqueries"]
    assert retrieve_output["diagnostics"]["reranker"]["provider"] == "deterministic"
    assert retrieve_output["diagnostics"]["context"]["selected_count"] >= 1
    assert retrieve_output["diagnostics"]["quality_report"]["citation_coverage_proxy"] == 1
    assert retrieve_output["results"][0]["context_included"] is True
    assert retrieve_output["results"][0]["chunk_id"] == (
        supported_claim["evidence_links"][0]["evidence_chunk_id"]
    )

    artifact = db_session.scalar(select(Artifact))
    assert artifact is not None
    assert artifact.current_version_id == uuid.UUID(body["version"]["id"])
    assert db_session.scalar(select(ArtifactVersion)) is not None
    assert db_session.scalar(select(Claim)) is not None
    assert db_session.scalar(select(ClaimEvidenceLink)) is not None
    assert db_session.scalar(select(Assumption)) is not None
    assert db_session.scalar(select(Risk)) is not None


def test_generate_opportunity_brief_versions_existing_artifact(client: TestClient) -> None:
    create_response = client.post("/api/projects", json={"name": "Versioned brief"})
    project_id = create_response.json()["id"]
    client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={
            "title": "Validation note",
            "text": "Founders need project memory, citations, and decision history.",
        },
    )

    first = client.post(f"/api/projects/{project_id}/artifacts/opportunity-brief/generate")
    second = client.post(f"/api/projects/{project_id}/artifacts/opportunity-brief/generate")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["artifact"]["id"] == second.json()["artifact"]["id"]
    assert first.json()["version"]["version"] == 1
    assert second.json()["version"]["version"] == 2
    assert second.json()["artifact"]["current_version_id"] == second.json()["version"]["id"]

    list_response = client.get(
        f"/api/projects/{project_id}/artifacts?artifact_type=opportunity_brief"
    )
    assert list_response.status_code == 200
    artifact = list_response.json()["artifacts"][0]
    assert len(artifact["versions"]) == 2
    assert artifact["current_version"]["version"] == 2


def test_generate_opportunity_brief_can_force_local_fallback_with_always_policy(
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
        "app.services.opportunity_brief_service.generate_structured_output",
        fail_if_called,
    )
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Local brief fallback",
            "short_description": "Source-backed plant care guidance.",
        },
    )
    project_id = create_response.json()["id"]
    client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={
            "title": "Plant care note",
            "text": "New plant owners want clearer weekly care routines.",
        },
    )

    response = client.post(f"/api/projects/{project_id}/artifacts/opportunity-brief/generate")

    assert response.status_code == 200
    body = response.json()
    assert body["model_provider"] == "local-fallback"
    assert body["used_stub"] is True
    assert body["artifact"]["artifact_type"] == "opportunity_brief"
    assert body["claims"]


def test_generate_opportunity_brief_uses_emergency_fallback_after_generation_failure(
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
        "app.services.opportunity_brief_service.generate_structured_output",
        fail_generation,
    )
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Emergency brief fallback",
            "short_description": "Source-backed plant care guidance.",
        },
    )
    project_id = create_response.json()["id"]
    client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={
            "title": "Plant care note",
            "text": "New plant owners want clearer weekly care routines.",
        },
    )

    response = client.post(f"/api/projects/{project_id}/artifacts/opportunity-brief/generate")

    assert response.status_code == 200
    body = response.json()
    assert body["model_provider"] == "local-fallback"
    assert body["used_stub"] is True
    assert body["claims"]


def test_opportunity_brief_generation_failure_marks_step_failed(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Slow brief",
            "short_description": "A brief that times out during local generation.",
        },
    )
    project_id = create_response.json()["id"]
    client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Validation note", "text": "Founders need cited opportunity briefs."},
    )

    def fail_generation(*args, **kwargs):
        raise StructuredOutputError("forced generation failure")

    monkeypatch.setattr(
        "app.services.opportunity_brief_service.generate_structured_output",
        fail_generation,
    )

    response = client.post(f"/api/projects/{project_id}/artifacts/opportunity-brief/generate")

    assert response.status_code == 502
    run = db_session.scalar(select(AIRun).where(AIRun.workflow_type == "opportunity_brief"))
    assert run is not None
    assert run.status == "failed"
    assert run.error == "forced generation failure"

    generation_step = db_session.scalar(
        select(AIStep).where(
            AIStep.ai_run_id == run.id,
            AIStep.step_name == "generate_structured_brief",
        )
    )
    assert generation_step is not None
    assert generation_step.status == "failed"
    assert generation_step.error == "forced generation failure"
    assert generation_step.latency_ms is not None


def test_opportunity_brief_generation_is_workspace_scoped(client: TestClient) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}

    create_response = client.post(
        "/api/projects",
        headers=user_a_headers,
        json={"name": "Private brief project"},
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/artifacts/opportunity-brief/generate",
        headers=user_b_headers,
    )

    assert response.status_code == 404
