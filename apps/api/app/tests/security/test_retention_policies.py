import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings, get_settings
from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    ArtifactVersion,
    AuditEvent,
    AuthenticationEvent,
    EvidenceChunk,
    EvidenceSource,
    EvidenceSourceTombstone,
    PiiTokenMapping,
    SessionRevocation,
    User,
    Workspace,
)
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
    tombstone = db_session.scalar(
        select(EvidenceSourceTombstone).where(EvidenceSourceTombstone.source_id == source_id)
    )
    assert tombstone is not None
    assert tombstone.deletion_reason == "retention_expired"


def test_local_retention_cleanup_removes_expired_payloads_but_keeps_run_accounting(
    client: TestClient,
    db_session: Session,
) -> None:
    project = client.post("/api/projects", json={"name": "Local retention cleanup"}).json()
    source_response = client.post(
        f"/api/projects/{project['id']}/evidence/note",
        json={"title": "Retention owner", "text": "A scoped owner record."},
    )
    source = db_session.scalar(
        select(EvidenceSource).where(EvidenceSource.id == uuid.UUID(source_response.json()["id"]))
    )
    assert source is not None
    owner = _owner_auth_context(db_session, source)
    expired_at = datetime.now(UTC) - timedelta(days=800)

    expired_run = AIRun(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        workflow_type="retention_test",
        status="succeeded",
        input_summary="expired prompt",
        output_summary="expired output",
        total_tokens=123,
        total_cost=4,
        langsmith_trace_id="expired-trace",
        langsmith_trace_url="https://trace.example/expired",
        error="expired error",
        created_by=source.created_by,
        created_at=expired_at,
    )
    current_run = AIRun(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        workflow_type="retention_test",
        status="succeeded",
        input_summary="current prompt",
        output_summary="current output",
        total_tokens=456,
        langsmith_trace_id="current-trace",
        created_by=source.created_by,
    )
    db_session.add_all((expired_run, current_run))
    db_session.flush()
    expired_step = AIStep(
        ai_run_id=expired_run.id,
        step_name="expired_step",
        status="succeeded",
        input_json={"prompt": "expired"},
        output_json={"answer": "expired"},
        tokens=21,
        langsmith_trace_id="expired-trace",
        langsmith_run_id="expired-run",
        langsmith_trace_url="https://trace.example/expired-step",
        error="expired step error",
        created_at=expired_at,
    )
    artifact = Artifact(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        artifact_type="other",
        title="Expired trace artifact",
        created_by=source.created_by,
    )
    db_session.add_all((expired_step, artifact))
    db_session.flush()
    expired_version = ArtifactVersion(
        workspace_id=source.workspace_id,
        artifact_id=artifact.id,
        version=1,
        markdown_content="Expired artifact contents remain durable.",
        structured_content={},
        langsmith_trace_id="expired-artifact-trace",
        langsmith_trace_url="https://trace.example/expired-artifact",
        created_by=source.created_by,
        created_at=expired_at,
    )
    expired_audit = AuditEvent(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        user_id=source.created_by,
        event_type="retention_test",
        actor_type="system",
        summary="Expired audit record",
        risk_level="low",
        event_metadata={},
        created_at=expired_at,
    )
    expired_security = AuthenticationEvent(
        workspace_id=source.workspace_id,
        user_id=source.created_by,
        event_type="login_success",
        authentication_method="dev",
        reason_code="retention_test",
        created_at=expired_at,
    )
    session_revocation = SessionRevocation(
        workspace_id=source.workspace_id,
        user_id=source.created_by,
        session_identifier_hash="0" * 64,
        revoked_at=expired_at,
    )
    db_session.add_all((expired_version, expired_audit, expired_security, session_revocation))
    db_session.commit()
    expired_audit_id = expired_audit.id
    expired_security_id = expired_security.id
    session_revocation_id = session_revocation.id

    result = retention_service.purge_expired_local_records(
        db_session,
        owner,
        get_settings(),
    )
    assert result.as_dict() == {
        "model_prompts_redacted": 2,
        "model_outputs_redacted": 2,
        "trace_references_cleared": 3,
        "audit_events_deleted": 1,
        "security_events_deleted": 1,
    }

    db_session.expire_all()
    expired_run = db_session.get(AIRun, expired_run.id)
    expired_step = db_session.get(AIStep, expired_step.id)
    expired_version = db_session.get(ArtifactVersion, expired_version.id)
    current_run = db_session.get(AIRun, current_run.id)
    assert expired_run is not None and expired_step is not None and expired_version is not None
    assert current_run is not None
    assert expired_run.input_summary is None
    assert expired_run.output_summary is None
    assert expired_run.error is None
    assert expired_run.langsmith_trace_id is None
    assert expired_run.total_tokens == 123
    assert expired_step.input_json is None
    assert expired_step.output_json is None
    assert expired_step.error is None
    assert expired_step.tokens == 21
    assert expired_version.langsmith_trace_id is None
    assert current_run.input_summary == "current prompt"
    assert current_run.output_summary == "current output"
    assert current_run.langsmith_trace_id == "current-trace"
    assert db_session.get(AuditEvent, expired_audit_id) is None
    assert db_session.get(AuthenticationEvent, expired_security_id) is None
    assert db_session.get(SessionRevocation, session_revocation_id) is not None


def test_worker_only_cleanup_purges_expired_unscoped_authentication_events(
    db_session: Session,
) -> None:
    expired_event = AuthenticationEvent(
        event_type="token_validation_failure",
        authentication_method="oidc",
        reason_code="token_rejected",
        created_at=datetime.now(UTC) - timedelta(days=800),
    )
    current_event = AuthenticationEvent(
        event_type="login_failure",
        authentication_method="oidc",
        reason_code="credentials_missing",
    )
    db_session.add_all((expired_event, current_event))
    db_session.commit()
    expired_event_id = expired_event.id
    current_event_id = current_event.id

    with pytest.raises(RuntimeError, match="worker role"):
        retention_service.purge_expired_unscoped_authentication_events(
            db_session,
            Settings(database_runtime_role="api"),
        )

    assert (
        retention_service.purge_expired_unscoped_authentication_events(
            db_session,
            Settings(database_runtime_role="worker"),
        )
        == 1
    )
    assert db_session.get(AuthenticationEvent, expired_event_id) is None
    assert db_session.get(AuthenticationEvent, current_event_id) is not None


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
