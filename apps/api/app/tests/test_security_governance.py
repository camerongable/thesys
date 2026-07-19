import base64
import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security as security_module
from app.core.config import Settings, get_settings
from app.core.security import (
    SecurityValidationError,
    validate_upload,
    validate_url_fetch_target,
    validate_url_response_content_type,
)
from app.db.models import AIRun, ApprovalRequest, AuditEvent, EvidenceSource, ToolInvocation
from app.schemas.security import KillSwitchUpdate
from app.services import (
    kill_switch_service,
    security_policy_service,
    tool_service,
    workflow_budget_service,
)
from app.services.identity_service import ensure_dev_identity


def test_url_ingestion_blocks_local_network_targets_and_audits_denial(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/evidence/url",
        json={"url": "http://127.0.0.1:8080/admin"},
    )

    assert response.status_code == 502
    source = db_session.scalar(
        select(EvidenceSource).where(EvidenceSource.url.contains("127.0.0.1"))
    )
    assert source is not None
    assert source.ingestion_status == "failed"
    assert "blocked network address" in (source.ingestion_error or "")
    assert [entry["state"] for entry in source.source_metadata["ingestion"]["history"]] == [
        "uploaded",
        "failed",
    ]
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "evidence_url_fetch_blocked")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.risk_level == "medium"
    assert audit.event_metadata["reason"].startswith("URL host resolves")


def test_security_helper_blocks_private_fetch_targets() -> None:
    with pytest.raises(SecurityValidationError, match="blocked network address"):
        validate_url_fetch_target("https://10.0.0.4/internal")

    with pytest.raises(SecurityValidationError, match="embedded credentials"):
        validate_url_fetch_target("https://user:pass@example.com")


def test_url_fetch_policy_blocks_denied_domains_ports_and_content_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("URL_FETCH_DENIED_DOMAINS", "example.com")
    monkeypatch.setenv("URL_FETCH_ALLOWED_PORTS", "80,443")
    monkeypatch.setenv("URL_FETCH_ALLOWED_CONTENT_TYPES", "text/html,text/plain")
    get_settings.cache_clear()
    settings = get_settings()

    with pytest.raises(SecurityValidationError, match="denied by policy"):
        validate_url_fetch_target("https://example.com/research", settings)
    with pytest.raises(SecurityValidationError, match="port is not allowed"):
        validate_url_fetch_target("https://example.org:444/research", settings)
    with pytest.raises(SecurityValidationError, match="content type is not allowed"):
        validate_url_response_content_type("application/octet-stream", settings)

    get_settings.cache_clear()


def test_file_upload_rejects_unsafe_filename_and_type(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("../secret.txt", b"private notes", "text/plain")},
    )

    assert response.status_code == 422
    assert db_session.scalar(select(EvidenceSource)) is None
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "evidence_upload_rejected")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert "path separators" in audit.event_metadata["reason"]

    with pytest.raises(SecurityValidationError, match="supported"):
        validate_upload(
            filename="archive.zip",
            content_type="application/zip",
            body=b"PK\x03\x04",
            settings=get_settings(),
        )


def test_file_upload_requires_content_detection_to_match_extension(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        security_module,
        "_detect_upload_content_type",
        lambda _body: "application/pdf",
    )

    response = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("notes.txt", b"harmless-looking text", "text/plain")},
    )

    assert response.status_code == 422
    assert db_session.scalar(select(EvidenceSource)) is None
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "evidence_upload_rejected")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert "Detected MIME type application/pdf" in audit.event_metadata["reason"]


def test_upload_validation_denies_when_mime_detector_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(security_module, "magic", None)
    monkeypatch.setattr(security_module.shutil, "which", lambda _command: None)

    with pytest.raises(SecurityValidationError, match="MIME detection is unavailable"):
        validate_upload(
            filename="notes.txt",
            content_type="text/plain",
            body=b"ordinary evidence notes",
            settings=get_settings(),
        )


def test_upload_validation_returns_detected_content_type() -> None:
    result = validate_upload(
        filename="notes.txt",
        content_type="text/plain",
        body=b"ordinary evidence notes",
        settings=get_settings(),
    )

    assert result.content_type == "text/plain"
    assert result.detected_content_type == "text/plain"


def test_extracted_text_limit_fails_closed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_EXTRACTED_TEXT_CHARS", "1000")
    get_settings.cache_clear()
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Oversized note", "text": "A" * 1001},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Note evidence ingestion failed."
    get_settings.cache_clear()


def test_role_permissions_block_viewer_research_and_admin_delete(
    client: TestClient,
) -> None:
    project_id = _create_project(client)

    viewer_plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        headers={"X-Dev-User-Role": "viewer"},
        json={"objective": "Investigate the market."},
    )
    assert viewer_plan_response.status_code == 403

    admin_delete_response = client.delete(
        f"/api/projects/{project_id}",
        headers={"X-Dev-User-Role": "admin"},
    )
    assert admin_delete_response.status_code == 403

    owner_delete_response = client.delete(
        f"/api/projects/{project_id}",
        headers={"X-Dev-User-Role": "owner"},
    )
    assert owner_delete_response.status_code == 204


def test_jwt_auth_accepts_signed_token_and_rejects_dev_headers(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_JWT_ISSUER", "https://issuer.example")
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "thesys-api")
    monkeypatch.setenv("AUTH_JWT_ALLOWED_KEY_IDS", "active-key")
    get_settings.cache_clear()
    token = _sign_jwt(
        "test-secret",
        {
            "sub": "interview-user",
            "email": "interview@example.com",
            "name": "Interview User",
            "role": "owner",
            "workspace_name": "Interview Workspace",
            "iss": "https://issuer.example",
            "aud": "thesys-api",
            "exp": int(time.time()) + 3600,
        },
        header={"kid": "active-key"},
    )

    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    dev_header_response = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}", "X-Dev-User-Role": "owner"},
    )
    assert dev_header_response.status_code == 403
    get_settings.cache_clear()


def test_jwt_auth_rejects_inactive_key_and_revoked_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_JWT_ALLOWED_KEY_IDS", "active-key")
    monkeypatch.setenv("AUTH_JWT_REVOKED_IDS", "revoked-token")
    get_settings.cache_clear()
    base_claims = {
        "sub": "interview-user",
        "email": "interview@example.com",
        "role": "owner",
        "exp": int(time.time()) + 3600,
    }

    inactive_key_token = _sign_jwt(
        "test-secret",
        base_claims,
        header={"kid": "old-key"},
    )
    inactive_response = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {inactive_key_token}"},
    )
    assert inactive_response.status_code == 401

    revoked_token = _sign_jwt(
        "test-secret",
        {**base_claims, "jti": "revoked-token"},
        header={"kid": "active-key"},
    )
    revoked_response = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {revoked_token}"},
    )
    assert revoked_response.status_code == 401
    get_settings.cache_clear()


def test_api_key_auth_accepts_hashed_service_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = "local-service-key"
    monkeypatch.setenv("AUTH_MODE", "api_key")
    monkeypatch.setenv("AUTH_API_KEY_HASHES", hashlib.sha256(api_key.encode()).hexdigest())
    get_settings.cache_clear()

    response = client.get("/api/projects", headers={"X-API-Key": api_key})

    assert response.status_code == 200
    get_settings.cache_clear()


def test_api_key_auth_rejects_revoked_hash(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = "local-service-key"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    monkeypatch.setenv("AUTH_MODE", "api_key")
    monkeypatch.setenv("AUTH_API_KEY_HASHES", key_hash)
    monkeypatch.setenv("AUTH_REVOKED_API_KEY_HASHES", key_hash)
    get_settings.cache_clear()

    response = client.get("/api/projects", headers={"X-API-Key": api_key})

    assert response.status_code == 401
    get_settings.cache_clear()


def test_expensive_workflow_rate_limit_denies_and_audits(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECURITY_RATE_LIMIT_USER_MAX_REQUESTS", "1")
    monkeypatch.setenv("SECURITY_RATE_LIMIT_WORKSPACE_MAX_REQUESTS", "10")
    monkeypatch.setenv("SECURITY_RATE_LIMIT_WINDOW_SECONDS", "600")
    get_settings.cache_clear()
    project_id = _create_project(client)

    first = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Signal", "text": "Founder interview notes show a repeated workflow."},
    )
    assert first.status_code == 201

    denied = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Signal 2", "text": "More notes."},
    )

    assert denied.status_code == 429
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["workflow_type"] == "evidence_note_ingestion"
    get_settings.cache_clear()


def test_authenticated_api_rate_limit_denies_before_route_work(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_project(client)
    monkeypatch.setenv("SECURITY_API_RATE_LIMIT_USER_MAX_REQUESTS", "1")
    monkeypatch.setenv("SECURITY_API_RATE_LIMIT_WORKSPACE_MAX_REQUESTS", "10")
    monkeypatch.setenv("SECURITY_API_RATE_LIMIT_IP_MAX_REQUESTS", "10")
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    first = client.get("/api/projects")
    denied = client.get("/api/projects")

    assert first.status_code == 200
    assert denied.status_code == 429
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["workflow_type"] == "authenticated_api_request"
    get_settings.cache_clear()


def test_authenticated_api_rate_limit_uses_hashed_redis_buckets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.counts: dict[str, int] = {}

        def eval(self, _script: str, _keys: int, key: str, _window_seconds: int) -> int:
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]

    fake_redis = FakeRedis()
    monkeypatch.setenv("SECURITY_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("SECURITY_API_RATE_LIMIT_USER_MAX_REQUESTS", "1")
    monkeypatch.setenv("SECURITY_API_RATE_LIMIT_WORKSPACE_MAX_REQUESTS", "10")
    monkeypatch.setenv("SECURITY_API_RATE_LIMIT_IP_MAX_REQUESTS", "10")
    monkeypatch.setattr(security_policy_service, "_redis_client", lambda _settings: fake_redis)
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    first = client.get("/api/projects")
    denied = client.get("/api/projects")

    assert first.status_code == 200
    assert denied.status_code == 429
    assert len(fake_redis.counts) == 3
    assert all(key.startswith("thesys:security-rate:v1:api_") for key in fake_redis.counts)
    assert all("authenticated_api_request" not in key for key in fake_redis.counts)
    get_settings.cache_clear()


def test_authenticated_api_rate_limit_fails_closed_when_redis_is_unavailable(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_settings: Settings) -> object:
        raise security_policy_service.RedisError("offline")

    monkeypatch.setenv("SECURITY_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(security_policy_service, "_redis_client", unavailable)
    get_settings.cache_clear()

    response = client.get("/api/projects")

    assert response.status_code == 503
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["workflow_type"] == "authenticated_api_request"
    assert audit.event_metadata["status_code"] == 503
    get_settings.cache_clear()


def test_file_upload_rate_limits_user_requests_and_workspace_bytes(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("SECURITY_UPLOAD_RATE_LIMIT_USER_MAX_REQUESTS", "1")
    monkeypatch.setenv("SECURITY_UPLOAD_RATE_LIMIT_WORKSPACE_MAX_BYTES", "100")
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    first = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    denied = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("note-2.txt", b"hello", "text/plain")},
    )

    assert first.status_code == 201
    assert denied.status_code == 429
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["detail"] == "Per-user upload rate limit exceeded."
    get_settings.cache_clear()


def test_file_upload_rate_limits_workspace_bytes(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("SECURITY_UPLOAD_RATE_LIMIT_USER_MAX_REQUESTS", "10")
    monkeypatch.setenv("SECURITY_UPLOAD_RATE_LIMIT_WORKSPACE_MAX_BYTES", "5")
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    first = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    denied = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("note-2.txt", b"hello", "text/plain")},
    )

    assert first.status_code == 201
    assert denied.status_code == 429
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["detail"] == "Per-workspace uploaded-byte rate limit exceeded."
    get_settings.cache_clear()


def test_file_upload_rate_limit_uses_hashed_redis_byte_bucket(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.counts: dict[str, int] = {}

        def eval(self, _script: str, _keys: int, key: str, *args: int) -> int:
            amount = args[0] if len(args) == 2 else 1
            self.counts[key] = self.counts.get(key, 0) + amount
            return self.counts[key]

    project_id = _create_project(client)
    fake_redis = FakeRedis()
    monkeypatch.setenv("SECURITY_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("SECURITY_UPLOAD_RATE_LIMIT_USER_MAX_REQUESTS", "10")
    monkeypatch.setenv("SECURITY_UPLOAD_RATE_LIMIT_WORKSPACE_MAX_BYTES", "5")
    monkeypatch.setattr(security_policy_service, "_redis_client", lambda _settings: fake_redis)
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    first = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    denied = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("note-2.txt", b"hello", "text/plain")},
    )

    assert first.status_code == 201
    assert denied.status_code == 429
    assert any(":upload_bytes_workspace:" in key for key in fake_redis.counts)
    assert all("evidence_file_upload" not in key for key in fake_redis.counts)
    get_settings.cache_clear()


def test_signed_url_rate_limit_denies_before_object_authorization(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _create_project(client)
    source = client.post(
        f"/api/projects/{project_id}/evidence/file",
        files={"file": ("note.txt", b"downloadable evidence", "text/plain")},
    ).json()
    monkeypatch.setenv("SECURITY_SIGNED_URL_RATE_LIMIT_USER_MAX_REQUESTS", "1")
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    first = client.get(f"/api/projects/{project_id}/evidence/{source['id']}/download")
    denied = client.get(f"/api/projects/{project_id}/evidence/{source['id']}/download")

    assert first.status_code == 200
    assert denied.status_code == 429
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["workflow_type"] == "evidence_signed_url"
    get_settings.cache_clear()


def test_research_sprint_rate_limit_denies_before_planning_run(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("SECURITY_RESEARCH_SPRINT_RATE_LIMIT_WORKSPACE_MAX_REQUESTS", "1")
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    first = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={"objective": "Plan the first research sprint."},
    )
    denied = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={"objective": "Plan a second research sprint."},
    )

    assert first.status_code == 200
    assert denied.status_code == 429
    assert db_session.scalar(select(AIRun).where(AIRun.workflow_type == "research_sprint_planning"))
    assert (
        db_session.scalar(
            select(AuditEvent)
            .where(AuditEvent.event_type == "security_policy_denied")
            .order_by(AuditEvent.created_at.desc())
        )
        is not None
    )
    get_settings.cache_clear()


def test_model_call_rate_limit_denies_before_provider_reservation(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    monkeypatch.setenv("SECURITY_MODEL_CALL_RATE_LIMIT_USER_MAX_REQUESTS", "1")
    monkeypatch.setenv("SECURITY_MODEL_CALL_RATE_LIMIT_WORKSPACE_MAX_REQUESTS", "10")
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    security_policy_service.enforce_model_call_rate_limit(
        db_session,
        auth,
        get_settings(),
        project_id=project_id,
    )
    with pytest.raises(HTTPException, match="model-call rate limit") as exc_info:
        security_policy_service.enforce_model_call_rate_limit(
            db_session,
            auth,
            get_settings(),
            project_id=project_id,
        )

    assert exc_info.value.status_code == 429
    get_settings.cache_clear()


def test_model_call_rate_scope_reserves_before_non_sprint_provider_call(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    monkeypatch.setenv("SECURITY_MODEL_CALL_RATE_LIMIT_USER_MAX_REQUESTS", "1")
    monkeypatch.setenv("SECURITY_MODEL_CALL_RATE_LIMIT_WORKSPACE_MAX_REQUESTS", "10")
    get_settings.cache_clear()
    security_policy_service.reset_policy_state()

    with workflow_budget_service.model_call_rate_scope(
        db_session,
        auth,
        get_settings(),
        project_id=project_id,
    ):
        workflow_budget_service.reserve_model_call()
        with pytest.raises(HTTPException, match="model-call rate limit") as exc_info:
            workflow_budget_service.reserve_model_call()

    assert exc_info.value.status_code == 429
    get_settings.cache_clear()


def test_expensive_workflow_rate_limit_uses_hashed_redis_buckets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.counts: dict[str, int] = {}

        def eval(self, _script: str, _keys: int, key: str, _window_seconds: int) -> int:
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]

    fake_redis = FakeRedis()
    monkeypatch.setenv("SECURITY_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("SECURITY_RATE_LIMIT_USER_MAX_REQUESTS", "1")
    monkeypatch.setenv("SECURITY_RATE_LIMIT_WORKSPACE_MAX_REQUESTS", "10")
    monkeypatch.setattr(security_policy_service, "_redis_client", lambda _settings: fake_redis)
    get_settings.cache_clear()
    project_id = _create_project(client)

    first = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Signal", "text": "Founder interview notes show a repeated workflow."},
    )
    denied = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Signal 2", "text": "More notes."},
    )

    assert first.status_code == 201
    assert denied.status_code == 429
    assert len(fake_redis.counts) == 5
    assert all(key.startswith("thesys:security-rate:v1:") for key in fake_redis.counts)
    assert all("evidence_note_ingestion" not in key for key in fake_redis.counts)
    get_settings.cache_clear()


def test_expensive_workflow_rate_limit_fails_closed_when_redis_is_unavailable(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_settings: Settings) -> object:
        raise security_policy_service.RedisError("offline")

    project_id = _create_project(client)
    monkeypatch.setenv("SECURITY_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(security_policy_service, "_redis_client", unavailable)
    monkeypatch.setattr(
        security_policy_service,
        "enforce_authenticated_request_rate_limit",
        lambda *_args, **_kwargs: None,
    )
    get_settings.cache_clear()

    response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": "Signal", "text": "Founder interview notes show a repeated workflow."},
    )

    assert response.status_code == 503
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["status_code"] == 503
    get_settings.cache_clear()


def test_concurrency_guard_denies_second_expensive_workflow(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECURITY_MAX_CONCURRENT_WORKFLOWS", "1")
    get_settings.cache_clear()
    settings = get_settings()
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")

    with security_policy_service.guarded_workflow(
        db_session,
        auth,
        settings,
        project_id=project_id,
        workflow_type="agentic_research",
        estimate=security_policy_service.WorkflowBudgetEstimate(
            estimated_tokens=1,
            estimated_cost=Decimal("0"),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            with security_policy_service.guarded_workflow(
                db_session,
                auth,
                settings,
                project_id=project_id,
                workflow_type="agentic_research",
                estimate=security_policy_service.WorkflowBudgetEstimate(
                    estimated_tokens=1,
                    estimated_cost=Decimal("0"),
                ),
            ):
                pass

    assert exc_info.value.status_code == 409
    get_settings.cache_clear()


def test_budget_preflight_denies_before_airun_creation(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_WORKFLOW_MAX_TOKENS", "1000")
    monkeypatch.setenv("AI_WORKFLOW_DEFAULT_ESTIMATED_TOKENS", "4000")
    get_settings.cache_clear()
    project_id = _create_project(client)

    response = client.post(f"/api/projects/{project_id}/guide/recommend")

    assert response.status_code == 402
    guide_run = db_session.scalar(
        select(AIRun).where(AIRun.workflow_type == "guide_recommendation")
    )
    assert guide_run is None
    get_settings.cache_clear()


def test_provider_egress_guard_denies_unapproved_live_provider_host(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://evil.example")
    monkeypatch.setenv("PROVIDER_EGRESS_ALLOWED_HOSTS", "localhost,127.0.0.1")
    get_settings.cache_clear()
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "What should I do next?"},
    )

    assert response.status_code == 403
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["workflow_type"] == "guide_chat"
    get_settings.cache_clear()


def test_runtime_kill_switches_deny_model_providers_and_external_egress(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session, "owner")
    settings = Settings(
        llm_stub_mode="never",
        litellm_base_url="https://models.example.test",
        provider_egress_allowed_hosts=["models.example.test", "api.tavily.com"],
    )
    kill_switch_service.update_state(
        db_session,
        auth,
        settings,
        KillSwitchUpdate(disable_model_provider=True),
    )

    with pytest.raises(HTTPException, match="Model-provider access") as model_denial:
        with security_policy_service.guarded_workflow(
            db_session,
            auth,
            settings,
            project_id=project_id,
            workflow_type="kill_switch_model_provider",
            estimate=security_policy_service.merge_estimate(
                settings,
                provider_urls=security_policy_service.llm_provider_urls(settings),
            ),
        ):
            pass

    assert model_denial.value.status_code == 403
    kill_switch_service.update_state(
        db_session,
        auth,
        settings,
        KillSwitchUpdate(disable_model_provider=False, disable_external_egress=True),
    )
    with pytest.raises(HTTPException, match="External network access") as egress_denial:
        with security_policy_service.guarded_workflow(
            db_session,
            auth,
            settings,
            project_id=project_id,
            workflow_type="kill_switch_external_egress",
            estimate=security_policy_service.merge_estimate(
                settings,
                provider_urls=("https://api.tavily.com",),
            ),
        ):
            pass

    assert egress_denial.value.status_code == 403
    denials = list(
        db_session.scalars(
            select(AuditEvent)
            .where(AuditEvent.event_type == "security_policy_denied")
            .order_by(AuditEvent.created_at.asc())
        )
    )
    assert [event.event_metadata["workflow_type"] for event in denials[-2:]] == [
        "kill_switch_model_provider",
        "kill_switch_external_egress",
    ]


def test_model_provider_kill_switch_returns_safe_api_denial_before_run_creation(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://models.example.test")
    monkeypatch.setenv("PROVIDER_EGRESS_ALLOWED_HOSTS", "models.example.test")
    get_settings.cache_clear()
    try:
        project_id = _create_project(client)
        update_response = client.patch(
            "/api/security/kill-switches",
            json={"disable_model_provider": True},
        )
        response = client.post(
            f"/api/projects/{project_id}/guide/chat",
            json={"message": "What should I do next?"},
        )
    finally:
        get_settings.cache_clear()

    assert update_response.status_code == 200
    assert response.status_code == 403
    assert response.json() == {"detail": "Model-provider access is temporarily unavailable."}
    assert db_session.scalar(select(AIRun).where(AIRun.workflow_type == "guide_chat")) is None
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["workflow_type"] == "guide_chat"


def test_source_fetching_kill_switch_denies_url_ingestion_before_source_creation(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        "app.services.evidence_service._fetch_url",
        lambda *_args: (_ for _ in ()).throw(AssertionError("URL fetch must not run.")),
    )
    update_response = client.patch(
        "/api/security/kill-switches",
        json={"disable_source_fetching": True},
    )
    response = client.post(
        f"/api/projects/{project_id}/evidence/url",
        json={"url": "https://example.test/research"},
    )

    assert update_response.status_code == 200
    assert response.status_code == 403
    assert response.json() == {"detail": "Source fetching is temporarily unavailable."}
    assert db_session.scalar(select(EvidenceSource)) is None
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "security_policy_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["workflow_type"] == "evidence_url_ingestion"


def test_tool_denial_is_audited_and_persisted_proposals_are_redacted(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    secret = "sk-testsecret123456789"
    bearer = "Bearer abcdefghijklmnopqrstuvwxyz0123456789"

    viewer_auth = _dev_auth(db_session, "viewer")
    with pytest.raises(HTTPException) as exc_info:
        tool_service.create_proposal(
            db_session,
            viewer_auth,
            project_id,
            "propose_memory_update",
            {
                "summary": "Update project memory",
                "api_key": secret,
                "contact": "founder@example.com",
            },
        )
    assert exc_info.value.status_code == 403

    denial = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "tool_invocation_denied")
    )
    assert denial is not None
    assert denial.risk_level == "medium"
    assert denial.event_metadata["role"] == "viewer"

    owner_auth = _dev_auth(db_session, "owner")
    invocation = tool_service.create_proposal(
        db_session,
        owner_auth,
        project_id,
        "propose_memory_update",
        {
            "summary": f"Use {secret} for founder@example.com",
            "api_key": secret,
            "notes": f"Authorization: {bearer} contact founder@example.com",
        },
        input_json={"Authorization": bearer},
    )

    db_session.refresh(invocation)
    approval = db_session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.entity_id == invocation.id)
    )
    assert approval is not None
    persisted_text = f"{invocation.input_json} {invocation.output_json} {approval.proposed_change}"
    assert secret not in persisted_text
    assert bearer not in persisted_text
    assert "founder@example.com" not in persisted_text
    assert "[redacted]" in persisted_text


def test_high_risk_tool_approval_requires_admin_or_owner(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")
    invocation = tool_service.create_proposal(
        db_session,
        owner_auth,
        project_id,
        "propose_decision",
        {
            "summary": "Record a kill decision.",
            "decision_type": "kill",
            "title": "Kill the idea",
            "rationale": "The evidence does not support the wedge.",
        },
    )
    approval = db_session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.entity_id == invocation.id)
    )
    assert approval is not None
    assert approval.request_type == "decision"
    assert approval.risk_level == "high"

    editor_response = client.post(
        f"/api/projects/{project_id}/approvals/{approval.id}/approve",
        headers={"X-Dev-User-Role": "editor"},
    )
    assert editor_response.status_code == 403
    db_session.refresh(invocation)
    assert invocation.status == "requested"

    admin_response = client.post(
        f"/api/projects/{project_id}/approvals/{approval.id}/approve",
        headers={"X-Dev-User-Role": "admin"},
    )
    assert admin_response.status_code == 200
    db_session.refresh(invocation)
    db_session.refresh(approval)
    assert invocation.status == "approved"
    assert approval.status == "approved"


def test_research_plan_creates_approval_request_and_audit_events(
    client: TestClient,
) -> None:
    project_id = _create_project(client)

    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        headers={"X-Dev-User-Role": "owner"},
        json={"objective": "Evaluate competitor pressure and validation risks."},
    )
    assert plan_response.status_code == 200

    approvals_response = client.get(
        f"/api/projects/{project_id}/approvals",
        headers={"X-Dev-User-Role": "owner"},
        params={"status_filter": "pending"},
    )
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()["approvals"]
    assert any(approval["request_type"] == "research_plan" for approval in approvals)

    audit_response = client.get(
        f"/api/projects/{project_id}/audit-events",
        headers={"X-Dev-User-Role": "owner"},
    )
    assert audit_response.status_code == 200
    event_types = {event["event_type"] for event in audit_response.json()["events"]}
    assert "research_sprint_started" in event_types
    assert "tool_invocation_requested" in event_types


def test_tool_input_guard_rejects_unsupported_fields_and_audits_denial(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")

    with pytest.raises(HTTPException) as exc_info:
        tool_service.execute_tool(
            db_session,
            owner_auth,
            get_settings(),
            project_id,
            "list_assumptions",
            {"query": "ignored by this read tool"},
            requested_by="agent",
        )

    assert exc_info.value.status_code == 422
    assert db_session.scalar(
        select(ToolInvocation).where(ToolInvocation.tool_name == "list_assumptions")
    ) is None
    denial = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "tool_invocation_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert denial is not None
    assert denial.event_metadata["reason"] == "input_guard_failed"
    assert "unsupported field" in denial.event_metadata["detail"]


def test_tool_scope_guard_rejects_conflicting_research_sprint_ids(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")
    scoped_sprint_id = uuid.uuid4()
    other_sprint_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        tool_service.execute_tool(
            db_session,
            owner_auth,
            get_settings(),
            project_id,
            "get_research_memo",
            {"research_sprint_id": str(other_sprint_id)},
            research_sprint_id=scoped_sprint_id,
            requested_by="agent",
        )

    assert exc_info.value.status_code == 422
    denial = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "tool_invocation_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert denial is not None
    assert denial.event_metadata["reason"] == "scope_guard_failed"


def test_scoped_proposal_guard_requires_matching_research_sprint_id(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")

    with pytest.raises(HTTPException) as exc_info:
        tool_service.create_proposal(
            db_session,
            owner_auth,
            project_id,
            "propose_memory_update",
            {"summary": "Missing scoped sprint id."},
            research_sprint_id=uuid.uuid4(),
            requested_by="agent",
        )

    assert exc_info.value.status_code == 422
    denial = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "tool_invocation_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert denial is not None
    assert denial.event_metadata["reason"] == "scope_guard_failed"


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        headers={"X-Dev-User-Role": "owner"},
        json={
            "name": "Governed research workspace",
            "short_description": "AI workspace for governed founder research.",
            "initial_thesis": "Founders need evidence before committing to a wedge.",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _dev_auth(db_session: Session, role: str):
    settings = get_settings()
    return ensure_dev_identity(
        db_session,
        email=settings.dev_auth_default_email,
        display_name=settings.dev_auth_default_name,
        role=role,
    )


def _sign_jwt(secret: str, claims: dict, *, header: dict | None = None) -> str:
    jwt_header = {"alg": "HS256", "typ": "JWT", **(header or {})}
    encoded_header = _base64url(json.dumps(jwt_header, separators=(",", ":")).encode("utf-8"))
    encoded_claims = _base64url(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_claims}".encode()
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_claims}.{_base64url(signature)}"


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
