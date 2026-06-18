import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIRun, AIStep, EvidenceChunk, EvidenceSource
from app.services import evidence_service


def test_note_ingestion_chunks_embeds_and_retrieves(
    client: TestClient,
    db_session: Session,
) -> None:
    create_response = client.post(
        "/api/projects",
        json={"name": "Fitness coach OS", "short_description": "AI for coach check-ins."},
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
    source = note_response.json()
    assert source["ingestion_status"] == "ready"
    assert source["classification"] == "customer_discovery"
    assert source["chunk_count"] == 1
    assert source["summary"]

    chunk = db_session.scalar(select(EvidenceChunk))
    assert chunk is not None
    assert chunk.source_id == uuid.UUID(source["id"])
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 1536

    retrieval_response = client.post(
        f"/api/projects/{project_id}/evidence/retrieve",
        json={
            "query": "fitness coaches weekly check-ins wearable data recommendations",
            "mode": "hybrid",
            "top_k": 5,
        },
    )

    assert retrieval_response.status_code == 200
    retrieval = retrieval_response.json()
    assert retrieval["mode"] == "hybrid"
    assert retrieval["diagnostics"]["embedding_provider"] == "deterministic"
    assert retrieval["diagnostics"]["embedding_model"] == "deterministic-hash-embedding-1536"
    assert retrieval["diagnostics"]["fallback_path_used"] is True
    assert retrieval["diagnostics"]["fallback_reason"] == "database dialect is not postgres"
    assert retrieval["results"]
    assert retrieval["results"][0]["source_id"] == source["id"]
    assert retrieval["results"][0]["chunk_id"] == str(chunk.id)
    assert retrieval["results"][0]["keyword_score"] > 0
    assert retrieval["results"][0]["embedding_provider"] == "deterministic"
    assert retrieval["results"][0]["embedding_model"] == "deterministic-hash-embedding-1536"
    assert retrieval["results"][0]["embedding_dimension"] == 1536
    assert retrieval["results"][0]["embedding_version"] == "v1"

    retrieval_run = db_session.scalar(
        select(AIRun).where(AIRun.id == uuid.UUID(retrieval["ai_run_id"]))
    )
    assert retrieval_run is not None
    assert retrieval_run.workflow_type == "evidence_retrieval"
    assert retrieval_run.status == "succeeded"

    retrieval_step = db_session.scalar(
        select(AIStep).where(AIStep.id == uuid.UUID(retrieval["ai_step_id"]))
    )
    assert retrieval_step is not None
    assert retrieval_step.step_name == "hybrid_retrieval"
    assert retrieval_step.output_json["result_count"] == 1
    assert retrieval_step.output_json["diagnostics"]["fallback_path_used"] is True


def test_url_ingestion_uses_fetcher_and_source_type_filter(
    client: TestClient,
    monkeypatch,
) -> None:
    create_response = client.post("/api/projects", json={"name": "Competitor research"})
    project_id = create_response.json()["id"]

    def fake_fetch_url(settings, url: str) -> evidence_service.ParsedSource:
        return evidence_service.ParsedSource(
            title="Trainerize Pricing",
            text=(
                "Trainerize offers fitness coaching software with habit tracking, "
                "messaging, payments, and coach-facing pricing tiers."
            ),
            content_type="text/html",
        )

    monkeypatch.setattr(evidence_service, "_fetch_url", fake_fetch_url)

    response = client.post(
        f"/api/projects/{project_id}/evidence/url",
        json={"url": "https://example.com/pricing"},
    )

    assert response.status_code == 201
    source = response.json()
    assert source["source_type"] == "url"
    assert source["title"] == "Trainerize Pricing"
    assert source["classification"] == "competitor_research"

    retrieval_response = client.post(
        f"/api/projects/{project_id}/evidence/retrieve",
        json={
            "query": "coach pricing messaging payments",
            "mode": "keyword",
            "source_types": ["url"],
        },
    )

    assert retrieval_response.status_code == 200
    assert retrieval_response.json()["results"][0]["source_type"] == "url"


def test_file_upload_stores_object_and_parses_markdown(
    client: TestClient,
    db_session: Session,
) -> None:
    create_response = client.post("/api/projects", json={"name": "File evidence"})
    project_id = create_response.json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={
            "file": (
                "interview-notes.md",
                b"# Interview\n\nA coach said client check-ins are the weekly bottleneck.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "file"
    assert body["object_storage_key"]
    assert body["chunk_count"] == 1

    source = db_session.scalar(
        select(EvidenceSource).where(EvidenceSource.id == uuid.UUID(body["id"]))
    )
    assert source is not None
    assert source.object_storage_key == body["object_storage_key"]


def test_reembed_evidence_dry_run_and_project_update(
    client: TestClient,
    db_session: Session,
) -> None:
    create_response = client.post("/api/projects", json={"name": "Reembed project"})
    project_id = create_response.json()["id"]
    note_response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Source", "text": "A narrow wedge needs proof from customer notes."},
    )
    assert note_response.status_code == 201
    chunk = db_session.scalar(select(EvidenceChunk))
    assert chunk is not None
    chunk.embedding_model = "old-model"
    db_session.commit()

    dry_run_response = client.post(
        f"/api/projects/{project_id}/evidence/reembed",
        json={"dry_run": True, "scope": "project"},
    )
    assert dry_run_response.status_code == 200
    dry_run = dry_run_response.json()
    assert dry_run["dry_run"] is True
    assert dry_run["scanned_count"] == 1
    assert dry_run["eligible_count"] == 1
    assert dry_run["reembedded_count"] == 0

    db_session.refresh(chunk)
    assert chunk.embedding_model == "old-model"

    update_response = client.post(
        f"/api/projects/{project_id}/evidence/reembed",
        json={"dry_run": False, "scope": "project"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["dry_run"] is False
    assert updated["eligible_count"] == 1
    assert updated["reembedded_count"] == 1
    assert updated["failed_count"] == 0

    db_session.refresh(chunk)
    assert chunk.embedding_model == "deterministic-hash-embedding-1536"
    assert chunk.embedding_provider == "deterministic"
    assert chunk.embedding_dimension == 1536
    assert chunk.embedding_version == "v1"
    assert chunk.embedded_at is not None


def test_evidence_endpoints_are_workspace_scoped(client: TestClient) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}

    create_response = client.post(
        "/api/projects",
        headers=user_a_headers,
        json={"name": "Private evidence project"},
    )
    project_id = create_response.json()["id"]
    note_response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        headers=user_a_headers,
        json={"title": "Private source", "text": "Private founder research."},
    )
    source_id = note_response.json()["id"]

    user_b_list = client.get(f"/api/projects/{project_id}/evidence", headers=user_b_headers)
    assert user_b_list.status_code == 404

    user_b_get = client.get(
        f"/api/projects/{project_id}/evidence/{source_id}",
        headers=user_b_headers,
    )
    assert user_b_get.status_code == 404
