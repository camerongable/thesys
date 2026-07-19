"""Encrypted project-local identifier tokenization and owner-authorized reversal."""

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_workspace_owner
from app.core.config import Settings
from app.db.models import PiiTokenMapping
from app.security.encryption import (
    EncryptedValue,
    EnvelopeEncryptionError,
    build_envelope_encryption_service,
)
from app.services import governance_service, project_service, retention_service
from app.services.data_protection_service import SanitizedText, data_protection_service

_TOKEN_ENTITY_TYPES = frozenset({"EMAIL", "PERSON", "PHONE_NUMBER"})
_TOKEN_PATTERN = re.compile(r"^<([A-Z_]+)_(\d{3})>$")


class PseudonymizationError(RuntimeError):
    pass


def create_searchable_copy(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    text: str,
) -> SanitizedText:
    """Tokenize reversible identifiers with a project-local encrypted mapping."""
    project_service.get_project(db, auth, project_id)
    mappings = list(
        db.scalars(
            select(PiiTokenMapping).where(
                PiiTokenMapping.workspace_id == auth.workspace_id,
                PiiTokenMapping.project_id == project_id,
            )
        )
    )
    encryption = build_envelope_encryption_service(settings)
    known = {
        (
            mapping.entity_type,
            _normalized(
                _decrypt_mapping(encryption, db, auth.workspace_id, project_id, mapping)
            ),
        ): mapping.token
        for mapping in mappings
    }
    next_ordinals = _next_ordinals(mappings)
    detections = data_protection_service.detect_pii(text)
    replacements: dict[tuple[int, int], str] = {}
    for detection in detections:
        value = text[detection.start : detection.end]
        if detection.entity_type not in _TOKEN_ENTITY_TYPES:
            replacements[(detection.start, detection.end)] = "[REDACTED_SECRET]"
            continue
        mapping_key = (detection.entity_type, _normalized(value))
        token = known.get(mapping_key)
        if token is None:
            ordinal = next_ordinals.get(detection.entity_type, 0) + 1
            next_ordinals[detection.entity_type] = ordinal
            token = f"<{detection.entity_type}_{ordinal:03d}>"
            encrypted = encryption.encrypt(
                db,
                workspace_id=auth.workspace_id,
                plaintext=value,
                purpose=_mapping_purpose(project_id),
            )
            db.add(
                PiiTokenMapping(
                    workspace_id=auth.workspace_id,
                    project_id=project_id,
                    token=token,
                    entity_type=detection.entity_type,
                    encrypted_value_ciphertext=encrypted.ciphertext,
                    encrypted_value_nonce=encrypted.nonce,
                    encrypted_value_key_version=encrypted.key_version,
                    algorithm=encrypted.algorithm,
                    retention_expires_at=retention_service.expires_at(
                        settings,
                        retention_service.RetentionAsset.PII_TOKEN_MAP,
                    ),
                    created_by=auth.user_id,
                )
            )
            known[mapping_key] = token
        replacements[(detection.start, detection.end)] = token
    sanitized = text
    for detection in reversed(detections):
        replacement = replacements[(detection.start, detection.end)]
        sanitized = sanitized[: detection.start] + replacement + sanitized[detection.end :]
    return SanitizedText(
        text=sanitized,
        data_classification=data_protection_service.classify_text(text),
        pii_status="redacted" if detections else "none_detected",
        pii_entity_types=tuple(sorted({detection.entity_type for detection in detections})),
    )


def reidentify_token(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    token: str,
) -> str:
    """Return one encrypted identifier only after project scope and owner authorization."""
    project_service.get_project(db, auth, project_id)
    if not data_protection_service.authorize_reidentification(auth):
        require_workspace_owner(auth)
    mapping = db.scalar(
        select(PiiTokenMapping).where(
            PiiTokenMapping.workspace_id == auth.workspace_id,
            PiiTokenMapping.project_id == project_id,
            PiiTokenMapping.token == token,
        )
    )
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PII token mapping not found.",
        )
    plaintext = _decrypt_mapping(
        build_envelope_encryption_service(settings),
        db,
        auth.workspace_id,
        project_id,
        mapping,
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="pii_reidentification_authorized",
        actor_type="user",
        project_id=project_id,
        entity_type="pii_token_mapping",
        entity_id=mapping.id,
        risk_level="high",
        summary="Authorized a project-local PII reidentification.",
        metadata={"entity_type": mapping.entity_type},
    )
    db.commit()
    return plaintext


def _decrypt_mapping(
    encryption,
    db: Session,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    mapping: PiiTokenMapping,
) -> str:
    try:
        return encryption.decrypt(
            db,
            workspace_id=workspace_id,
            encrypted=EncryptedValue(
                ciphertext=mapping.encrypted_value_ciphertext,
                nonce=mapping.encrypted_value_nonce,
                key_version=mapping.encrypted_value_key_version,
                algorithm=mapping.algorithm,
            ),
            purpose=_mapping_purpose(project_id),
        )
    except EnvelopeEncryptionError:
        raise PseudonymizationError("PII token mapping is unavailable.") from None


def _next_ordinals(mappings: list[PiiTokenMapping]) -> dict[str, int]:
    ordinals: dict[str, int] = {}
    for mapping in mappings:
        match = _TOKEN_PATTERN.fullmatch(mapping.token)
        if match:
            entity_type, value = match.groups()
            ordinals[entity_type] = max(ordinals.get(entity_type, 0), int(value))
    return ordinals


def _mapping_purpose(project_id: uuid.UUID) -> str:
    return f"pii_token_map:{project_id}"


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()
