import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.litellm_client import LLMCompletion
from app.ai.structured_output import StructuredOutputResult
from app.core.config import get_settings
from app.db.models import (
    AIRun,
    Competitor,
    CompetitorCandidate,
    DiscoveredSource,
    EvidenceSource,
)
from app.schemas.research import (
    CompetitorDiscoveryCandidateDraft,
    CompetitorDiscoveryDraft,
    SourceDiscoveryCandidateDraft,
    SourceDiscoveryDraft,
)


def _approved_research_sprint(client: TestClient) -> tuple[str, str]:
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
                "Investigate competitors, substitutes, and market evidence for online "
                "fitness coaches."
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
    return project_id, sprint_id


def test_source_discovery_generates_dedupes_and_ingests_approved_candidates(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id, sprint_id = _approved_research_sprint(client)

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["generated_count"] >= 3
    assert body["candidate_count"] >= 3
    assert body["sources"][0]["status"] == "candidate"
    assert body["sources"][0]["reason_selected"]

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.workflow_type == "source_discovery"
    assert run.status == "succeeded"

    duplicate_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover"
    )
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["candidate_count"] == body["candidate_count"]

    source_id = body["sources"][0]["id"]
    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/approve"
    )

    assert approve_response.status_code == 200
    approved = approve_response.json()["source"]
    assert approved["status"] == "ingested"
    assert approved["evidence_source_id"] is not None

    evidence = db_session.scalar(
        select(EvidenceSource).where(EvidenceSource.id == uuid.UUID(approved["evidence_source_id"]))
    )
    assert evidence is not None
    assert evidence.ingestion_status == "ready"
    assert evidence.url == approved["url"]

    rejected_source_id = body["sources"][1]["id"]
    reject_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/{rejected_source_id}/reject"
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["source"]["status"] == "rejected"

    assert db_session.scalar(select(DiscoveredSource)) is not None


def test_source_discovery_requires_an_approved_research_plan(client: TestClient) -> None:
    project_response = client.post("/api/projects", json={"name": "Unapproved idea"})
    project_id = project_response.json()["id"]
    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={},
    )
    sprint_id = plan_response.json()["sprint"]["id"]

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover"
    )

    assert response.status_code == 409


def test_source_discovery_uses_structured_output_in_live_mode(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    project_id, sprint_id = _approved_research_sprint(client)
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("LITELLM_MODEL", "test-live-model")
    get_settings.cache_clear()
    calls: list[object] = []

    def fake_generate(settings, output_schema, messages, **kwargs):
        calls.append(output_schema)
        draft = SourceDiscoveryDraft(
            sources=[
                SourceDiscoveryCandidateDraft(
                    url="https://example.com/plant-market-report",
                    title="Plant market report",
                    snippet="A source candidate selected by the live model path.",
                    source_type="market_report",
                    relevance_score=Decimal("0.91"),
                    reason_selected="Tests whether source discovery calls structured output.",
                    associated_research_question="Which market evidence should be reviewed?",
                )
            ]
        )
        return StructuredOutputResult(
            parsed=draft,
            completion=LLMCompletion(
                content=draft.model_dump_json(),
                model_provider="litellm",
                model_name="test-live-model",
                prompt_tokens=11,
                completion_tokens=17,
                total_tokens=28,
                total_cost=Decimal("0.001"),
                raw_response={"test": True},
                used_stub=False,
            ),
        )

    monkeypatch.setattr(
        "app.services.source_discovery_service.generate_structured_output",
        fake_generate,
    )

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover"
    )

    assert response.status_code == 200
    assert calls == [SourceDiscoveryDraft]
    body = response.json()
    assert body["sources"][0]["url"] == "https://example.com/plant-market-report"
    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.model_provider == "litellm"
    assert run.model_name == "test-live-model"
    assert run.total_tokens == 28


def test_competitor_discovery_classifies_candidates_and_merges_approved_competitors(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id, sprint_id = _approved_research_sprint(client)
    source_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover"
    )
    source_id = source_response.json()["sources"][0]["id"]
    client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/approve"
    )

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/discover"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] >= 3
    categories = {candidate["category"] for candidate in body["candidates"]}
    assert "direct_competitor" in categories
    assert "substitute_behavior" in categories
    assert all(candidate["why_it_matters"] for candidate in body["candidates"])

    first_candidate = body["candidates"][0]
    patch_response = client.patch(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{first_candidate['id']}",
        json={"name": "Edited competitor", "threat_level": "low"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Edited competitor"
    assert patch_response.json()["threat_level"] == "low"

    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{first_candidate['id']}/approve"
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()["candidate"]
    assert approved["status"] == "merged"
    assert approved["competitor_id"] is not None

    competitor = db_session.scalar(
        select(Competitor).where(Competitor.id == uuid.UUID(approved["competitor_id"]))
    )
    assert competitor is not None
    assert competitor.name == "Edited competitor"
    assert competitor.threat_level == "low"

    reject_target = next(
        candidate for candidate in body["candidates"] if candidate["id"] != first_candidate["id"]
    )
    reject_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{reject_target['id']}/reject"
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["candidate"]["status"] == "rejected"

    assert db_session.scalar(select(CompetitorCandidate)) is not None


def test_competitor_discovery_uses_structured_output_in_live_mode(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    project_id, sprint_id = _approved_research_sprint(client)
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("LITELLM_MODEL", "test-live-model")
    get_settings.cache_clear()
    calls: list[object] = []

    def fake_generate(settings, output_schema, messages, **kwargs):
        calls.append(output_schema)
        draft = CompetitorDiscoveryDraft(
            candidates=[
                CompetitorDiscoveryCandidateDraft(
                    name="Live Model Competitor",
                    url="https://example.com/competitor",
                    category="direct_competitor",
                    target_user="Plant-care beginners",
                    positioning="A model-generated competitor candidate.",
                    pricing_signal="Pricing requires verification.",
                    core_features=["guidance", "reminders"],
                    why_it_matters="Tests whether competitor discovery calls structured output.",
                    threat_level="medium",
                    relevance_score=Decimal("0.89"),
                    source_ids=[],
                )
            ]
        )
        return StructuredOutputResult(
            parsed=draft,
            completion=LLMCompletion(
                content=draft.model_dump_json(),
                model_provider="litellm",
                model_name="test-live-model",
                prompt_tokens=13,
                completion_tokens=19,
                total_tokens=32,
                total_cost=Decimal("0.001"),
                raw_response={"test": True},
                used_stub=False,
            ),
        )

    monkeypatch.setattr(
        "app.services.competitor_discovery_service.generate_structured_output",
        fake_generate,
    )

    response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/discover"
    )

    assert response.status_code == 200
    assert calls == [CompetitorDiscoveryDraft]
    body = response.json()
    assert body["candidates"][0]["name"] == "Live Model Competitor"
    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.model_provider == "litellm"
    assert run.model_name == "test-live-model"
    assert run.total_tokens == 32
