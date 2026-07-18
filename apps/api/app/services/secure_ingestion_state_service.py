"""Validated lifecycle metadata for secure evidence ingestion."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class SecureIngestionState(StrEnum):
    UPLOADED = "uploaded"
    MALWARE_SCANNING = "malware_scanning"
    EXTRACTION_PENDING = "extraction_pending"
    EXTRACTED = "extracted"
    CLASSIFICATION_PENDING = "classification_pending"
    CLASSIFIED = "classified"
    PII_REVIEW_PENDING = "pii_review_pending"
    APPROVED_FOR_EMBEDDING = "approved_for_embedding"
    EMBEDDED = "embedded"
    RETRIEVABLE = "retrievable"
    QUARANTINED = "quarantined"
    FAILED = "failed"


_ALLOWED_TRANSITIONS = {
    SecureIngestionState.UPLOADED: {
        SecureIngestionState.MALWARE_SCANNING,
        SecureIngestionState.EXTRACTION_PENDING,
        SecureIngestionState.FAILED,
    },
    SecureIngestionState.MALWARE_SCANNING: {
        SecureIngestionState.EXTRACTION_PENDING,
        SecureIngestionState.QUARANTINED,
        SecureIngestionState.FAILED,
    },
    SecureIngestionState.EXTRACTION_PENDING: {
        SecureIngestionState.EXTRACTED,
        SecureIngestionState.FAILED,
    },
    SecureIngestionState.EXTRACTED: {
        SecureIngestionState.CLASSIFICATION_PENDING,
        SecureIngestionState.FAILED,
    },
    SecureIngestionState.CLASSIFICATION_PENDING: {
        SecureIngestionState.CLASSIFIED,
        SecureIngestionState.FAILED,
    },
    SecureIngestionState.CLASSIFIED: {
        SecureIngestionState.PII_REVIEW_PENDING,
        SecureIngestionState.APPROVED_FOR_EMBEDDING,
        SecureIngestionState.FAILED,
    },
    SecureIngestionState.PII_REVIEW_PENDING: {
        SecureIngestionState.APPROVED_FOR_EMBEDDING,
        SecureIngestionState.FAILED,
    },
    SecureIngestionState.APPROVED_FOR_EMBEDDING: {
        SecureIngestionState.EMBEDDED,
        SecureIngestionState.FAILED,
    },
    SecureIngestionState.EMBEDDED: {
        SecureIngestionState.RETRIEVABLE,
        SecureIngestionState.FAILED,
    },
    # Reprocessing a source is a new extraction attempt. Keep the complete
    # history rather than replacing the prior successful lifecycle.
    SecureIngestionState.RETRIEVABLE: {SecureIngestionState.EXTRACTION_PENDING},
    SecureIngestionState.QUARANTINED: set(),
    SecureIngestionState.FAILED: {SecureIngestionState.EXTRACTION_PENDING},
}


def initialize(source: Any) -> None:
    metadata = dict(source.source_metadata or {})
    if isinstance(metadata.get("ingestion"), dict):
        return
    metadata["ingestion"] = {
        "state": SecureIngestionState.UPLOADED.value,
        "history": [_history_entry(SecureIngestionState.UPLOADED)],
    }
    source.source_metadata = metadata


def transition(source: Any, state: SecureIngestionState) -> None:
    initialize(source)
    metadata = dict(source.source_metadata or {})
    ingestion = dict(metadata["ingestion"])
    current = SecureIngestionState(str(ingestion["state"]))
    if current is state:
        return
    if state not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid secure-ingestion transition: {current} -> {state}.")
    history = list(ingestion.get("history") or [])
    history.append(_history_entry(state))
    ingestion["state"] = state.value
    ingestion["history"] = history
    metadata["ingestion"] = ingestion
    source.source_metadata = metadata


def state(source: Any) -> SecureIngestionState:
    initialize(source)
    metadata = source.source_metadata or {}
    ingestion = metadata["ingestion"]
    return SecureIngestionState(str(ingestion["state"]))


def _history_entry(state: SecureIngestionState) -> dict[str, str]:
    return {"state": state.value, "at": datetime.now(UTC).isoformat()}
