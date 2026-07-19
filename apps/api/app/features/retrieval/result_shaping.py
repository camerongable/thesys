"""Pure retrieval result shaping helpers."""

import uuid
from collections import defaultdict

from app.schemas.evidence import EvidenceRetrievalResultRead


def fuse_results(
    results: list[EvidenceRetrievalResultRead],
) -> list[EvidenceRetrievalResultRead]:
    """Deduplicate subquery hits while preserving match-count metadata."""
    by_chunk: dict[uuid.UUID, EvidenceRetrievalResultRead] = {}
    match_counts: defaultdict[uuid.UUID, int] = defaultdict(int)
    for result in results:
        match_counts[result.chunk_id] += 1
        existing = by_chunk.get(result.chunk_id)
        if existing is None or result.score > existing.score:
            by_chunk[result.chunk_id] = result

    fused: list[EvidenceRetrievalResultRead] = []
    for result in by_chunk.values():
        metadata = dict(result.metadata)
        metadata["retrieval_match_count"] = match_counts[result.chunk_id]
        fused.append(result.model_copy(update={"metadata": metadata}))
    return sorted(fused, key=lambda item: (item.score, item.created_at), reverse=True)
