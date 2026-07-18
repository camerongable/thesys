"""Deterministic risk and duplicate-concentration controls for retrieval ranking."""

from collections import defaultdict
from typing import Any

from app.schemas.evidence import EvidenceRetrievalResultRead


def apply_security_ranking(
    results: list[EvidenceRetrievalResultRead],
) -> list[EvidenceRetrievalResultRead]:
    """Drop explicitly unsafe results and penalize risk before reranking/context use."""
    safe_results = [
        result
        for result in results
        if _source_trust_status(result.metadata) not in {"blocked", "quarantined"}
    ]
    source_ids_by_content_hash: dict[str, set[object]] = defaultdict(set)
    for result in safe_results:
        content_hash = _content_hash(result.metadata)
        if content_hash:
            source_ids_by_content_hash[content_hash].add(result.source_id)

    scored: list[EvidenceRetrievalResultRead] = []
    for result in safe_results:
        content_hash = _content_hash(result.metadata)
        duplicate_source_count = (
            len(source_ids_by_content_hash[content_hash]) if content_hash else 1
        )
        source_trust = _source_trust(result.metadata)
        injection_score = _float_value(source_trust.get("injection_score"))
        poisoning_score = _float_value(source_trust.get("poisoning_score"))
        risk_penalty = min(0.35, (injection_score * 0.14) + (poisoning_score * 0.21))
        duplicate_penalty = min(0.3, max(duplicate_source_count - 1, 0) * 0.12)
        adjusted_score = max(0.0, result.score - risk_penalty - duplicate_penalty)
        metadata = {
            **result.metadata,
            "security_risk_penalty": round(risk_penalty, 6),
            "duplicate_source_penalty": round(duplicate_penalty, 6),
            "duplicate_source_count": duplicate_source_count,
            "security_rank_score": round(adjusted_score, 6),
        }
        scored.append(result.model_copy(update={"score": adjusted_score, "metadata": metadata}))
    return sorted(scored, key=lambda result: (result.score, result.created_at), reverse=True)


def _source_trust_status(metadata: dict[str, object]) -> str | None:
    source_trust = _source_trust(metadata)
    status = source_trust.get("security_status")
    return str(status) if status is not None else None


def _source_trust(metadata: dict[str, object]) -> dict[str, Any]:
    source_trust = metadata.get("source_trust")
    return source_trust if isinstance(source_trust, dict) else {}


def _content_hash(metadata: dict[str, object]) -> str | None:
    value = metadata.get("source_content_hash") or metadata.get("content_hash")
    return str(value) if isinstance(value, str) and value else None


def _float_value(value: object) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
