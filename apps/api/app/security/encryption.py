"""AES-GCM envelope encryption for restricted reversible workspace data."""

import base64
import binascii
import os
import re
import uuid
from typing import Literal, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import WorkspaceDataKey
from app.security.secrets import SecretProvider, SecretProviderError, build_secret_provider

ALGORITHM = "AES-256-GCM"
NONCE_BYTES = 12
KEY_BYTES = 32
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SECRET_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_PURPOSE_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class EncryptedValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    ciphertext: str
    nonce: str
    key_version: str
    algorithm: Literal["AES-256-GCM"] = ALGORITHM


class KeyEncryptionKeyProvider(Protocol):
    @property
    def current_version(self) -> str: ...

    def get_key(self, version: str) -> bytes: ...


class EnvelopeEncryptionError(RuntimeError):
    """Restricted data could not be encrypted or authenticated."""


class SecretBackedKeyEncryptionKeyProvider:
    """Resolve versioned wrapping keys through the configured secret backend."""

    def __init__(
        self,
        secret_provider: SecretProvider,
        *,
        current_version: str,
        secret_name_prefix: str = "THESYS_ENCRYPTION_KEK",
    ) -> None:
        self._secret_provider = secret_provider
        self._current_version = _validated_version(current_version)
        self._secret_name_prefix = secret_name_prefix.rstrip("_")
        if not _SECRET_PREFIX_PATTERN.fullmatch(self._secret_name_prefix):
            raise EnvelopeEncryptionError("Encryption key secret prefix is invalid.")

    @property
    def current_version(self) -> str:
        return self._current_version

    def get_key(self, version: str) -> bytes:
        safe_version = _validated_version(version)
        try:
            encoded = self._secret_provider.get_secret(
                f"{self._secret_name_prefix}_{safe_version.upper()}"
            )
            key = base64.b64decode(encoded, validate=True)
        except (SecretProviderError, binascii.Error, ValueError):
            raise EnvelopeEncryptionError("Key encryption material is unavailable.") from None
        if len(key) != KEY_BYTES:
            raise EnvelopeEncryptionError("Key encryption material is invalid.")
        return key

    def __repr__(self) -> str:
        return "SecretBackedKeyEncryptionKeyProvider()"


class EnvelopeEncryptionService:
    """Encrypt values with a workspace DEK that is itself encrypted at rest."""

    def __init__(self, key_provider: KeyEncryptionKeyProvider) -> None:
        self._key_provider = key_provider

    def encrypt(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        plaintext: str,
        purpose: str,
    ) -> EncryptedValue:
        safe_purpose = _validated_purpose(purpose)
        try:
            key_record, dek = self._workspace_dek(db, workspace_id)
            nonce = os.urandom(NONCE_BYTES)
            ciphertext = AESGCM(dek).encrypt(
                nonce,
                plaintext.encode("utf-8"),
                _value_aad(workspace_id, key_record.key_version, safe_purpose),
            )
        except EnvelopeEncryptionError:
            raise
        except Exception:
            raise EnvelopeEncryptionError("Restricted value encryption failed.") from None
        return EncryptedValue(
            ciphertext=_encode(ciphertext),
            nonce=_encode(nonce),
            key_version=key_record.key_version,
        )

    def decrypt(
        self,
        db: Session,
        *,
        workspace_id: uuid.UUID,
        encrypted: EncryptedValue,
        purpose: str,
    ) -> str:
        safe_purpose = _validated_purpose(purpose)
        try:
            key_record = db.scalar(
                select(WorkspaceDataKey).where(
                    WorkspaceDataKey.workspace_id == workspace_id,
                    WorkspaceDataKey.key_version == encrypted.key_version,
                )
            )
            if key_record is None or encrypted.algorithm != ALGORITHM:
                raise EnvelopeEncryptionError("Restricted value decryption failed.")
            dek = self._unwrap_dek(key_record)
            plaintext = AESGCM(dek).decrypt(
                _decode(encrypted.nonce),
                _decode(encrypted.ciphertext),
                _value_aad(workspace_id, encrypted.key_version, safe_purpose),
            )
            return plaintext.decode("utf-8")
        except EnvelopeEncryptionError:
            raise
        except (InvalidTag, UnicodeDecodeError, binascii.Error, ValueError):
            raise EnvelopeEncryptionError("Restricted value decryption failed.") from None

    def rewrap_workspace_key(self, db: Session, *, workspace_id: uuid.UUID) -> None:
        key_record = db.scalar(
            select(WorkspaceDataKey).where(WorkspaceDataKey.workspace_id == workspace_id)
        )
        if key_record is None:
            raise EnvelopeEncryptionError("Workspace encryption key is unavailable.")
        if key_record.wrapping_key_version == self._key_provider.current_version:
            return
        dek = self._unwrap_dek(key_record)
        ciphertext, nonce = self._wrap_dek(
            workspace_id,
            key_record.key_version,
            dek,
            self._key_provider.current_version,
        )
        key_record.wrapped_dek_ciphertext = ciphertext
        key_record.wrapped_dek_nonce = nonce
        key_record.wrapping_key_version = self._key_provider.current_version
        db.flush()

    def _workspace_dek(
        self,
        db: Session,
        workspace_id: uuid.UUID,
    ) -> tuple[WorkspaceDataKey, bytes]:
        key_record = db.scalar(
            select(WorkspaceDataKey).where(WorkspaceDataKey.workspace_id == workspace_id)
        )
        if key_record is not None:
            return key_record, self._unwrap_dek(key_record)

        dek = AESGCM.generate_key(bit_length=256)
        key_version = f"dek-{uuid.uuid4().hex}"
        ciphertext, nonce = self._wrap_dek(
            workspace_id,
            key_version,
            dek,
            self._key_provider.current_version,
        )
        key_record = WorkspaceDataKey(
            workspace_id=workspace_id,
            key_version=key_version,
            wrapping_key_version=self._key_provider.current_version,
            wrapped_dek_ciphertext=ciphertext,
            wrapped_dek_nonce=nonce,
            algorithm=ALGORITHM,
        )
        db.add(key_record)
        db.flush()
        return key_record, dek

    def _wrap_dek(
        self,
        workspace_id: uuid.UUID,
        key_version: str,
        dek: bytes,
        wrapping_key_version: str,
    ) -> tuple[str, str]:
        wrapping_key = self._key_provider.get_key(wrapping_key_version)
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(wrapping_key).encrypt(
            nonce,
            dek,
            _dek_aad(workspace_id, key_version, wrapping_key_version),
        )
        return _encode(ciphertext), _encode(nonce)

    def _unwrap_dek(self, key_record: WorkspaceDataKey) -> bytes:
        try:
            wrapping_key = self._key_provider.get_key(key_record.wrapping_key_version)
            return AESGCM(wrapping_key).decrypt(
                _decode(key_record.wrapped_dek_nonce),
                _decode(key_record.wrapped_dek_ciphertext),
                _dek_aad(
                    key_record.workspace_id,
                    key_record.key_version,
                    key_record.wrapping_key_version,
                ),
            )
        except EnvelopeEncryptionError:
            raise
        except (InvalidTag, binascii.Error, ValueError):
            raise EnvelopeEncryptionError("Workspace encryption key is invalid.") from None


def build_envelope_encryption_service(settings: Settings) -> EnvelopeEncryptionService:
    key_provider = SecretBackedKeyEncryptionKeyProvider(
        build_secret_provider(settings),
        current_version=settings.encryption_key_current_version,
        secret_name_prefix=settings.encryption_key_secret_prefix,
    )
    return EnvelopeEncryptionService(key_provider)


def _validated_version(value: str) -> str:
    if not _VERSION_PATTERN.fullmatch(value):
        raise EnvelopeEncryptionError("Encryption key version is invalid.")
    return value


def _validated_purpose(value: str) -> str:
    if not _PURPOSE_PATTERN.fullmatch(value):
        raise EnvelopeEncryptionError("Encryption purpose is invalid.")
    return value


def _encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def _dek_aad(
    workspace_id: uuid.UUID,
    key_version: str,
    wrapping_key_version: str,
) -> bytes:
    return (
        f"thesys:workspace-dek:v1:{workspace_id}:{key_version}:{wrapping_key_version}"
    ).encode("ascii")


def _value_aad(workspace_id: uuid.UUID, key_version: str, purpose: str) -> bytes:
    return f"thesys:restricted:v1:{workspace_id}:{key_version}:{purpose}".encode("ascii")
