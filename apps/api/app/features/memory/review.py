"""Pure payload shaping for human-reviewed memory proposals."""

import uuid
from datetime import datetime
from typing import Any, Literal

MemoryReviewStatus = Literal["approved", "rejected"]


def reviewed_memory_metadata(
    metadata: dict[str, Any] | None,
    *,
    status: MemoryReviewStatus,
    user_id: uuid.UUID,
    reviewed_at: datetime,
) -> dict[str, Any]:
    """Return provenance metadata for an approved or rejected memory proposal."""

    reviewed = dict(metadata or {})
    if status == "approved":
        reviewed["approved_by_user_id"] = str(user_id)
        reviewed["approved_at"] = reviewed_at.isoformat()
    else:
        reviewed["rejected_by_user_id"] = str(user_id)
        reviewed["rejected_at"] = reviewed_at.isoformat()
    return reviewed


def memory_review_audit_metadata(
    item: Any,
    *,
    status: MemoryReviewStatus,
) -> dict[str, Any]:
    """Return stable audit metadata for a memory proposal review event."""

    metadata = item.provenance_metadata or {}
    return {
        "memory_item_id": str(item.id),
        "memory_type": item.memory_type,
        "status": status,
        "proposal_kind": metadata.get("proposal_kind") or metadata.get("source"),
        "source_entity_type": item.source_entity_type,
        "source_entity_id": str(item.source_entity_id) if item.source_entity_id else None,
    }
