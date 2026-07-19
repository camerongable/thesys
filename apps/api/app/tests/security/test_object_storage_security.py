import json
import uuid
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import AuditEvent, SecurityAlert, SecurityEvent
from app.services import object_storage_service


class FakeS3Client:
    def __init__(self, *, failure: str | None = None, head_error: ClientError | None = None):
        self.failure = failure
        self.head_error = head_error
        self.calls: list[tuple[str, dict]] = []

    def head_bucket(self, **kwargs) -> None:
        self.calls.append(("head_bucket", kwargs))
        if self.head_error is not None:
            raise self.head_error

    def create_bucket(self, **kwargs) -> None:
        self.calls.append(("create_bucket", kwargs))

    def put_public_access_block(self, **kwargs) -> None:
        self.calls.append(("put_public_access_block", kwargs))

    def put_bucket_ownership_controls(self, **kwargs) -> None:
        self.calls.append(("put_bucket_ownership_controls", kwargs))

    def put_bucket_encryption(self, **kwargs) -> None:
        self.calls.append(("put_bucket_encryption", kwargs))

    def put_bucket_lifecycle_configuration(self, **kwargs) -> None:
        self.calls.append(("put_bucket_lifecycle_configuration", kwargs))

    def get_public_access_block(self, **kwargs) -> dict:
        self.calls.append(("get_public_access_block", kwargs))
        values = {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
        if self.failure == "public":
            values["BlockPublicPolicy"] = False
        return {"PublicAccessBlockConfiguration": values}

    def get_bucket_ownership_controls(self, **kwargs) -> dict:
        self.calls.append(("get_bucket_ownership_controls", kwargs))
        ownership = "ObjectWriter" if self.failure == "ownership" else "BucketOwnerEnforced"
        return {"OwnershipControls": {"Rules": [{"ObjectOwnership": ownership}]}}

    def get_bucket_encryption(self, **kwargs) -> dict:
        self.calls.append(("get_bucket_encryption", kwargs))
        algorithm = "aws:kms" if self.failure == "encryption" else "AES256"
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": algorithm}}
                ]
            }
        }

    def get_bucket_lifecycle_configuration(self, **kwargs) -> dict:
        self.calls.append(("get_bucket_lifecycle_configuration", kwargs))
        days = 999 if self.failure == "lifecycle" else 45
        return {
            "Rules": [
                {
                    "Status": "Enabled",
                    "Filter": {"Prefix": "workspaces/"},
                    "Expiration": {"Days": days},
                }
            ]
        }

    def get_bucket_policy(self, **kwargs) -> dict:
        self.calls.append(("get_bucket_policy", kwargs))
        principal = {"AWS": "arn:aws:iam::123456789012:root"} if self.failure == "tls" else "*"
        return {
            "Policy": json.dumps(
                {
                    "Statement": [
                        {
                            "Effect": "Deny",
                            "Principal": principal,
                            "Action": "s3:*",
                            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                        }
                    ]
                }
            )
        }

    def put_object(self, **kwargs) -> None:
        self.calls.append(("put_object", kwargs))

    def generate_presigned_url(self, operation: str, **kwargs) -> str:
        self.calls.append(("generate_presigned_url", {"operation": operation, **kwargs}))
        return "https://download.example.com/evidence?signature=short-lived"

    def delete_object(self, **kwargs) -> None:
        self.calls.append(("delete_object", kwargs))


@pytest.fixture(autouse=True)
def clear_storage_security_cache():
    object_storage_service.reset_bucket_security_cache()
    yield
    object_storage_service.reset_bucket_security_cache()


def test_hosted_object_storage_configuration_fails_closed() -> None:
    base = {
        "environment": "production",
        "auth_mode": "api_key",
        "secret_provider": "cloud",
        "database_url": (
            "postgresql+psycopg://thesys_api:secret@db.example/thesys?sslmode=verify-full"
        ),
        "redis_url": "rediss://redis.example:6380/0",
        "malware_scanner_mode": "clamav",
    }

    with pytest.raises(ValidationError, match="OBJECT_STORAGE_MODE"):
        Settings(**base)
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(**base, object_storage_mode="s3", s3_endpoint_url="http://s3.example.com")
    with pytest.raises(ValidationError, match="must not create"):
        Settings(
            **base,
            object_storage_mode="s3",
            s3_endpoint_url="https://s3.example.com",
            s3_auto_create_bucket=True,
            s3_verify_bucket_security=True,
        )
    with pytest.raises(ValidationError, match="verification is required"):
        Settings(
            **base,
            object_storage_mode="s3",
            s3_endpoint_url="https://s3.example.com",
        )

    settings = Settings(
        **base,
        object_storage_mode="s3",
        s3_endpoint_url="https://s3.example.com",
        s3_verify_bucket_security=True,
    )
    assert settings.object_storage_mode == "s3"


def test_scoped_s3_write_download_and_delete_enforce_security(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeS3Client()
    monkeypatch.setattr(object_storage_service, "_s3_client", lambda _settings: fake)
    settings = _secure_s3_settings()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()

    key = object_storage_service.put_evidence_object(
        settings,
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source_id,
        filename="interview-notes.md",
        body=b"private evidence",
        content_type="text/markdown",
    )
    download = object_storage_service.prepare_evidence_download(
        settings,
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source_id,
        key=key,
        filename="interview-notes.md",
        content_type="text/markdown",
    )
    object_storage_service.delete_evidence_object(
        settings,
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source_id,
        key=key,
    )

    assert key == (
        f"workspaces/{workspace_id}/projects/{project_id}/sources/"
        f"{source_id}/interview-notes.md"
    )
    put_call = _call(fake, "put_object")
    assert put_call["ServerSideEncryption"] == "AES256"
    assert put_call["ContentType"] == "text/markdown"
    assert put_call["ContentDisposition"] == 'attachment; filename="interview-notes.md"'
    assert "ACL" not in put_call
    presign_call = _call(fake, "generate_presigned_url")
    assert presign_call["ExpiresIn"] == 120
    assert presign_call["Params"]["ResponseContentType"] == "text/markdown"
    assert presign_call["Params"]["ResponseContentDisposition"].startswith("attachment;")
    assert download.url is not None and download.url.startswith("https://")
    assert _call(fake, "delete_object") == {"Bucket": "private-bucket", "Key": key}
    assert sum(name == "get_public_access_block" for name, _ in fake.calls) == 1


def test_bucket_security_is_verified_on_a_fresh_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeS3Client()
    monkeypatch.setattr(object_storage_service, "_s3_client", lambda _settings: fake)
    monkeypatch.setattr(object_storage_service, "monotonic", lambda: 10.0)

    object_storage_service.put_evidence_object(
        _secure_s3_settings(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        filename="source.pdf",
        body=b"%PDF fixture",
        content_type="application/pdf",
    )

    assert _call(fake, "get_public_access_block") == {"Bucket": "private-bucket"}


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("public", "public access"),
        ("ownership", "ACL ownership"),
        ("encryption", "encryption"),
        ("lifecycle", "retention"),
        ("tls", "require TLS"),
    ],
)
def test_bucket_verification_rejects_noncompliant_controls(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    message: str,
) -> None:
    fake = FakeS3Client(failure=failure)
    monkeypatch.setattr(object_storage_service, "_s3_client", lambda _settings: fake)

    with pytest.raises(object_storage_service.ObjectStorageError, match=message):
        object_storage_service.put_evidence_object(
            _secure_s3_settings(),
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            filename="source.pdf",
            body=b"%PDF fixture",
            content_type="application/pdf",
        )


def test_bucket_auto_creation_only_handles_missing_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    access_denied = FakeS3Client(head_error=_client_error("AccessDenied", 403))
    monkeypatch.setattr(object_storage_service, "_s3_client", lambda _settings: access_denied)
    settings = Settings(OBJECT_STORAGE_MODE="s3", S3_AUTO_CREATE_BUCKET=True)
    assert settings.object_storage_mode == "s3"

    with pytest.raises(object_storage_service.ObjectStorageError, match="unavailable"):
        object_storage_service.put_evidence_object(
            settings,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            filename="source.txt",
            body=b"source",
            content_type="text/plain",
        )
    assert not any(name == "create_bucket" for name, _ in access_denied.calls)

    missing = FakeS3Client(head_error=_client_error("NoSuchBucket", 404))
    monkeypatch.setattr(object_storage_service, "_s3_client", lambda _settings: missing)
    object_storage_service.put_evidence_object(
        settings,
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        filename="source.txt",
        body=b"source",
        content_type="text/plain",
    )
    call_names = {name for name, _ in missing.calls}
    assert {
        "create_bucket",
        "put_public_access_block",
        "put_bucket_ownership_controls",
        "put_bucket_encryption",
        "put_bucket_lifecycle_configuration",
        "put_object",
    } <= call_names


def test_storage_keys_cannot_cross_workspace_scope(tmp_path: Path) -> None:
    settings = Settings(local_object_storage_path=str(tmp_path))
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()
    key = object_storage_service.put_evidence_object(
        settings,
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source_id,
        filename="private.txt",
        body=b"private",
        content_type="text/plain",
    )

    with pytest.raises(object_storage_service.ObjectStorageError, match="authorized scope"):
        object_storage_service.prepare_evidence_download(
            settings,
            workspace_id=uuid.uuid4(),
            project_id=project_id,
            source_id=source_id,
            key=key,
            filename="private.txt",
            content_type="text/plain",
        )
    with pytest.raises(object_storage_service.ObjectStorageError, match="filename"):
        object_storage_service.put_evidence_object(
            settings,
            workspace_id=workspace_id,
            project_id=project_id,
            source_id=source_id,
            filename="../../escape.txt",
            body=b"private",
            content_type="text/plain",
        )


def test_evidence_storage_route_authorizes_signs_and_audits(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeS3Client()
    monkeypatch.setattr(object_storage_service, "_s3_client", lambda _settings: fake)
    monkeypatch.setenv("OBJECT_STORAGE_MODE", "s3")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.example.com")
    monkeypatch.setenv("S3_BUCKET", "private-bucket")
    monkeypatch.setenv("S3_VERIFY_BUCKET_SECURITY", "true")
    monkeypatch.setenv("S3_RETENTION_DAYS", "45")
    monkeypatch.setenv("S3_PRESIGNED_URL_TTL_SECONDS", "120")
    get_settings.cache_clear()
    user_a = {"X-Dev-User-Email": "storage-a@example.com", "X-Dev-User-Name": "A"}
    user_b = {"X-Dev-User-Email": "storage-b@example.com", "X-Dev-User-Name": "B"}
    project_id = client.post(
        "/api/projects",
        headers=user_a,
        json={"name": "Private storage"},
    ).json()["id"]
    upload = client.post(
        f"/api/projects/{project_id}/evidence/file",
        headers=user_a,
        files={"file": ("private.md", b"Private research evidence.", "text/markdown")},
    )
    source_id = upload.json()["id"]

    denied = client.get(
        f"/api/projects/{project_id}/evidence/{source_id}/download",
        headers=user_b,
        follow_redirects=False,
    )
    download = client.get(
        f"/api/projects/{project_id}/evidence/{source_id}/download",
        headers=user_a,
        follow_redirects=False,
    )
    deleted = client.delete(
        f"/api/projects/{project_id}/evidence/{source_id}",
        headers=user_a,
    )

    assert upload.status_code == 201
    assert denied.status_code == 404
    assert download.status_code == 307
    assert download.headers["location"].startswith("https://download.example.com/")
    assert download.headers["cache-control"] == "private, no-store"
    assert deleted.status_code == 204
    assert sum(name == "generate_presigned_url" for name, _ in fake.calls) == 1
    events = list(
        db_session.scalars(
            select(AuditEvent).where(AuditEvent.project_id == uuid.UUID(project_id))
        )
    )
    assert {event.event_type for event in events} >= {
        "object_stored",
        "signed_url_created",
        "object_deleted",
    }
    serialized_metadata = json.dumps([event.event_metadata for event in events])
    assert "signature=short-lived" not in serialized_metadata
    assert "workspaces/" not in serialized_metadata


def test_distinct_evidence_downloads_detect_one_mass_export_attempt(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECURITY_MASS_EXPORT_DISTINCT_SOURCE_THRESHOLD", "3")
    get_settings.cache_clear()
    project_id = client.post("/api/projects", json={"name": "Export detection"}).json()["id"]
    source_ids: list[str] = []
    for index in range(4):
        upload = client.post(
            f"/api/projects/{project_id}/evidence/file",
            files={
                "file": (
                    f"export-{index + 1}.txt",
                    f"Private export evidence {index + 1}.".encode(),
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 201
        source_ids.append(upload.json()["id"])

    for source_id in source_ids:
        response = client.get(f"/api/projects/{project_id}/evidence/{source_id}/download")
        assert response.status_code == 200

    export_events = list(
        db_session.scalars(select(AuditEvent).where(AuditEvent.event_type == "mass_export_attempt"))
    )
    assert len(export_events) == 1
    event = export_events[0]
    assert event.risk_level == "high"
    assert event.event_metadata == {
        "distinct_source_count": 3,
        "request_id": event.event_metadata["request_id"],
        "window_seconds": 900,
    }
    assert str(uuid.UUID(event.event_metadata["request_id"])) == event.event_metadata["request_id"]
    assert all(source_id not in str(event.__dict__) for source_id in source_ids)
    security_event = db_session.scalar(
        select(SecurityEvent).where(SecurityEvent.audit_event_id == event.id)
    )
    assert security_event is not None
    assert security_event.event_type == "mass_export_attempt"
    assert security_event.severity == "high"
    assert all(source_id not in str(security_event.__dict__) for source_id in source_ids)
    alert = db_session.scalar(
        select(SecurityAlert).where(SecurityAlert.security_event_id == security_event.id)
    )
    assert alert is not None
    assert alert.severity == "high"
    get_settings.cache_clear()


def test_project_deletion_removes_objects_and_preserves_audit(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeS3Client()
    monkeypatch.setattr(object_storage_service, "_s3_client", lambda _settings: fake)
    monkeypatch.setenv("OBJECT_STORAGE_MODE", "s3")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.example.com")
    monkeypatch.setenv("S3_BUCKET", "private-bucket")
    monkeypatch.setenv("S3_VERIFY_BUCKET_SECURITY", "true")
    monkeypatch.setenv("S3_RETENTION_DAYS", "45")
    get_settings.cache_clear()
    headers = {
        "X-Dev-User-Email": "project-delete@example.com",
        "X-Dev-User-Name": "Project Delete",
    }
    project = client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Delete private storage"},
    ).json()
    project_id = project["id"]
    upload = client.post(
        f"/api/projects/{project_id}/evidence/file",
        headers=headers,
        files={"file": ("private.txt", b"Delete this evidence.", "text/plain")},
    )
    source_id = upload.json()["id"]

    response = client.delete(f"/api/projects/{project_id}", headers=headers)

    assert upload.status_code == 201
    assert response.status_code == 204
    assert _call(fake, "delete_object")["Key"].startswith(
        f"workspaces/{project['workspace_id']}/projects/{project_id}/sources/{source_id}/"
    )
    event = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "object_deleted",
            AuditEvent.entity_id == uuid.UUID(source_id),
        )
    )
    assert event is not None
    assert event.project_id is None
    assert event.event_metadata == {
        "storage_mode": "s3",
        "deleted_project_id": project_id,
        "request_id": event.event_metadata["request_id"],
    }
    assert str(uuid.UUID(event.event_metadata["request_id"])) == event.event_metadata["request_id"]


def _secure_s3_settings() -> Settings:
    settings = Settings(
        OBJECT_STORAGE_MODE="s3",
        S3_ENDPOINT_URL="https://s3.example.com",
        S3_BUCKET="private-bucket",
        S3_VERIFY_BUCKET_SECURITY=True,
        S3_RETENTION_DAYS=45,
        S3_PRESIGNED_URL_TTL_SECONDS=120,
    )
    assert settings.object_storage_mode == "s3"
    assert settings.s3_verify_bucket_security is True
    return settings


def _call(client: FakeS3Client, name: str) -> dict:
    return next(arguments for call_name, arguments in client.calls if call_name == name)


def _client_error(code: str, status_code: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "internal backend detail"},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        },
        "HeadBucket",
    )
