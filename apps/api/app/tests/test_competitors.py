import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    Claim,
    ClaimEvidenceLink,
    Competitor,
    CompetitorEvidenceLink,
    EvidenceChunk,
    EvidenceSource,
)
from app.services import evidence_service


def test_create_and_analyze_competitors_persists_profiles_artifact_and_links(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Fitness coach OS",
            "short_description": "AI for independent fitness coach check-ins.",
            "initial_thesis": "Help coaches synthesize check-ins and training data.",
        },
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    def fake_fetch_url(settings, url: str) -> evidence_service.ParsedSource:
        return evidence_service.ParsedSource(
            title="Trainerize Features and Pricing",
            text=(
                "Trainerize sells fitness coaching software for online coaches. "
                "It includes client messaging, habit tracking, workout programming, "
                "payments, and pricing tiers for solo fitness businesses."
            ),
            content_type="text/html",
        )

    monkeypatch.setattr(evidence_service, "_fetch_url", fake_fetch_url)

    competitor_response = client.post(
        f"/api/projects/{project_id}/competitors",
        json={"name": "Trainerize", "url": "https://example.com/trainerize"},
    )
    assert competitor_response.status_code == 201
    competitor_id = competitor_response.json()["id"]

    response = client.post(f"/api/projects/{project_id}/competitors/analyze", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is True
    assert body["retrieval_result_count"] >= 1
    assert body["ingested_source_count"] == 1
    assert body["artifact"]["artifact_type"] == "competitor_landscape"
    assert body["artifact"]["current_version"]["version"] == 1
    assert "## Positioning Gaps" in body["artifact"]["current_version"]["markdown_content"]
    assert body["claims"]
    assert body["unsupported_claims"]

    analyzed = next(item for item in body["competitors"] if item["id"] == competitor_id)
    assert analyzed["category"] == "direct"
    assert analyzed["threat_level"] == "high"
    assert analyzed["key_features"]
    assert analyzed["evidence_links"]

    source = db_session.scalar(select(EvidenceSource))
    assert source is not None
    assert source.classification == "competitor_research"

    chunk = db_session.scalar(select(EvidenceChunk))
    assert chunk is not None
    assert chunk.chunk_metadata["competitor_id"] == competitor_id

    competitor = db_session.scalar(
        select(Competitor).where(Competitor.id == uuid.UUID(competitor_id))
    )
    assert competitor is not None
    assert competitor.last_analyzed_at is not None

    run = db_session.scalar(select(AIRun).where(AIRun.id == uuid.UUID(body["ai_run_id"])))
    assert run is not None
    assert run.workflow_type == "competitor_analysis"
    assert run.status == "succeeded"

    steps = list(
        db_session.scalars(
            select(AIStep).where(AIStep.ai_run_id == run.id).order_by(AIStep.created_at)
        )
    )
    assert [step.step_name for step in steps] == [
        "load_project_state",
        "load_user_seeded_competitors",
        "fetch_competitor_sources",
        "retrieve_competitor_evidence",
        "extract_competitor_profiles",
        "citation_audit",
        "write_competitor_landscape",
    ]

    artifact = db_session.scalar(
        select(Artifact).where(Artifact.artifact_type == "competitor_landscape")
    )
    assert artifact is not None
    assert db_session.scalar(select(CompetitorEvidenceLink)) is not None
    assert db_session.scalar(select(Claim)) is not None
    assert db_session.scalar(select(ClaimEvidenceLink)) is not None


def test_competitor_analysis_can_create_seeded_competitors(client: TestClient) -> None:
    create_response = client.post("/api/projects", json={"name": "Seeded competitors"})
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/competitors/analyze",
        json={
            "ingest_urls": False,
            "seed_competitors": [
                {
                    "name": "ChatGPT",
                    "url": "https://example.com/chatgpt",
                    "category": "substitute",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["competitors"][0]["name"] == "ChatGPT"
    assert body["competitors"][0]["category"] == "substitute"
    assert body["artifact"]["current_version"]["version"] == 1

    list_response = client.get(f"/api/projects/{project_id}/competitors")
    assert list_response.status_code == 200
    assert list_response.json()["competitors"][0]["name"] == "ChatGPT"


def test_create_competitor_accepts_bare_domain(client: TestClient) -> None:
    create_response = client.post("/api/projects", json={"name": "Bare URL competitor"})
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/competitors",
        json={"name": "Plant.id", "url": "plant.id", "category": "direct"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["url"] == "https://plant.id"


def test_competitor_endpoints_are_workspace_scoped(client: TestClient) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}

    create_response = client.post(
        "/api/projects",
        headers=user_a_headers,
        json={"name": "Private competitor project"},
    )
    project_id = create_response.json()["id"]
    competitor_response = client.post(
        f"/api/projects/{project_id}/competitors",
        headers=user_a_headers,
        json={"name": "Private competitor"},
    )
    competitor_id = competitor_response.json()["id"]

    user_b_list = client.get(f"/api/projects/{project_id}/competitors", headers=user_b_headers)
    assert user_b_list.status_code == 404

    user_b_get = client.get(
        f"/api/projects/{project_id}/competitors/{competitor_id}",
        headers=user_b_headers,
    )
    assert user_b_get.status_code == 404

    user_b_analyze = client.post(
        f"/api/projects/{project_id}/competitors/analyze",
        headers=user_b_headers,
        json={},
    )
    assert user_b_analyze.status_code == 404
