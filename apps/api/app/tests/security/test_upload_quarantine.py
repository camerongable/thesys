import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditEvent, EvidenceChunk, EvidenceSource
from app.services import secure_ingestion_state_service


def test_unavailable_scanner_quarantines_upload_before_storage_or_parsing(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MALWARE_SCANNER_MODE", "disabled")
    get_settings.cache_clear()
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("notes.txt", b"Private customer notes", "text/plain")},
    )

    assert response.status_code == 422
    source = db_session.scalar(select(EvidenceSource))
    assert source is not None
    assert source.ingestion_status == "quarantined"
    assert source.object_storage_key is None
    assert source.raw_text is None
    assert db_session.scalar(select(EvidenceChunk)) is None
    assert source.source_metadata["security"]["malware_status"] == "scan_failed"
    assert _ingestion_states(source) == ["uploaded", "malware_scanning", "quarantined"]
    audit = db_session.scalar(select(AuditEvent).order_by(AuditEvent.created_at.desc()))
    assert audit is not None
    assert audit.event_type == "evidence_upload_quarantined"
    assert audit.event_metadata["malware_status"] == "scan_failed"
    get_settings.cache_clear()


def test_infected_upload_is_quarantined_before_storage_or_parsing(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={
            "file": (
                "eicar.txt",
                b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
                "text/plain",
            )
        },
    )

    assert response.status_code == 422
    source = db_session.scalar(select(EvidenceSource))
    assert source is not None
    assert source.ingestion_status == "quarantined"
    assert source.object_storage_key is None
    assert db_session.scalar(select(EvidenceChunk)) is None
    assert source.source_metadata["security"]["malware_status"] == "infected"
    assert _ingestion_states(source) == ["uploaded", "malware_scanning", "quarantined"]


def test_secure_ingestion_state_rejects_post_quarantine_processing() -> None:
    source = type("Source", (), {"source_metadata": {}})()
    secure_ingestion_state_service.transition(
        source,
        secure_ingestion_state_service.SecureIngestionState.MALWARE_SCANNING,
    )
    secure_ingestion_state_service.transition(
        source,
        secure_ingestion_state_service.SecureIngestionState.QUARANTINED,
    )

    with pytest.raises(ValueError, match="Invalid secure-ingestion transition"):
        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.EXTRACTION_PENDING,
        )


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "Upload quarantine", "short_description": "Scanner boundary coverage."},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _ingestion_states(source: EvidenceSource) -> list[str]:
    ingestion = source.source_metadata["ingestion"]
    return [entry["state"] for entry in ingestion["history"]]
