from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuditEvent, EvidenceChunk, EvidenceSource
from app.services import evidence_service


def _build_pdf(
    *,
    page_count: int = 1,
    encrypted: bool = False,
    active_content: bool = False,
) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("secret-password")
    if active_content:
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
            {
                NameObject("/S"): NameObject("/JavaScript"),
                NameObject("/JS"): TextStringObject("app.alert('unsafe')"),
            }
        )
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (_build_pdf(encrypted=True), "Password-protected PDFs"),
        (_build_pdf(active_content=True), "PDF active content"),
    ],
    ids=["encrypted", "active-content"],
)
def test_unsafe_pdf_is_rejected_before_storage_or_extraction(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    reason: str,
) -> None:
    project_id = _create_project(client)

    def storage_must_not_run(**_kwargs: object) -> str:
        raise AssertionError("Unsafe PDFs must not reach object storage.")

    monkeypatch.setattr(
        evidence_service.object_storage_service,
        "put_evidence_object",
        storage_must_not_run,
    )
    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("unsafe.pdf", body, "application/pdf")},
    )

    assert response.status_code == 422
    assert db_session.scalar(select(EvidenceSource)) is None
    assert db_session.scalar(select(EvidenceChunk)) is None
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "evidence_upload_rejected")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert reason in audit.event_metadata["reason"]


def test_pdf_page_limit_is_enforced_before_storage(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_PDF_PAGES", "1")
    get_settings.cache_clear()
    project_id = _create_project(client)

    def storage_must_not_run(**_kwargs: object) -> str:
        raise AssertionError("Over-limit PDFs must not reach object storage.")

    monkeypatch.setattr(
        evidence_service.object_storage_service,
        "put_evidence_object",
        storage_must_not_run,
    )

    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("two-pages.pdf", _build_pdf(page_count=2), "application/pdf")},
    )

    assert response.status_code == 422
    assert db_session.scalar(select(EvidenceSource)) is None
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "evidence_upload_rejected")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert "PDF exceeds 1 page limit" in audit.event_metadata["reason"]
    get_settings.cache_clear()


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "PDF security", "short_description": "PDF preflight coverage."},
    )
    assert response.status_code == 201
    return response.json()["id"]
