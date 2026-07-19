"""Hash-chain helpers for tamper-evident workspace audit histories."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent


@dataclass(frozen=True)
class AuditChainVerificationResult:
    """Verification outcome for one workspace audit chain."""

    workspace_id: uuid.UUID
    event_count: int
    valid: bool
    error: str | None = None


def calculate_event_hash(event: AuditEvent, previous_event_hash: str | None) -> str:
    """Return the stable SHA-256 digest for an audit event and its predecessor."""
    payload = {
        "actor_identity": event.actor_identity,
        "actor_type": event.actor_type,
        "created_at": _timestamp_value(event.created_at),
        "entity_id": str(event.entity_id) if event.entity_id is not None else None,
        "entity_type": event.entity_type,
        "event_id": str(event.id),
        "event_metadata": event.event_metadata,
        "event_type": event.event_type,
        "policy_decision": event.policy_decision,
        "previous_event_hash": previous_event_hash,
        "project_id": str(event.project_id) if event.project_id is not None else None,
        "resource_identifier": event.resource_identifier,
        "risk_level": event.risk_level,
        "summary": event.summary,
        "user_id": str(event.user_id) if event.user_id is not None else None,
        "workspace_id": str(event.workspace_id),
    }
    encoded = json.dumps(
        payload,
        default=str,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_audit_chains(
    db: Session,
    *,
    workspace_id: uuid.UUID | None = None,
) -> list[AuditChainVerificationResult]:
    """Verify each requested workspace chain in chronological append order."""
    statement = select(AuditEvent).order_by(
        AuditEvent.workspace_id,
        AuditEvent.created_at,
        AuditEvent.id,
    )
    if workspace_id is not None:
        statement = statement.where(AuditEvent.workspace_id == workspace_id)

    results: list[AuditChainVerificationResult] = []
    current_workspace_id: uuid.UUID | None = None
    previous_event_hash: str | None = None
    event_count = 0
    error: str | None = None

    for event in db.scalars(statement):
        if event.workspace_id != current_workspace_id:
            if current_workspace_id is not None:
                results.append(
                    AuditChainVerificationResult(
                        workspace_id=current_workspace_id,
                        event_count=event_count,
                        valid=error is None,
                        error=error,
                    )
                )
            current_workspace_id = event.workspace_id
            previous_event_hash = None
            event_count = 0
            error = None

        event_count += 1
        if error is None:
            if event.event_hash is None:
                error = f"event {event.id} has no event hash"
            elif event.previous_event_hash != previous_event_hash:
                error = f"event {event.id} has an unexpected previous event hash"
            elif event.event_hash != calculate_event_hash(event, previous_event_hash):
                error = f"event {event.id} hash does not match its content"
        previous_event_hash = event.event_hash

    if current_workspace_id is not None:
        results.append(
            AuditChainVerificationResult(
                workspace_id=current_workspace_id,
                event_count=event_count,
                valid=error is None,
                error=error,
            )
        )
    return results


def _timestamp_value(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")
