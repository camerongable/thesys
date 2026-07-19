import json
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from time import monotonic
from typing import Literal
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.core.security import SecurityValidationError, sanitize_filename
from app.security.secrets import SecretName, SecretProviderError, resolve_secret

_BUCKET_SECURITY_CACHE_SECONDS = 300.0
_CONTENT_TYPE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$"
)
_bucket_security_cache: dict[tuple[str, ...], float] = {}
_bucket_security_lock = threading.Lock()


class ObjectStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObjectDownload:
    storage_mode: Literal["local", "s3"]
    content_type: str
    content_disposition: str
    expires_at: datetime
    url: str | None = None
    local_path: Path | None = None


def put_evidence_object(
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    filename: str,
    body: bytes,
    content_type: str,
) -> str:
    safe_filename = _safe_filename(filename)
    safe_content_type = _safe_content_type(content_type)
    key = _evidence_key(workspace_id, project_id, source_id, safe_filename)
    if settings.object_storage_mode == "s3":
        _put_s3_object(
            settings,
            key=key,
            body=body,
            filename=safe_filename,
            content_type=safe_content_type,
        )
    else:
        destination = _local_path(settings, key)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
        except OSError:
            raise ObjectStorageError("Could not store evidence object.") from None
    return key


def prepare_evidence_download(
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    key: str,
    filename: str,
    content_type: str,
) -> ObjectDownload:
    safe_filename = _safe_filename(filename)
    safe_content_type = _safe_content_type(content_type)
    _require_evidence_scope(key, workspace_id, project_id, source_id)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.s3_presigned_url_ttl_seconds)
    content_disposition = _content_disposition(safe_filename)

    if settings.object_storage_mode == "local":
        local_path = _local_path(settings, key)
        if not local_path.is_file():
            raise ObjectStorageError("Stored evidence object is unavailable.")
        return ObjectDownload(
            storage_mode="local",
            content_type=safe_content_type,
            content_disposition=content_disposition,
            expires_at=expires_at,
            local_path=local_path,
        )

    client = _s3_client(settings)
    _ensure_bucket_security(settings, client)
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": key,
                "ResponseContentType": safe_content_type,
                "ResponseContentDisposition": content_disposition,
            },
            ExpiresIn=settings.s3_presigned_url_ttl_seconds,
            HttpMethod="GET",
        )
    except (BotoCoreError, ClientError):
        raise ObjectStorageError("Could not authorize evidence download.") from None
    if settings.environment in {"staging", "production"}:
        parsed_url = urlparse(url)
        endpoint_host = urlparse(settings.s3_endpoint_url).hostname or ""
        if (
            parsed_url.scheme != "https"
            or not parsed_url.hostname
            or (
                parsed_url.hostname != endpoint_host
                and not parsed_url.hostname.endswith(f".{endpoint_host}")
            )
        ):
            raise ObjectStorageError("Object storage returned an insecure download URL.")
    return ObjectDownload(
        storage_mode="s3",
        content_type=safe_content_type,
        content_disposition=content_disposition,
        expires_at=expires_at,
        url=url,
    )


def delete_evidence_object(
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    key: str,
) -> None:
    _require_evidence_scope(key, workspace_id, project_id, source_id)
    if settings.object_storage_mode == "local":
        path = _local_path(settings, key)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            raise ObjectStorageError("Could not delete evidence object.") from None
        return

    client = _s3_client(settings)
    _ensure_bucket_security(settings, client)
    try:
        client.delete_object(Bucket=settings.s3_bucket, Key=key)
    except (BotoCoreError, ClientError):
        raise ObjectStorageError("Could not delete evidence object.") from None


def reset_bucket_security_cache() -> None:
    with _bucket_security_lock:
        _bucket_security_cache.clear()


def _put_s3_object(
    settings: Settings,
    *,
    key: str,
    body: bytes,
    filename: str,
    content_type: str,
) -> None:
    client = _s3_client(settings)
    _ensure_bucket_security(settings, client)
    parameters: dict[str, object] = {
        "Bucket": settings.s3_bucket,
        "Key": key,
        "Body": body,
        "ContentType": content_type,
        "ContentDisposition": _content_disposition(filename),
        "ServerSideEncryption": settings.s3_server_side_encryption,
    }
    if settings.s3_server_side_encryption == "aws:kms" and settings.s3_kms_key_id:
        parameters["SSEKMSKeyId"] = settings.s3_kms_key_id
    try:
        client.put_object(**parameters)
    except (BotoCoreError, ClientError):
        raise ObjectStorageError("Could not store evidence object.") from None


def _s3_client(settings: Settings):
    try:
        access_key_id = resolve_secret(settings, SecretName.S3_ACCESS_KEY_ID)
        secret_access_key = resolve_secret(settings, SecretName.S3_SECRET_ACCESS_KEY)
    except SecretProviderError:
        raise ObjectStorageError("Object storage credentials are unavailable.") from None
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )


def _ensure_bucket_security(settings: Settings, client) -> None:
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError as exc:
        if not settings.s3_auto_create_bucket or not _is_missing_bucket(exc):
            raise ObjectStorageError("Object storage bucket is unavailable.") from None
        try:
            client.create_bucket(Bucket=settings.s3_bucket)
            _configure_new_bucket(settings, client)
        except (BotoCoreError, ClientError):
            raise ObjectStorageError("Object storage bucket setup failed.") from None
    except BotoCoreError:
        raise ObjectStorageError("Object storage bucket is unavailable.") from None

    if settings.s3_verify_bucket_security:
        _verify_bucket_security(settings, client)


def _configure_new_bucket(settings: Settings, client) -> None:
    client.put_public_access_block(
        Bucket=settings.s3_bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    client.put_bucket_ownership_controls(
        Bucket=settings.s3_bucket,
        OwnershipControls={"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
    )
    encryption_rule: dict[str, str] = {
        "SSEAlgorithm": settings.s3_server_side_encryption,
    }
    if settings.s3_server_side_encryption == "aws:kms" and settings.s3_kms_key_id:
        encryption_rule["KMSMasterKeyID"] = settings.s3_kms_key_id
    client.put_bucket_encryption(
        Bucket=settings.s3_bucket,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": encryption_rule}]
        },
    )
    client.put_bucket_lifecycle_configuration(
        Bucket=settings.s3_bucket,
        LifecycleConfiguration={"Rules": [_lifecycle_rule(settings)]},
    )


def _verify_bucket_security(settings: Settings, client) -> None:
    cache_key = (
        settings.s3_endpoint_url,
        settings.s3_bucket,
        settings.s3_server_side_encryption,
        settings.s3_kms_key_id or "",
        str(settings.s3_retention_days),
    )
    now = monotonic()
    with _bucket_security_lock:
        last_verified = _bucket_security_cache.get(cache_key)
        if (
            last_verified is not None
            and now - last_verified < _BUCKET_SECURITY_CACHE_SECONDS
        ):
            return

    try:
        public_access = client.get_public_access_block(Bucket=settings.s3_bucket)[
            "PublicAccessBlockConfiguration"
        ]
        if not all(
            public_access.get(field) is True
            for field in (
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            )
        ):
            raise ObjectStorageError("Object storage bucket permits public access.")

        ownership_rules = client.get_bucket_ownership_controls(Bucket=settings.s3_bucket)[
            "OwnershipControls"
        ]["Rules"]
        if not any(
            rule.get("ObjectOwnership") == "BucketOwnerEnforced"
            for rule in ownership_rules
        ):
            raise ObjectStorageError("Object storage bucket permits object ACL ownership.")

        encryption_rules = client.get_bucket_encryption(Bucket=settings.s3_bucket)[
            "ServerSideEncryptionConfiguration"
        ]["Rules"]
        if not _has_required_encryption(settings, encryption_rules):
            raise ObjectStorageError("Object storage bucket encryption is not compliant.")

        lifecycle_rules = client.get_bucket_lifecycle_configuration(Bucket=settings.s3_bucket)[
            "Rules"
        ]
        if not any(_is_required_lifecycle_rule(settings, rule) for rule in lifecycle_rules):
            raise ObjectStorageError("Object storage retention policy is not compliant.")

        policy = json.loads(client.get_bucket_policy(Bucket=settings.s3_bucket)["Policy"])
        if not _denies_insecure_transport(policy):
            raise ObjectStorageError("Object storage bucket does not require TLS.")
    except ObjectStorageError:
        raise
    except (BotoCoreError, ClientError, KeyError, TypeError, ValueError):
        raise ObjectStorageError("Object storage bucket security could not be verified.") from None

    with _bucket_security_lock:
        _bucket_security_cache[cache_key] = now


def _has_required_encryption(settings: Settings, rules: list[dict]) -> bool:
    for rule in rules:
        default = rule.get("ApplyServerSideEncryptionByDefault") or {}
        if default.get("SSEAlgorithm") != settings.s3_server_side_encryption:
            continue
        if settings.s3_server_side_encryption != "aws:kms" or not settings.s3_kms_key_id:
            return True
        if default.get("KMSMasterKeyID") == settings.s3_kms_key_id:
            return True
    return False


def _is_required_lifecycle_rule(settings: Settings, rule: dict) -> bool:
    prefix = (rule.get("Filter") or {}).get("Prefix", rule.get("Prefix"))
    expiration = rule.get("Expiration") or {}
    return (
        rule.get("Status") == "Enabled"
        and prefix == "workspaces/"
        and expiration.get("Days") == settings.s3_retention_days
    )


def _denies_insecure_transport(policy: dict) -> bool:
    statements = policy.get("Statement") or []
    if isinstance(statements, dict):
        statements = [statements]
    for statement in statements:
        condition = statement.get("Condition") or {}
        secure_transport = (condition.get("Bool") or {}).get("aws:SecureTransport")
        principal = statement.get("Principal")
        actions = statement.get("Action") or []
        if isinstance(actions, str):
            actions = [actions]
        applies_to_all = principal == "*" or (
            isinstance(principal, dict) and principal.get("AWS") == "*"
        )
        if (
            statement.get("Effect") == "Deny"
            and applies_to_all
            and any(action in {"*", "s3:*"} for action in actions)
            and str(secure_transport).casefold() == "false"
        ):
            return True
    return False


def _lifecycle_rule(settings: Settings) -> dict:
    return {
        "ID": "expire-workspace-evidence",
        "Status": "Enabled",
        "Filter": {"Prefix": "workspaces/"},
        "Expiration": {"Days": settings.s3_retention_days},
        "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
    }


def _is_missing_bucket(exc: ClientError) -> bool:
    error = exc.response.get("Error") or {}
    status_code = (exc.response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    return error.get("Code") in {"404", "NoSuchBucket", "NotFound"} or status_code == 404


def _evidence_key(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    filename: str,
) -> str:
    return (
        f"workspaces/{workspace_id}/projects/{project_id}/sources/{source_id}/{filename}"
    )


def _require_evidence_scope(
    key: str,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
) -> None:
    expected_prefix = _evidence_key(workspace_id, project_id, source_id, "")
    path = PurePosixPath(key)
    if not key.startswith(expected_prefix) or len(path.parts) != 7 or path.name != _safe_filename(
        path.name
    ):
        raise ObjectStorageError("Stored evidence object is outside the authorized scope.")


def _local_path(settings: Settings, key: str) -> Path:
    base_path = Path(settings.local_object_storage_path).resolve()
    destination = (base_path / key).resolve()
    if not destination.is_relative_to(base_path):
        raise ObjectStorageError("Stored evidence object is outside the local storage root.")
    return destination


def _safe_filename(filename: str) -> str:
    try:
        return sanitize_filename(filename)
    except SecurityValidationError:
        raise ObjectStorageError("Evidence filename is invalid.") from None


def _safe_content_type(content_type: str) -> str:
    value = content_type.strip().lower()
    if (
        not value
        or len(value) > 255
        or not _CONTENT_TYPE_PATTERN.fullmatch(value)
        or any(character in value for character in "\r\n\0")
    ):
        raise ObjectStorageError("Evidence content type is invalid.")
    return value


def _content_disposition(filename: str) -> str:
    return f'attachment; filename="{filename}"'
