"""Read-only memory serialization helpers for Inspect and explanation surfaces."""

from typing import Any

from app.schemas.memory import ProjectMemoryItemRead


def serialize_memory_item(item: Any) -> dict[str, Any]:
    """Serialize a memory ORM row or row-like object with the public schema shape."""

    return ProjectMemoryItemRead.model_validate(item).model_dump(mode="json")


def inspect_payload(
    *,
    workflow_type: str,
    selection: Any,
    proposed: list[Any],
) -> dict[str, Any]:
    """Build the hidden Inspect payload for selected/proposed/excluded memory."""

    return {
        "workflow_type": workflow_type,
        "selected_memory": [serialize_memory_item(item) for item in selection.selected],
        "excluded_memory": selection.excluded,
        "proposed_memory": [serialize_memory_item(item) for item in proposed],
        "conflicts": selection.conflicts,
        "policy": selection.policy,
    }


def explanation_payload(item: Any) -> dict[str, Any]:
    """Build an inspectable explanation of why a memory item exists."""

    provenance = item.provenance_metadata or {}
    source = provenance.get("source") or item.source_entity_type or item.entity_type or "unknown"
    explanation = (
        f"{item.title} is {item.memory_type} memory with {item.write_policy} write policy. "
        f"It came from {source} and is currently {item.status}."
    )
    return {
        "memory_item": serialize_memory_item(item),
        "explanation": explanation,
        "provenance": provenance,
    }
