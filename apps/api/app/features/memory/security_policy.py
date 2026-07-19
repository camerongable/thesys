"""Secure provenance and recall policy for durable project memory."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

SECURE_MEMORY_POLICY_VERSION = "secure-memory:v1"
MINIMUM_RECALL_TRUST_SCORE = 0.5
_EVIDENCE_ENTITY_TYPES = {"evidence_source", "evidence_chunk", "retrieved_evidence"}
_PROCEDURAL_SOURCE_TYPES = {"code", "config"}
_ORIGINS = {"user", "agent", "derived", "system"}
_SECURITY_STATUSES = {"approved", "quarantined", "blocked"}


def secure_memory_metadata(
    metadata: dict[str, Any] | None,
    *,
    content: dict[str, Any],
    summary: str,
    source_entity_type: str | None,
    source_entity_id: object | None,
    write_policy: str,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    """Normalize the durable metadata required for secure memory recall."""
    normalized = dict(metadata or {})
    origin = str(normalized.get("origin") or _default_origin(source_entity_type, write_policy))
    if origin not in _ORIGINS:
        origin = "agent"
    security_status = str(normalized.get("security_status") or "approved")
    if security_status not in _SECURITY_STATUSES:
        security_status = "quarantined"
    trust_score = _bounded_score(normalized.get("trust_score"), default=1.0)
    source_ids = _source_ids(normalized.get("source_ids"), source_entity_type, source_entity_id)
    conflicts = _string_list(normalized.get("contradicts_memory_ids"))
    now = datetime.now(UTC).isoformat()
    trusted_projection = bool(normalized.get("trusted_projection")) and origin == "derived"
    normalized.update(
        {
            "policy_version": SECURE_MEMORY_POLICY_VERSION,
            "origin": origin,
            "security_status": security_status,
            "trust_score": trust_score,
            "content_hash": _content_hash(content, summary),
            "source_ids": source_ids,
            "contradicts_memory_ids": conflicts,
            "last_verified_at": normalized.get("last_verified_at") or now,
            "expires_at": _expiry_metadata(expires_at),
            "requires_human_approval": write_policy == "approval_required" or origin == "agent",
            "trusted_projection": trusted_projection or origin == "user",
        }
    )
    return normalized


def requires_memory_proposal(
    metadata: dict[str, Any],
    *,
    source_entity_type: str | None,
    status_value: str,
) -> bool:
    """Prevent retrieved or untrusted content from becoming active memory directly."""
    if status_value != "active":
        return False
    if metadata.get("security_status") != "approved":
        return True
    if source_entity_type in _EVIDENCE_ENTITY_TYPES:
        return True
    if metadata.get("origin") == "agent":
        return True
    return bool(
        metadata.get("requires_human_approval")
        and not (metadata.get("approved_at") or metadata.get("trusted_projection"))
    )


def procedural_memory_write_allowed(
    metadata: dict[str, Any],
    *,
    source_entity_type: str | None,
    source_entity_id: object | None,
    write_policy: str,
) -> bool:
    """Only permit versioned code/config procedures in durable memory."""
    return (
        metadata.get("origin") == "system"
        and source_entity_type in _PROCEDURAL_SOURCE_TYPES
        and source_entity_id is not None
        and write_policy == "derived_read_only"
        and isinstance(metadata.get("procedure_version"), str)
        and bool(metadata["procedure_version"].strip())
    )


def memory_recall_exclusion_reason(item: Any, *, now: datetime) -> str | None:
    """Return an explainable denial reason for a durable-memory recall candidate."""
    if item.status != "active":
        return f"status_{item.status}"
    if item.expires_at is not None and _as_utc(item.expires_at) <= _as_utc(now):
        return "expired"
    metadata = item.provenance_metadata or {}
    if metadata.get("policy_version") != SECURE_MEMORY_POLICY_VERSION:
        return "missing_secure_memory_metadata"
    if metadata.get("security_status") != "approved":
        return "memory_security_status_not_approved"
    if _bounded_score(metadata.get("trust_score"), default=0.0) < MINIMUM_RECALL_TRUST_SCORE:
        return "memory_trust_below_threshold"
    if metadata.get("requires_human_approval") and not (
        metadata.get("approved_at") or metadata.get("trusted_projection")
    ):
        return "memory_approval_required"
    return None


def _default_origin(source_entity_type: str | None, write_policy: str) -> str:
    if source_entity_type in _EVIDENCE_ENTITY_TYPES:
        return "agent"
    return "user"


def _content_hash(content: dict[str, Any], summary: str) -> str:
    payload = json.dumps(
        {"content": content, "summary": summary},
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_ids(value: object, source_type: str | None, source_id: object | None) -> list[str]:
    values = _string_list(value)
    if source_type in _EVIDENCE_ENTITY_TYPES and source_id is not None:
        values.append(str(source_id))
    return sorted(set(values))


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _bounded_score(value: object, *, default: float) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _expiry_metadata(value: datetime | None) -> str | None:
    return _as_utc(value).isoformat() if value is not None else None
