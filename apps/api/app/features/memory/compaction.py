"""Pure payload shaping for approval-gated memory compaction proposals."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompactedMemoryPayload:
    title: str
    summary: str
    content: dict[str, Any]
    provenance_metadata: dict[str, Any]


def compacted_memory_payload(
    *,
    workflow_type: str,
    source_items: list[Any],
    title: str | None = None,
) -> CompactedMemoryPayload:
    summary = " ".join(
        item.summary.strip() for item in source_items if item.summary.strip()
    )[:1800]
    source_memory_ids = [str(item.id) for item in source_items]
    return CompactedMemoryPayload(
        title=title or f"Compacted {workflow_type} memory",
        summary=summary,
        content={
            "summary": summary,
            "source_memory_ids": source_memory_ids,
            "source_memory_titles": [item.title for item in source_items],
            "workflow_type": workflow_type,
        },
        provenance_metadata={
            "source": "memory_compaction",
            "workflow_type": workflow_type,
            "source_memory_ids": source_memory_ids,
            "source_entity_refs": [source_entity_ref(item) for item in source_items],
            "requires_human_approval": True,
        },
    )


def source_entity_ref(item: Any) -> dict[str, str | None]:
    return {
        "memory_id": str(item.id),
        "source_entity_type": item.source_entity_type,
        "source_entity_id": str(item.source_entity_id) if item.source_entity_id else None,
        "superseded_by_id": str(item.superseded_by_id) if item.superseded_by_id else None,
    }

