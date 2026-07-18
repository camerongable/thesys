import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import get_settings
from app.db.models import AuditEvent, EvidenceSource, PiiTokenMapping, User, Workspace
from app.services import pseudonymization_service


def test_pseudonymization_is_encrypted_project_local_and_owner_authorized(
    client: TestClient,
    db_session: Session,
) -> None:
    email = "jane.doe@example.com"
    first_project_id = _create_project(client, "Private mapping one")
    first_source = _add_note(client, first_project_id, email)
    first_mapping = db_session.scalar(select(PiiTokenMapping))
    assert first_mapping is not None
    assert first_mapping.token == "<EMAIL_001>"
    assert email not in first_mapping.encrypted_value_ciphertext
    assert email not in first_mapping.encrypted_value_nonce
    assert email not in (first_source["text_preview"] or "")
    assert "<EMAIL_001>" in (first_source["text_preview"] or "")

    owner = _auth_context(db_session, first_source, "owner")
    assert pseudonymization_service.reidentify_token(
        db_session,
        owner,
        get_settings(),
        project_id=uuid.UUID(first_project_id),
        token=first_mapping.token,
    ) == email
    audit = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "pii_reidentification_authorized")
    )
    assert audit is not None
    assert email not in str(audit.event_metadata)

    viewer = _auth_context(db_session, first_source, "viewer")
    with pytest.raises(HTTPException) as exc_info:
        pseudonymization_service.reidentify_token(
            db_session,
            viewer,
            get_settings(),
            project_id=uuid.UUID(first_project_id),
            token=first_mapping.token,
        )
    assert exc_info.value.status_code == 403

    second_project_id = _create_project(client, "Private mapping two")
    _add_note(client, second_project_id, email)
    mappings = list(
        db_session.scalars(select(PiiTokenMapping).order_by(PiiTokenMapping.created_at))
    )
    assert len(mappings) == 2
    assert {mapping.project_id for mapping in mappings} == {
        uuid.UUID(first_project_id),
        uuid.UUID(second_project_id),
    }
    assert all(mapping.token == "<EMAIL_001>" for mapping in mappings)
    assert mappings[0].encrypted_value_ciphertext != mappings[1].encrypted_value_ciphertext


def _create_project(client: TestClient, name: str) -> str:
    response = client.post("/api/projects", json={"name": name, "short_description": "PII scope."})
    assert response.status_code == 201
    return response.json()["id"]


def _add_note(client: TestClient, project_id: str, email: str) -> dict[str, object]:
    response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Customer contact", "text": f"Reach the customer at {email}."},
    )
    assert response.status_code == 201
    return response.json()


def _auth_context(db: Session, source: dict[str, object], role: str) -> AuthContext:
    source_id = uuid.UUID(str(source["id"]))
    stored_source = db.scalar(select(EvidenceSource).where(EvidenceSource.id == source_id))
    assert stored_source is not None and stored_source.created_by is not None
    user = db.scalar(select(User).where(User.id == stored_source.created_by))
    workspace = db.scalar(select(Workspace).where(Workspace.id == stored_source.workspace_id))
    assert user is not None and workspace is not None
    return AuthContext.from_identity(
        user=user,
        workspace=workspace,
        role=role,
        authentication_method="dev",
    )
