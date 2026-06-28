"""Evidence-to-context item conversion helpers."""

from typing import Any

from app.features.memory.context_pack import context_item
from app.schemas.context import ContextItem


def evidence_items(output: dict[str, Any]) -> list[ContextItem]:
    results = output.get("results")
    if not isinstance(results, list):
        return []
    items: list[ContextItem] = []
    for index, result in enumerate(results[:10]):
        if not isinstance(result, dict):
            continue
        source_id = str(result.get("source_id") or "")
        chunk_id = str(result.get("chunk_id") or "")
        citation_id = f"{source_id}:{chunk_id}" if source_id and chunk_id else None
        text = str(result.get("text") or "")[:900]
        items.append(
            context_item(
                f"guide-evidence-{chunk_id or index}",
                "evidence",
                str(result.get("title") or f"Retrieved evidence {index + 1}"),
                text,
                source="search_project_evidence",
                entity_type="evidence_chunk" if chunk_id else "evidence_source",
                entity_id=chunk_id or source_id or None,
                citation_id=citation_id,
                metadata={
                    "source_id": source_id,
                    "chunk_id": chunk_id,
                    "url": result.get("url"),
                    "score": result.get("score"),
                    "source_type": result.get("source_type"),
                },
                untrusted=True,
                priority=20 + index,
            )
        )
    return items


def evidence_result_items(
    results: list[Any],
    *,
    prefix: str,
    base_priority: int,
) -> list[ContextItem]:
    items: list[ContextItem] = []
    for index, result in enumerate(results[:12]):
        source_id = result_value(result, "source_id")
        chunk_id = result_value(result, "chunk_id")
        citation_id = f"{source_id}:{chunk_id}" if source_id and chunk_id else None
        text = str(result_value(result, "text") or "")[:900]
        items.append(
            context_item(
                f"{prefix}-evidence-{chunk_id or index}",
                "evidence",
                str(result_value(result, "title") or f"Retrieved evidence {index + 1}"),
                text,
                source=f"{prefix}_retrieval",
                entity_type="evidence_chunk" if chunk_id else "evidence_source",
                entity_id=str(chunk_id or source_id) if (chunk_id or source_id) else None,
                citation_id=citation_id,
                metadata={
                    "source_id": str(source_id) if source_id else None,
                    "chunk_id": str(chunk_id) if chunk_id else None,
                    "url": result_value(result, "url"),
                    "score": result_value(result, "score"),
                    "source_type": result_value(result, "source_type"),
                },
                untrusted=True,
                priority=base_priority + index,
            )
        )
    return items


def result_value(result: Any, key: str) -> Any:
    if isinstance(result, dict):
        return result.get(key)
    return getattr(result, key, None)

