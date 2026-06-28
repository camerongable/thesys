"""Swappable reranker adapters for retrieval feature candidates."""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.ai.litellm_client import ChatMessage, LiteLLMClient, LiteLLMClientError
from app.core.config import Settings
from app.schemas.evidence import EvidenceRetrievalResultRead, RetrievalQueryPlanRead

RERANK_CANDIDATE_LIMIT = 16


@dataclass(frozen=True)
class RerankResult:
    results: list[EvidenceRetrievalResultRead]
    adapter: str
    fallback_used: bool = False
    fallback_reason: str | None = None


def rerank_results(
    settings: Settings,
    query: str,
    plan: RetrievalQueryPlanRead,
    results: list[EvidenceRetrievalResultRead],
) -> RerankResult:
    """Rerank candidates through no-op, deterministic, or provider-backed adapters."""
    if not settings.retrieval_reranking_enabled or settings.retrieval_reranker_provider == "none":
        return RerankResult(results=_no_op_rerank(results), adapter="none")

    fallback_reason: str | None = None
    ordered_ids: list[uuid.UUID] | None = None
    adapter = "deterministic"
    if settings.retrieval_reranker_provider == "litellm" and not settings.should_use_llm_stub:
        adapter = "litellm_cross_encoder_compatible"
        try:
            ordered_ids = _litellm_rerank_order(settings, query, plan, results)
        except Exception as exc:
            fallback_reason = f"LiteLLM reranker failed: {exc}"
            adapter = "deterministic"

    ranked = _deterministic_rerank(query, plan, results, ordered_ids=ordered_ids)
    return RerankResult(
        results=ranked,
        adapter=adapter,
        fallback_used=fallback_reason is not None,
        fallback_reason=fallback_reason,
    )


def _no_op_rerank(
    results: list[EvidenceRetrievalResultRead],
) -> list[EvidenceRetrievalResultRead]:
    return [
        result.model_copy(
            update={
                "rerank_score": result.score,
                "final_rank": index + 1,
                "selection_reason": "Reranking disabled; original retrieval score used.",
            }
        )
        for index, result in enumerate(results)
    ]


def _litellm_rerank_order(
    settings: Settings,
    query: str,
    plan: RetrievalQueryPlanRead,
    results: list[EvidenceRetrievalResultRead],
) -> list[uuid.UUID]:
    candidates = results[:RERANK_CANDIDATE_LIMIT]
    if not candidates:
        return []
    payload = {
        "query": query,
        "intent": plan.intent,
        "needed_evidence_types": plan.needed_evidence_types,
        "candidates": [
            {
                "chunk_id": str(result.chunk_id),
                "title": result.title,
                "source_type": result.source_type,
                "score": result.score,
                "text": result.text[:900],
            }
            for result in candidates
        ],
    }
    messages = [
        ChatMessage(
            role="system",
            content=(
                "Rerank retrieved evidence for a founder strategic RAG workflow. "
                "Return JSON only with key ranked_chunk_ids as an ordered array "
                "of chunk_id strings. Prefer specific, source-backed evidence and "
                "reject generic or weak snippets."
            ),
        ),
        ChatMessage(role="user", content=json.dumps(payload, ensure_ascii=True, default=str)),
    ]
    completion = LiteLLMClient(settings).complete(
        messages,
        model=settings.litellm_model,
        temperature=0.0,
        response_format_json=True,
        max_tokens=600,
    )
    try:
        body = json.loads(completion.content)
        raw_ids = body.get("ranked_chunk_ids")
    except json.JSONDecodeError as exc:
        raise LiteLLMClientError("LiteLLM reranker did not return valid JSON.") from exc
    if not isinstance(raw_ids, list):
        raise LiteLLMClientError("LiteLLM reranker response omitted ranked_chunk_ids.")
    valid_ids = {result.chunk_id for result in candidates}
    ordered: list[uuid.UUID] = []
    for raw_id in raw_ids:
        try:
            chunk_id = uuid.UUID(str(raw_id))
        except ValueError:
            continue
        if chunk_id in valid_ids and chunk_id not in ordered:
            ordered.append(chunk_id)
    return ordered


def _deterministic_rerank(
    query: str,
    plan: RetrievalQueryPlanRead,
    results: list[EvidenceRetrievalResultRead],
    *,
    ordered_ids: list[uuid.UUID] | None,
) -> list[EvidenceRetrievalResultRead]:
    query_terms = _term_set(query)
    planned_terms = _term_set(" ".join(plan.needed_evidence_types))
    explicit_rank = {chunk_id: index for index, chunk_id in enumerate(ordered_ids or [])}
    scored: list[tuple[float, EvidenceRetrievalResultRead]] = []
    for result in results:
        text_terms = _term_set(result.text)
        overlap = len(query_terms & text_terms) / max(len(query_terms), 1)
        type_overlap = len(planned_terms & text_terms) / max(len(planned_terms), 1)
        credibility = _metadata_float(result.metadata, "source_credibility_score") or 0.5
        freshness = _freshness_boost(result)
        match_count = _metadata_float(result.metadata, "retrieval_match_count") or 1.0
        quality_weight = _metadata_float(result.metadata, "source_quality_retrieval_weight")
        if quality_weight is None:
            quality = result.metadata.get("source_quality")
            if isinstance(quality, dict):
                quality_weight = _metadata_float(quality, "retrieval_weight")
        quality_weight = quality_weight if quality_weight is not None else credibility
        provider_rank_boost = 0.0
        if result.chunk_id in explicit_rank:
            provider_rank_boost = max(0.0, 0.25 - (explicit_rank[result.chunk_id] * 0.01))
        rerank_score = (
            result.score * 0.55
            + overlap * 0.18
            + type_overlap * 0.08
            + min(quality_weight, 1.0) * 0.08
            + freshness * 0.06
            + min(match_count / 4.0, 1.0) * 0.05
            + provider_rank_boost
        )
        if overlap == 0 and type_overlap == 0 and result.keyword_score == 0:
            rerank_score *= 0.6
        scored.append((round(min(rerank_score, 1.0), 6), result))
    scored.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
    return [
        result.model_copy(
            update={
                "rerank_score": score,
                "final_rank": index + 1,
                "selection_reason": _selection_reason(result, score),
            }
        )
        for index, (score, result) in enumerate(scored)
    ]


def _selection_reason(result: EvidenceRetrievalResultRead, rerank_score: float) -> str:
    reasons: list[str] = []
    if result.keyword_score > 0:
        reasons.append("keyword overlap")
    if result.semantic_score > 0:
        reasons.append("semantic similarity")
    if (_metadata_float(result.metadata, "retrieval_match_count") or 0) > 1:
        reasons.append("matched multiple subqueries")
    if not reasons:
        reasons.append("retrieval score")
    return f"Selected by {', '.join(reasons)}; rerank score {rerank_score:.2f}."


def _metadata_float(metadata: dict[str, object], key: str) -> float | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _freshness_boost(result: EvidenceRetrievalResultRead) -> float:
    return _freshness_score(result.created_at)


def _freshness_score(created_at: datetime | None) -> float:
    if created_at is None:
        return 0.5
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    age_days = max((datetime.now(UTC) - created_at).days, 0)
    if age_days <= 30:
        return 1.0
    if age_days <= 180:
        return 0.6
    if age_days <= 730:
        return 0.3
    return 0.1


def _term_set(text: str) -> set[str]:
    return {
        term
        for term in (
            part.strip(".,:;!?()[]{}\"'").casefold() for part in text.split()
        )
        if len(term) > 2
    }
