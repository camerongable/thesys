import base64

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Workspace, WorkspaceDataKey
from app.security.encryption import (
    EncryptedValue,
    EnvelopeEncryptionError,
    EnvelopeEncryptionService,
    SecretBackedKeyEncryptionKeyProvider,
    build_envelope_encryption_service,
)
from app.security.secrets import (
    CloudSecretManagerProvider,
    EnvironmentSecretProvider,
    SecretNotFoundError,
    VaultSecretProvider,
    build_secret_provider,
)


def test_secret_provider_policy_is_environment_specific() -> None:
    with pytest.raises(ValidationError, match="Local development"):
        Settings(environment="local", secret_provider="cloud")
    with pytest.raises(ValidationError, match="Hosted environments"):
        Settings(
            environment="production",
            auth_mode="api_key",
            database_url="postgresql+psycopg://thesys_api:secret@db.example/thesys",
        )
    with pytest.raises(ValidationError, match="VAULT_ADDRESS"):
        Settings(
            environment="production",
            auth_mode="api_key",
            secret_provider="vault",
            database_url="postgresql+psycopg://thesys_api:secret@db.example/thesys",
        )

    hosted = Settings(
        environment="production",
        auth_mode="api_key",
        secret_provider="cloud",
        llm_stub_mode="auto",
        litellm_api_key="hosted-environment-secret",
        database_url="postgresql+psycopg://thesys_api:secret@db.example/thesys",
        object_storage_mode="s3",
        s3_endpoint_url="https://s3.example.com",
        s3_verify_bucket_security=True,
    )
    assert hosted.secret_provider == "cloud"
    assert hosted.should_use_llm_stub is False
    assert hosted.litellm_api_key == ""


def test_invalid_configuration_hides_secret_inputs_from_errors() -> None:
    sentinel = "configuration-secret-sentinel"

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="local",
            secret_provider="cloud",
            litellm_api_key=sentinel,
        )

    assert sentinel not in str(exc_info.value)


def test_environment_provider_uses_local_settings_without_leaking_values() -> None:
    sentinel = "sk-local-sentinel-value"
    settings = Settings(litellm_api_key=sentinel)
    provider = build_secret_provider(settings, environment={})

    assert provider.get_secret("LITELLM_API_KEY") == sentinel
    assert sentinel not in repr(settings)
    assert sentinel not in repr(provider)
    with pytest.raises(SecretNotFoundError) as exc_info:
        provider.get_secret("TAVILY_API_KEY")
    assert sentinel not in str(exc_info.value)


def test_vault_provider_reads_kv_v2_without_exposing_token() -> None:
    token = "vault-sensitive-token"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/secret/data/thesys/LITELLM_API_KEY"
        assert request.headers["X-Vault-Token"] == token
        return httpx.Response(200, json={"data": {"data": {"value": "provider-value"}}})

    provider = VaultSecretProvider(
        address="https://vault.example.com",
        token=token,
        client_factory=lambda: httpx.Client(
            base_url="https://vault.example.com",
            transport=httpx.MockTransport(handler),
        ),
    )

    assert provider.get_secret("LITELLM_API_KEY") == "provider-value"
    assert token not in repr(provider)


def test_cloud_provider_uses_workload_client_and_generic_errors() -> None:
    class ResourceNotFoundException(Exception):
        pass

    class Exceptions:
        pass

    Exceptions.ResourceNotFoundException = ResourceNotFoundException

    class FakeClient:
        exceptions = Exceptions

        def get_secret_value(self, *, SecretId: str) -> dict[str, str | bytes]:
            if SecretId.endswith("MISSING"):
                raise ResourceNotFoundException("backend included an internal identifier")
            if SecretId.endswith("BINARY"):
                return {"SecretBinary": b"binary-provider-value"}
            assert SecretId == "thesys/LITELLM_API_KEY"
            return {"SecretString": "cloud-provider-value"}

    provider = CloudSecretManagerProvider(client=FakeClient())

    assert provider.get_secret("LITELLM_API_KEY") == "cloud-provider-value"
    assert provider.get_secret("BINARY") == "binary-provider-value"
    with pytest.raises(SecretNotFoundError, match="not configured") as exc_info:
        provider.get_secret("MISSING")
    assert "internal identifier" not in str(exc_info.value)


def test_envelope_encryption_round_trip_has_no_plaintext_at_rest(db_session: Session) -> None:
    workspace = Workspace(name="Encrypted Workspace")
    db_session.add(workspace)
    db_session.flush()
    service = _encryption_service({"v1": b"1" * 32})
    plaintext = "oauth-refresh-token-sensitive-value"

    encrypted = service.encrypt(
        db_session,
        workspace_id=workspace.id,
        plaintext=plaintext,
        purpose="oauth_refresh_token",
    )
    key_record = db_session.scalar(
        select(WorkspaceDataKey).where(WorkspaceDataKey.workspace_id == workspace.id)
    )

    assert key_record is not None
    assert encrypted.algorithm == "AES-256-GCM"
    assert encrypted.key_version == key_record.key_version
    assert plaintext not in encrypted.model_dump_json()
    assert plaintext not in key_record.wrapped_dek_ciphertext
    assert service.decrypt(
        db_session,
        workspace_id=workspace.id,
        encrypted=encrypted,
        purpose="oauth_refresh_token",
    ) == plaintext


def test_encryption_service_factory_uses_configured_secret_provider(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Workspace(name="Configured Encryption Workspace")
    db_session.add(workspace)
    db_session.flush()
    monkeypatch.setenv(
        "THESYS_ENCRYPTION_KEK_V1",
        base64.b64encode(b"5" * 32).decode("ascii"),
    )
    service = build_envelope_encryption_service(Settings())

    encrypted = service.encrypt(
        db_session,
        workspace_id=workspace.id,
        plaintext="configured-secret-value",
        purpose="provider_credentials",
    )

    assert service.decrypt(
        db_session,
        workspace_id=workspace.id,
        encrypted=encrypted,
        purpose="provider_credentials",
    ) == "configured-secret-value"


def test_envelope_encryption_authenticates_ciphertext_workspace_and_purpose(
    db_session: Session,
) -> None:
    workspace = Workspace(name="Workspace A")
    other_workspace = Workspace(name="Workspace B")
    db_session.add_all([workspace, other_workspace])
    db_session.flush()
    service = _encryption_service({"v1": b"2" * 32})
    encrypted = service.encrypt(
        db_session,
        workspace_id=workspace.id,
        plaintext="connector-credential",
        purpose="connector_credentials",
    )
    tampered_bytes = bytearray(base64.b64decode(encrypted.ciphertext))
    tampered_bytes[0] ^= 1
    tampered = EncryptedValue(
        **{
            **encrypted.model_dump(),
            "ciphertext": base64.b64encode(tampered_bytes).decode("ascii"),
        }
    )

    for candidate_workspace, purpose, candidate_value in (
        (workspace.id, "connector_credentials", tampered),
        (workspace.id, "oauth_refresh_token", encrypted),
        (other_workspace.id, "connector_credentials", encrypted),
    ):
        with pytest.raises(EnvelopeEncryptionError, match="decryption failed"):
            service.decrypt(
                db_session,
                workspace_id=candidate_workspace,
                encrypted=candidate_value,
                purpose=purpose,
            )


def test_workspace_dek_can_be_rewrapped_without_reencrypting_values(db_session: Session) -> None:
    workspace = Workspace(name="Rotating Workspace")
    db_session.add(workspace)
    db_session.flush()
    keys = {"v1": b"3" * 32, "v2": b"4" * 32}
    original_service = _encryption_service(keys, current_version="v1")
    encrypted = original_service.encrypt(
        db_session,
        workspace_id=workspace.id,
        plaintext="sensitive-integration-config",
        purpose="integration_config",
    )
    rotated_service = _encryption_service(keys, current_version="v2")

    rotated_service.rewrap_workspace_key(db_session, workspace_id=workspace.id)
    key_record = db_session.scalar(
        select(WorkspaceDataKey).where(WorkspaceDataKey.workspace_id == workspace.id)
    )

    assert key_record is not None and key_record.wrapping_key_version == "v2"
    assert rotated_service.decrypt(
        db_session,
        workspace_id=workspace.id,
        encrypted=encrypted,
        purpose="integration_config",
    ) == "sensitive-integration-config"


def _encryption_service(
    keys: dict[str, bytes],
    *,
    current_version: str = "v1",
) -> EnvelopeEncryptionService:
    environment = {
        f"THESYS_ENCRYPTION_KEK_{version.upper()}": base64.b64encode(key).decode("ascii")
        for version, key in keys.items()
    }
    provider = EnvironmentSecretProvider(environment)
    key_provider = SecretBackedKeyEncryptionKeyProvider(
        provider,
        current_version=current_version,
    )
    return EnvelopeEncryptionService(key_provider)
