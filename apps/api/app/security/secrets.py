"""Environment-aware access to application secrets.

Callers use the closed ``SecretName`` registry. Provider objects are internal
infrastructure and are never registered as agent or MCP tools.
"""

import base64
import os
from collections.abc import Callable, Mapping
from enum import StrEnum
from functools import lru_cache
from typing import Any, Protocol

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings


class SecretProvider(Protocol):
    def get_secret(self, name: str) -> str: ...


class SecretProviderError(RuntimeError):
    """A secret backend could not safely satisfy a request."""


class SecretNotFoundError(SecretProviderError):
    """A requested secret does not exist or has an empty value."""


class SecretName(StrEnum):
    AUTH_JWT_SECRET = "AUTH_JWT_SECRET"
    LITELLM_API_KEY = "LITELLM_API_KEY"
    OPENAI_API_KEY = "OPENAI_API_KEY"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
    GEMINI_API_KEY = "GEMINI_API_KEY"
    S3_ACCESS_KEY_ID = "S3_ACCESS_KEY_ID"
    S3_SECRET_ACCESS_KEY = "S3_SECRET_ACCESS_KEY"
    TAVILY_API_KEY = "TAVILY_API_KEY"
    LANGSMITH_API_KEY = "LANGSMITH_API_KEY"


_SETTING_FIELDS: dict[SecretName, str] = {
    SecretName.AUTH_JWT_SECRET: "auth_jwt_secret",
    SecretName.LITELLM_API_KEY: "litellm_api_key",
    SecretName.OPENAI_API_KEY: "openai_api_key",
    SecretName.ANTHROPIC_API_KEY: "anthropic_api_key",
    SecretName.GEMINI_API_KEY: "gemini_api_key",
    SecretName.S3_ACCESS_KEY_ID: "s3_access_key_id",
    SecretName.S3_SECRET_ACCESS_KEY: "s3_secret_access_key",
    SecretName.TAVILY_API_KEY: "tavily_api_key",
    SecretName.LANGSMITH_API_KEY: "langsmith_api_key",
}


class EnvironmentSecretProvider:
    """Read local-development secrets without exposing values in diagnostics."""

    def __init__(
        self,
        environment: Mapping[str, str] | None = None,
        *,
        fallbacks: Mapping[str, str | None] | None = None,
    ) -> None:
        self._environment = environment if environment is not None else os.environ
        self._fallbacks = fallbacks or {}

    def get_secret(self, name: str) -> str:
        value = self._environment.get(name) or self._fallbacks.get(name)
        if not value or not value.strip():
            raise SecretNotFoundError("The requested local secret is not configured.")
        return value

    def __repr__(self) -> str:
        return "EnvironmentSecretProvider()"


class VaultSecretProvider:
    """Read one-value secrets from a Vault KV v2 mount."""

    def __init__(
        self,
        *,
        address: str,
        token: str,
        mount_point: str = "secret",
        path_prefix: str = "thesys",
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        if not token.strip():
            raise SecretProviderError("Vault workload authentication is not configured.")
        self._address = address.rstrip("/")
        self._mount_point = _safe_path(mount_point)
        self._path_prefix = _safe_path(path_prefix)
        self._token = token
        self._client_factory = client_factory

    def get_secret(self, name: str) -> str:
        path_name = _safe_path(name)
        path = f"/v1/{self._mount_point}/data/{self._path_prefix}/{path_name}"
        try:
            if self._client_factory is None:
                with httpx.Client(
                    base_url=self._address,
                    headers={"X-Vault-Token": self._token},
                    timeout=5.0,
                ) as client:
                    response = client.get(path)
            else:
                with self._client_factory() as client:
                    response = client.get(path, headers={"X-Vault-Token": self._token})
            if response.status_code == 404:
                raise SecretNotFoundError("The requested Vault secret is not configured.")
            response.raise_for_status()
            value = response.json()["data"]["data"]["value"]
        except SecretNotFoundError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise SecretProviderError("Vault secret retrieval failed.") from None
        if not isinstance(value, str) or not value.strip():
            raise SecretNotFoundError("The requested Vault secret is not configured.")
        return value

    def __repr__(self) -> str:
        return "VaultSecretProvider()"


class CloudSecretManagerProvider:
    """Read secrets from AWS Secrets Manager using workload credentials."""

    def __init__(
        self,
        *,
        region_name: str | None = None,
        secret_id_prefix: str = "thesys/",
        client: Any | None = None,
    ) -> None:
        self._secret_id_prefix = secret_id_prefix
        self._client = client if client is not None else _cloud_secret_client(region_name)

    def get_secret(self, name: str) -> str:
        try:
            response = self._client.get_secret_value(SecretId=f"{self._secret_id_prefix}{name}")
            value = response.get("SecretString")
            if value is None and response.get("SecretBinary") is not None:
                binary_value = response["SecretBinary"]
                value = (
                    bytes(binary_value).decode("utf-8")
                    if isinstance(binary_value, bytes | bytearray)
                    else base64.b64decode(binary_value).decode("utf-8")
                )
        except self._client.exceptions.ResourceNotFoundException:
            raise SecretNotFoundError("The requested cloud secret is not configured.") from None
        except (BotoCoreError, ClientError, UnicodeDecodeError, ValueError):
            raise SecretProviderError("Cloud secret retrieval failed.") from None
        if not isinstance(value, str) or not value.strip():
            raise SecretNotFoundError("The requested cloud secret is not configured.")
        return value

    def __repr__(self) -> str:
        return "CloudSecretManagerProvider()"


def build_secret_provider(
    settings: Settings,
    *,
    environment: Mapping[str, str] | None = None,
    cloud_client: Any | None = None,
    vault_client_factory: Callable[[], httpx.Client] | None = None,
) -> SecretProvider:
    source = environment if environment is not None else os.environ
    if settings.secret_provider == "environment":
        fallbacks = {
            name.value: getattr(settings, field_name)
            for name, field_name in _SETTING_FIELDS.items()
        }
        return EnvironmentSecretProvider(source, fallbacks=fallbacks)
    if settings.secret_provider == "vault":
        return VaultSecretProvider(
            address=settings.vault_address or "",
            token=source.get("VAULT_TOKEN", ""),
            mount_point=settings.vault_mount_point,
            path_prefix=settings.vault_secret_path_prefix,
            client_factory=vault_client_factory,
        )
    return CloudSecretManagerProvider(
        region_name=settings.cloud_secret_region,
        secret_id_prefix=settings.cloud_secret_id_prefix,
        client=cloud_client,
    )


def resolve_secret(
    settings: Settings,
    name: SecretName,
    *,
    required: bool = True,
) -> str | None:
    try:
        return build_secret_provider(settings).get_secret(name.value)
    except SecretNotFoundError:
        if required:
            raise
        return None


def has_secret(settings: Settings, name: SecretName) -> bool:
    return resolve_secret(settings, name, required=False) is not None


def _safe_path(value: str) -> str:
    cleaned = value.strip().strip("/")
    if not cleaned or any(part in {"", ".", ".."} for part in cleaned.split("/")):
        raise SecretProviderError("Secret provider path configuration is invalid.")
    if not all(character.isalnum() or character in {"-", "_", "/"} for character in cleaned):
        raise SecretProviderError("Secret provider path configuration is invalid.")
    return cleaned


@lru_cache(maxsize=8)
def _cloud_secret_client(region_name: str | None) -> Any:
    return boto3.client("secretsmanager", region_name=region_name)
