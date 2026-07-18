import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import get_settings
from app.db.models import EvidenceChunk, EvidenceSource, PiiTokenMapping, User, Workspace
from app.services import retention_service


def test_retention_registry_covers_every_required_asset() -> None:
    configured = retention_service.policies(get_settings())

    assert set(configured) == set(retention_service.RetentionAsset)
    assert (
        configured[retention_service.RetentionAsset.RAW_SOURCE_OBJECT].days
        < configured[retention_service.RetentionAsset.AUDIT_EVENT].days
    )
    assert (
        configured[retention_service.RetentionAsset.PII_TOKEN_MAP].days
        < configured[retention_service.RetentionAsset.SECURITY_EVENT].days
    )
    assert configured[retention_service.RetentionAsset.LANGSMITH_TRACE].enforcement_boundary == (
        "langsmith_provider"
    )


def test_expired_evidence_and_pii_mappings_are_purged_by_workspace(
    client: TestClient,
    db_session: Session,
) -> None:
    project = client.post("/api/projects", json={"name": "Retention policy"}).json()
    project_id = project["id"]
    created = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Expiring evidence", "text": "Weekly check-ins create repeated pain."},
    )
    assert created.status_code == 201
    source = db_session.scalar(
        select(EvidenceSource).where(EvidenceSource.id == uuid.UUID(created.json()["id"]))
    )
    assert source is not None
    security = source.source_metadata["security"]
    assert security["retention_expires_at"]
    assert source.source_metadata["retention"]["raw_source_object_expires_at"]
    chunk = db_session.scalar(select(EvidenceChunk).where(EvidenceChunk.source_id == source.id))
    assert chunk is not None and chunk.chunk_metadata["security"]["retention_expires_at"]

    owner = _owner_auth_context(db_session, source)
    source.source_metadata = {
        **source.source_metadata,
        "security": {
            **security,
            "retention_expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        },
    }
    mapping = PiiTokenMapping(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        token="<EMAIL_099>",
        entity_type="EMAIL",
        encrypted_value_ciphertext="ciphertext",
        encrypted_value_nonce="nonce",
        encrypted_value_key_version="v1",
        algorithm="AES-256-GCM",
        retention_expires_at=datetime.now(UTC) - timedelta(days=1),
        created_by=source.created_by,
    )
    db_session.add(mapping)
    db_session.commit()
    mapping_id = mapping.id
    source_id = source.id

    settings = get_settings()
    assert retention_service.purge_expired_pii_token_mappings(db_session, owner) == 1
    assert (
        retention_service.purge_expired_evidence_sources(db_session, owner, settings) == 1
    )

    assert (
        db_session.scalar(select(PiiTokenMapping).where(PiiTokenMapping.id == mapping_id))
        is None
    )
    assert db_session.scalar(select(EvidenceSource).where(EvidenceSource.id == source_id)) is None
    assert (
        db_session.scalar(select(EvidenceChunk).where(EvidenceChunk.source_id == source_id)) is None
    )


def _owner_auth_context(db: Session, source: EvidenceSource) -> AuthContext:
    user = db.scalar(select(User).where(User.id == source.created_by))
    workspace = db.scalar(select(Workspace).where(Workspace.id == source.workspace_id))
    assert user is not None and workspace is not None
    return AuthContext.from_identity(
        user=user,
        workspace=workspace,
        role="owner",
        authentication_method="dev",
    )
