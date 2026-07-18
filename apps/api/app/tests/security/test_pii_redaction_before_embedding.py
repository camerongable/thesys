from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvidenceChunk, EvidenceSource
from app.services import embedding_service
from app.services.data_protection_service import data_protection_service


def test_data_protection_detects_and_sanitizes_restricted_content() -> None:
    text = (
        "Contact Jane Doe at jane.doe@example.com or +1 (415) 555-0123. "
        "Card 4111 1111 1111 1111, api_key=sk-supersecretvalue123, "
        "and https://reader:password@example.com/report are restricted."
    )

    protected = data_protection_service.create_searchable_copy(text)

    assert protected.data_classification.value == "restricted"
    assert protected.pii_status == "redacted"
    assert set(protected.pii_entity_types) >= {
        "API_KEY",
        "CREDIT_CARD",
        "EMAIL",
        "PHONE_NUMBER",
        "URL_CREDENTIAL",
    }
    for raw_value in (
        "Jane Doe",
        "jane.doe@example.com",
        "415) 555-0123",
        "4111 1111 1111 1111",
        "sk-supersecretvalue123",
        "reader:password",
    ):
        assert raw_value not in protected.text
    assert "<EMAIL_001>" in protected.text
    assert "[REDACTED_SECRET]" in protected.text


def test_presidio_detects_and_anonymizes_extended_identifier_types() -> None:
    text = "The applicant SSN is 219-09-9999 and IBAN is GB82 WEST 1234 5698 7654 32."

    protected = data_protection_service.create_searchable_copy(text)

    assert protected.data_classification.value == "restricted"
    assert {"US_SSN", "IBAN_CODE"} <= set(protected.pii_entity_types)
    assert "219-09-9999" not in protected.text
    assert "GB82 WEST 1234 5698 7654 32" not in protected.text
    assert protected.text.count("[REDACTED_SECRET]") == 2


def test_note_pii_is_sanitized_before_persistence_and_embedding(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    embedded_texts: list[str] = []
    original_embed = embedding_service.embed_text_with_metadata_cached

    def capture_embedding(*args, **kwargs):
        embedded_texts.append(args[3])
        return original_embed(*args, **kwargs)

    monkeypatch.setattr(embedding_service, "embed_text_with_metadata_cached", capture_embedding)
    project_response = client.post(
        "/api/projects",
        json={"name": "Sensitive evidence", "short_description": "Secure ingestion coverage."},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    raw_text = (
        "Jane Doe can be reached at jane.doe@example.com. "
        "Use api_key=sk-supersecretvalue123 for the internal report."
    )

    response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Jane Doe notes", "text": raw_text},
    )

    assert response.status_code == 201
    source = db_session.scalar(select(EvidenceSource))
    chunk = db_session.scalar(select(EvidenceChunk))
    assert source is not None and chunk is not None
    for raw_value in ("Jane Doe", "jane.doe@example.com", "sk-supersecretvalue123"):
        assert raw_value not in (source.raw_text or "")
        assert raw_value not in chunk.text
        assert all(raw_value not in embedded_text for embedded_text in embedded_texts)
    security_metadata = source.source_metadata["security"]
    assert security_metadata == {
        "data_classification": "restricted",
        "pii_status": "redacted",
        "pii_entity_types": ["API_KEY", "EMAIL", "PERSON"],
        "security_status": "approved",
        "classification_status": "approved",
        "malware_status": "not_scanned",
        "sanitization_version": "v1",
        "retention_expires_at": security_metadata["retention_expires_at"],
    }
    assert security_metadata["retention_expires_at"]
    assert chunk.chunk_metadata["security"]["retrieval_allowed"] is True


def test_unapproved_source_or_chunk_is_excluded_from_retrieval_and_reembedding(
    client: TestClient,
    db_session: Session,
) -> None:
    project_response = client.post(
        "/api/projects",
        json={"name": "Security eligibility", "short_description": "Retrieval gate coverage."},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    note_response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Approved note", "text": "A specific secure retrieval proof point."},
    )
    assert note_response.status_code == 201
    source = db_session.scalar(select(EvidenceSource))
    chunk = db_session.scalar(select(EvidenceChunk))
    assert source is not None and chunk is not None
    chunk.embedding_model = "old-model"
    source.source_metadata = {
        **source.source_metadata,
        "security": {**source.source_metadata["security"], "security_status": "blocked"},
    }
    db_session.commit()

    retrieval_response = client.post(
        f"/api/projects/{project_id}/evidence/retrieve",
        json={"query": "specific secure proof", "mode": "keyword"},
    )
    assert retrieval_response.status_code == 200
    assert retrieval_response.json()["results"] == []
    reembed_response = client.post(
        f"/api/projects/{project_id}/evidence/reembed",
        json={"dry_run": True, "scope": "project"},
    )
    assert reembed_response.status_code == 200
    assert reembed_response.json()["eligible_count"] == 0

    source.source_metadata = {
        **source.source_metadata,
        "security": {**source.source_metadata["security"], "security_status": "approved"},
    }
    chunk.chunk_metadata = {
        **chunk.chunk_metadata,
        "security": {**chunk.chunk_metadata["security"], "retrieval_allowed": False},
    }
    db_session.commit()

    retrieval_response = client.post(
        f"/api/projects/{project_id}/evidence/retrieve",
        json={"query": "specific secure proof", "mode": "keyword"},
    )
    assert retrieval_response.status_code == 200
    assert retrieval_response.json()["results"] == []
    reembed_response = client.post(
        f"/api/projects/{project_id}/evidence/reembed",
        json={"dry_run": True, "scope": "project"},
    )
    assert reembed_response.status_code == 200
    assert reembed_response.json()["eligible_count"] == 0
