"""Pure memory selection and conflict policy helpers."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.db.models import ProjectMemoryItem
from app.features.memory import security_policy


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
    working_memory_session_scope: str | None = None,
    allowed_data_classifications: set[str] | None = None,
) -> str | None:
    if not security_policy.memory_visible_to_clearance(
        item,
        allowed_data_classifications=allowed_data_classifications,
    ):
        return "memory_data_classification_not_allowed"
    if item.memory_type not in allowed_types:
        return "memory_type_not_allowed_for_workflow"
    if item.status == "proposed":
        return "pending_human_review"
    recall_reason = security_policy.memory_recall_exclusion_reason(
        item,
        now=now,
        working_memory_session_scope=working_memory_session_scope,
        allowed_data_classifications=allowed_data_classifications,
    )
    if recall_reason is not None:
        return recall_reason
    return None


def excluded(item: ProjectMemoryItem, reason: str) -> dict[str, Any]:
    return {
        "id": item.id,
        "memory_type": item.memory_type,
        "status": item.status,
        "title": "Restricted memory"
        if reason == "memory_data_classification_not_allowed"
        else item.title,
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
