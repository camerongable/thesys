"""Memory context-pack serialization helpers."""

import json
from typing import Any

from app.schemas.context import ContextItem, ContextProvenance

APPROX_CHARS_PER_TOKEN = 4


def context_item(
    item_id: str,
    item_type: str,
    title: str,
    content: str,
    *,
    source: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    citation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    untrusted: bool = False,
    priority: int = 100,
) -> ContextItem:
    return ContextItem(
        id=item_id,
        type=item_type,  # type: ignore[arg-type]
        title=title[:200],
        content=content,
        token_count=estimate_tokens(content),
        provenance=ContextProvenance(
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
            citation_id=citation_id,
            metadata=metadata or {},
        ),
        untrusted=untrusted,
        priority=priority,
    )


def memory_items(memory_selection: Any | None, *, base_priority: int) -> list[ContextItem]:
    items: list[ContextItem] = []
    for index, memory in enumerate(selected_memory(memory_selection)[:12]):
        memory_id = memory_value(memory, "id")
        memory_type = str(memory_value(memory, "memory_type") or "memory")
        status = str(memory_value(memory, "status") or "unknown")
        write_policy = str(memory_value(memory, "write_policy") or "unknown")
        provenance = memory_value(memory, "provenance_metadata") or {}
        content = {
            "title": memory_value(memory, "title"),
            "summary": memory_value(memory, "summary"),
            "memory_type": memory_type,
            "status": status,
            "write_policy": write_policy,
            "content": memory_value(memory, "content") or {},
        }
        items.append(
            context_item(
                f"memory-{memory_id or index}",
                "memory",
                str(memory_value(memory, "title") or f"{memory_type} memory"),
                json.dumps(content, default=str, ensure_ascii=True),
                source="memory_manager",
                entity_type="project_memory_item",
                entity_id=str(memory_id) if memory_id else None,
                metadata={
                    "memory_type": memory_type,
                    "status": status,
                    "write_policy": write_policy,
                    "provenance": provenance,
                },
                priority=base_priority + index,
            )
        )
    return items


def conflict_items(memory_selection: Any | None, *, base_priority: int) -> list[ContextItem]:
    items: list[ContextItem] = []
    for index, conflict in enumerate(memory_conflicts(memory_selection)):
        conflict_id = str(conflict.get("conflict_group_id") or index)
        items.append(
            context_item(
                f"memory-conflict-{conflict_id}",
                "conflict",
                "Memory conflict",
                json.dumps(conflict, default=str, ensure_ascii=True),
                source="memory_manager",
                entity_type="memory_conflict",
                entity_id=conflict_id,
                metadata={
                    "memory_item_ids": [
                        str(item) for item in conflict.get("memory_item_ids", [])
                    ]
                },
                priority=base_priority + index,
            )
        )
    return items


def memory_metadata(memory_selection: Any | None) -> dict[str, Any]:
    selected = selected_memory(memory_selection)
    excluded = excluded_memory(memory_selection)
    conflicts = memory_conflicts(memory_selection)
    policy = selection_value(memory_selection, "policy") or {}
    return {
        "memory_policy": policy,
        "selected_memory_count": len(selected),
        "excluded_memory_count": len(excluded),
        "memory_conflict_count": len(conflicts),
        "selected_memory_ids": [str(memory_value(item, "id")) for item in selected],
        "excluded_memory": [
            {
                **item,
                "id": str(item.get("id")),
            }
            for item in excluded
            if isinstance(item, dict)
        ],
    }


def selected_memory(memory_selection: Any | None) -> list[Any]:
    value = selection_value(memory_selection, "selected")
    if value is None:
        value = selection_value(memory_selection, "selected_memory")
    return list(value or [])


def excluded_memory(memory_selection: Any | None) -> list[dict[str, Any]]:
    value = selection_value(memory_selection, "excluded")
    if value is None:
        value = selection_value(memory_selection, "excluded_memory")
    return list(value or [])


def memory_conflicts(memory_selection: Any | None) -> list[dict[str, Any]]:
    value = selection_value(memory_selection, "conflicts")
    return list(value or [])


def selection_value(memory_selection: Any | None, key: str) -> Any:
    if memory_selection is None:
        return None
    if isinstance(memory_selection, dict):
        return memory_selection.get(key)
    return getattr(memory_selection, key, None)


def memory_value(memory: Any, key: str) -> Any:
    if isinstance(memory, dict):
        return memory.get(key)
    return getattr(memory, key, None)


def estimate_tokens(content: str) -> int:
    return max(1, len(content) // APPROX_CHARS_PER_TOKEN)
