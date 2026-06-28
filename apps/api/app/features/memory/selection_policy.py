"""Pure memory selection and conflict policy helpers."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.db.models import ProjectMemoryItem


@dataclass(frozen=True)
class MemorySelection:
    """Inspectable memory-selection result for context compilation and UI review."""

    selected: list[ProjectMemoryItem]
    excluded: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    policy: dict[str, Any]


class MemoryConflictMembershipError(ValueError):
    """Raised when a memory item is not in the requested conflict group."""


def memory_exclusion_reason(
    item: ProjectMemoryItem,
    *,
    allowed_types: set[str],
    include_stale_history: bool,
    now: datetime,
) -> str | None:
    if item.memory_type not in allowed_types:
        return "memory_type_not_allowed_for_workflow"
    if item.expires_at is not None and item.expires_at <= now:
        return "expired"
    if item.status == "active":
        return None
    if item.status == "stale" and include_stale_history:
        return None
    if item.status == "proposed":
        return "pending_human_review"
    return f"status_{item.status}"


def excluded(item: ProjectMemoryItem, reason: str) -> dict[str, Any]:
    return {
        "id": item.id,
        "memory_type": item.memory_type,
        "status": item.status,
        "title": item.title,
        "reason": reason,
    }


def conflict_key(item: ProjectMemoryItem) -> str:
    entity = str(item.entity_id) if item.entity_id else normalize_text(item.title)
    return f"{item.memory_type}:{item.entity_type or 'title'}:{entity}"


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def ensure_conflict_member(item: ProjectMemoryItem, conflict_group_id: str) -> None:
    metadata = item.provenance_metadata or {}
    if metadata.get("conflict_group_id") != conflict_group_id:
        raise MemoryConflictMembershipError(
            "Memory item is not part of the requested conflict group."
        )
