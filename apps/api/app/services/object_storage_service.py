from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.security.secrets import SecretName, SecretProviderError, resolve_secret


class ObjectStorageError(RuntimeError):
    pass


def put_object(
    settings: Settings,
    *,
    key: str,
    body: bytes,
    content_type: str,
) -> str:
    if settings.object_storage_mode == "s3":
        return _put_s3_object(settings, key=key, body=body, content_type=content_type)
    return _put_local_object(settings, key=key, body=body)


def _put_s3_object(
    settings: Settings,
    *,
    key: str,
    body: bytes,
    content_type: str,
) -> str:
    try:
        access_key_id = resolve_secret(settings, SecretName.S3_ACCESS_KEY_ID)
        secret_access_key = resolve_secret(settings, SecretName.S3_SECRET_ACCESS_KEY)
    except SecretProviderError:
        raise ObjectStorageError("Object storage credentials are unavailable.") from None
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)

    try:
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
    except ClientError as exc:
        raise ObjectStorageError(f"Could not store object {key}.") from exc
    return key


def _put_local_object(settings: Settings, *, key: str, body: bytes) -> str:
    base_path = Path(settings.local_object_storage_path)
    destination = base_path / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
    return key
