from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIRun, AIStep, EvidenceChunk, EvidenceSource
from app.services import embedding_service, evidence_service, multimodal_extraction_service
from app.services.data_protection_service import data_protection_service


def test_data_protection_detects_and_sanitizes_restricted_content() -> None:
    text = (
        "Contact Jane Doe at jane.doe@example.com or +1 (415) 555-0123. "
        "Card 4111 1111 1111 1111, api_key=sk-supersecretvalue123, "
        "access_token=access-token-secret123, "
        "and https://reader:password@example.com/report are restricted."
    )

    protected = data_protection_service.create_searchable_copy(text)

    assert protected.data_classification.value == "restricted"
    assert protected.pii_status == "redacted"
    assert set(protected.pii_entity_types) >= {
        "ACCESS_TOKEN",
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
        "access-token-secret123",
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


def test_generated_summary_is_sanitized_before_persistence_and_workflow_recording(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    generated_summary = (
        "Generated summary: Jane Doe can be reached at jane.doe@example.com "
        "with api_key=sk-summarysecret123."
    )
    monkeypatch.setattr(evidence_service, "_summarize", lambda _text: generated_summary)
    project_id = _create_project(client, "Summary output protection")

    response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Safe source", "text": "A generic research finding."},
    )

    assert response.status_code == 201
    source = db_session.scalar(select(EvidenceSource))
    run = db_session.scalar(select(AIRun))
    step = db_session.scalar(select(AIStep))
    assert source is not None and run is not None and step is not None
    for raw_value in ("Jane Doe", "jane.doe@example.com", "sk-summarysecret123"):
        assert raw_value not in (source.summary or "")
        assert raw_value not in str(step.output_json)
        assert raw_value not in (run.output_summary or "")
    assert "[REDACTED_SECRET]" in (source.summary or "")


def test_url_title_is_sanitized_before_pre_fetch_source_persistence(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    raw_title = "Jane Doe contact jane.doe@example.com"

    def fake_fetch(_settings: object, _url: str) -> evidence_service.ParsedSource:
        source = db_session.scalar(select(EvidenceSource))
        assert source is not None
        assert "Jane Doe" not in (source.title or "")
        assert "jane.doe@example.com" not in (source.title or "")
        return evidence_service.ParsedSource(
            title=None,
            text="A generic fetched research finding.",
            content_type="text/plain",
            metadata={},
        )

    monkeypatch.setattr(evidence_service, "_fetch_url", fake_fetch)
    project_id = _create_project(client, "URL title protection")

    response = client.post(
        f"/api/projects/{project_id}/evidence/url",
        json={"url": "https://example.com/research", "title": raw_title},
    )

    assert response.status_code == 201
    source = db_session.scalar(select(EvidenceSource))
    assert source is not None
    assert "Jane Doe" not in (source.title or "")
    assert "jane.doe@example.com" not in (source.title or "")


def test_image_caption_and_provider_metadata_are_sanitized_before_storage_and_embedding(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    embedded_texts: list[str] = []
    original_embed = embedding_service.embed_text_with_metadata_cached

    def capture_embedding(*args, **kwargs):
        embedded_texts.append(args[3])
        return original_embed(*args, **kwargs)

    def fake_extraction(
        _settings: object,
        *,
        filename: str,
        content_type: str,
        body: bytes,
        media_type: str,
    ) -> multimodal_extraction_service.MultimodalExtraction:
        del body
        return multimodal_extraction_service.MultimodalExtraction(
            text=(
                "Image caption: Jane Doe at jane.doe@example.com shared "
                "access_token=caption-secret-123."
            ),
            title="Jane Doe interview image",
            provider="deterministic",
            model="caption-test",
            media_type=media_type,
            content_type=content_type,
            warnings=["Caption references Jane Doe at jane.doe@example.com."],
            metadata={"caption_author": "Jane Doe", "contact": "jane.doe@example.com"},
        )

    monkeypatch.setattr(embedding_service, "embed_text_with_metadata_cached", capture_embedding)
    monkeypatch.setattr(multimodal_extraction_service, "extract_file", fake_extraction)
    project_id = _create_project(client, "Caption output protection")

    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("interview.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 201
    source = db_session.scalar(select(EvidenceSource))
    chunk = db_session.scalar(select(EvidenceChunk))
    assert source is not None and chunk is not None
    for raw_value in ("Jane Doe", "jane.doe@example.com", "caption-secret-123"):
        assert raw_value not in (source.title or "")
        assert raw_value not in (source.raw_text or "")
        assert raw_value not in chunk.text
        assert raw_value not in str(source.source_metadata)
        assert all(raw_value not in text for text in embedded_texts)
    assert "[REDACTED_SECRET]" in (source.raw_text or "")


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("interview-notes.md", "text/markdown"),
        ("application.log", "text/plain"),
    ],
)
def test_uploaded_markdown_and_logs_are_sanitized_before_embedding(
    client: TestClient,
    db_session: Session,
    monkeypatch,
    filename: str,
    content_type: str,
) -> None:
    embedded_texts: list[str] = []
    original_embed = embedding_service.embed_text_with_metadata_cached

    def capture_embedding(*args, **kwargs):
        embedded_texts.append(args[3])
        return original_embed(*args, **kwargs)

    monkeypatch.setattr(embedding_service, "embed_text_with_metadata_cached", capture_embedding)
    project_id = _create_project(client, f"Protected {filename}")
    raw_text = "Contact Jane Doe at jane.doe@example.com with api_key=sk-logsecret123."

    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": (filename, raw_text.encode(), content_type)},
    )

    assert response.status_code == 201
    source = db_session.scalar(select(EvidenceSource))
    chunk = db_session.scalar(select(EvidenceChunk))
    assert source is not None and chunk is not None
    for raw_value in ("Jane Doe", "jane.doe@example.com", "sk-logsecret123"):
        assert raw_value not in (source.raw_text or "")
        assert raw_value not in chunk.text
        assert all(raw_value not in text for text in embedded_texts)
    assert "[REDACTED_SECRET]" in (source.raw_text or "")


def _create_project(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/projects",
        json={"name": name, "short_description": "PII output protection coverage."},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _png_bytes() -> bytes:
    image = Image.new("RGB", (8, 8), color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
