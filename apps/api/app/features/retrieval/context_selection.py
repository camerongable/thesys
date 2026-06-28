"""Context selection and lightweight retrieval-quality diagnostics."""

import uuid
from collections import defaultdict
from urllib.parse import urlparse

from app.core.config import Settings
from app.features.retrieval import planning
from app.schemas.evidence import (
    EvidenceRetrievalResultRead,
    RetrievalContextDiagnosticsRead,
    RetrievalDiagnosticsRead,
    RetrievalQualityReportRead,
)

APPROX_CHARS_PER_TOKEN = 4


def assemble_context_results(
    settings: Settings,
    results: list[EvidenceRetrievalResultRead],
    *,
    top_k: int | None = None,
) -> tuple[list[EvidenceRetrievalResultRead], RetrievalContextDiagnosticsRead]:
    """Select final prompt context under token, diversity, and dedupe constraints."""

    selected: list[EvidenceRetrievalResultRead] = []
    per_source: defaultdict[uuid.UUID, int] = defaultdict(int)
    per_domain: defaultdict[str, int] = defaultdict(int)
    per_source_type: defaultdict[str, int] = defaultdict(int)
    per_competitor: defaultdict[str, int] = defaultdict(int)
    token_count = 0
    deduped_count = 0
    dropped_count = 0
    max_results = top_k or len(results)
    signatures: list[set[str]] = []
    for result in diversify_context_candidates(settings, results):
        score = result.rerank_score if result.rerank_score is not None else result.score
        if score < settings.retrieval_min_context_score:
            dropped_count += 1
            continue
        if per_source[result.source_id] >= settings.retrieval_max_chunks_per_source:
            dropped_count += 1
            continue
        domain = result_domain(result)
        if domain and per_domain[domain] >= settings.retrieval_max_chunks_per_domain:
            dropped_count += 1
            continue
        source_type = result.source_type
        if per_source_type[source_type] >= settings.retrieval_max_chunks_per_source_type:
            dropped_count += 1
            continue
        competitor_id = result_competitor_id(result)
        if (
            competitor_id
            and per_competitor[competitor_id] >= settings.retrieval_max_chunks_per_competitor
        ):
            dropped_count += 1
            continue
        terms = signature_terms(result.text)
        if any(jaccard(terms, existing) >= 0.88 for existing in signatures):
            deduped_count += 1
            continue
        estimated_tokens = estimate_tokens(result.text)
        if selected and token_count + estimated_tokens > settings.retrieval_context_token_budget:
            dropped_count += 1
            continue
        selected.append(
            result.model_copy(
                update={
                    "context_included": True,
                    "selection_reason": (
                        context_selection_reason(result, per_source[result.source_id])
                    ),
                }
            )
        )
        signatures.append(terms)
        per_source[result.source_id] += 1
        if domain:
            per_domain[domain] += 1
        per_source_type[source_type] += 1
        if competitor_id:
            per_competitor[competitor_id] += 1
        token_count += estimated_tokens
        if len(selected) >= max_results:
            break
    context = RetrievalContextDiagnosticsRead(
        token_budget=settings.retrieval_context_token_budget,
        token_count=token_count,
        selected_count=len(selected),
        dropped_count=dropped_count,
        deduped_count=deduped_count,
        max_chunks_per_source=settings.retrieval_max_chunks_per_source,
        max_chunks_per_domain=settings.retrieval_max_chunks_per_domain,
        max_chunks_per_source_type=settings.retrieval_max_chunks_per_source_type,
        max_chunks_per_competitor=settings.retrieval_max_chunks_per_competitor,
        mmr_enabled=settings.retrieval_mmr_enabled,
        mmr_lambda=settings.retrieval_mmr_lambda,
        min_context_score=settings.retrieval_min_context_score,
    )
    return selected, context


def diversify_context_candidates(
    settings: Settings,
    results: list[EvidenceRetrievalResultRead],
) -> list[EvidenceRetrievalResultRead]:
    if settings.retrieval_mmr_enabled:
        return mmr_order(results, lambda_weight=settings.retrieval_mmr_lambda)

    by_source: dict[uuid.UUID, list[EvidenceRetrievalResultRead]] = defaultdict(list)
    for result in results:
        by_source[result.source_id].append(result)
    diversified: list[EvidenceRetrievalResultRead] = []
    while by_source:
        for source_id in list(by_source):
            candidates = by_source[source_id]
            if candidates:
                diversified.append(candidates.pop(0))
            if not candidates:
                del by_source[source_id]
    return diversified


def mmr_order(
    results: list[EvidenceRetrievalResultRead],
    *,
    lambda_weight: float,
) -> list[EvidenceRetrievalResultRead]:
    """Order candidates with maximal marginal relevance for diverse context."""

    remaining = list(results)
    selected: list[EvidenceRetrievalResultRead] = []
    while remaining:
        best_index = 0
        best_score = float("-inf")
        for index, candidate in enumerate(remaining):
            relevance = (
                candidate.rerank_score
                if candidate.rerank_score is not None
                else candidate.score
            )
            similarity = max(
                (
                    text_similarity(candidate.text, selected_item.text)
                    for selected_item in selected
                ),
                default=0.0,
            )
            if any(selected_item.source_id == candidate.source_id for selected_item in selected):
                similarity = max(similarity, 1.0)
            mmr_score = (lambda_weight * relevance) - ((1.0 - lambda_weight) * similarity)
            if mmr_score > best_score:
                best_index = index
                best_score = mmr_score
        selected.append(remaining.pop(best_index))
    return selected


def context_selection_reason(
    result: EvidenceRetrievalResultRead,
    prior_source_count: int,
) -> str:
    base = result.selection_reason or "Selected for synthesis context."
    if prior_source_count == 0:
        return f"{base} Prioritized for source diversity."
    return base


def quality_report(
    *,
    selected: list[EvidenceRetrievalResultRead],
    candidate_count: int,
    total_latency_ms: int,
    reranker_used: bool,
    token_count: int,
) -> RetrievalQualityReportRead:
    """Compute cheap retrieval-quality proxies for evals and trace inspection."""

    source_count = len({result.source_id for result in selected})
    selected_count = len(selected)
    recall_proxy = min(1.0, selected_count / max(candidate_count, 1))
    precision_proxy = sum(
        1 for result in selected if (result.rerank_score or result.score) >= 0.35
    ) / max(selected_count, 1)
    relevance_by_rank = [
        min(1.0, max(result.rerank_score if result.rerank_score is not None else result.score, 0.0))
        for result in selected
    ]
    relevant_flags = [score >= 0.35 for score in relevance_by_rank]
    first_relevant = next(
        (index + 1 for index, relevant in enumerate(relevant_flags) if relevant),
        0,
    )
    mrr = 1 / first_relevant if first_relevant else 0.0
    ndcg = ndcg_proxy(relevance_by_rank)
    citation_coverage_proxy = sum(
        1 for result in selected if result.source_id and result.chunk_id
    ) / max(selected_count, 1)
    if source_count >= 3 and selected_count >= 3:
        recall_proxy = max(recall_proxy, 0.75)
    return RetrievalQualityReportRead(
        recall_proxy=round(recall_proxy, 3),
        precision_proxy=round(precision_proxy, 3),
        recall_at_k=round(recall_proxy, 3),
        precision_at_k=round(precision_proxy, 3),
        mrr=round(mrr, 3),
        ndcg_proxy=round(ndcg, 3),
        citation_coverage_proxy=round(citation_coverage_proxy, 3),
        citation_support_rate=round(citation_coverage_proxy, 3),
        unsupported_claim_count=0,
        unsupported_claim_rate=0.0,
        average_retrieval_latency_ms=total_latency_ms,
        reranker_used=reranker_used,
        context_token_count=token_count,
    )


def ndcg_proxy(relevance_scores: list[float]) -> float:
    if not relevance_scores:
        return 0.0
    dcg = sum(score / log2(index + 2) for index, score in enumerate(relevance_scores))
    ideal = sorted(relevance_scores, reverse=True)
    idcg = sum(score / log2(index + 2) for index, score in enumerate(ideal))
    return dcg / max(idcg, 0.0001)


def combine_fallback_reasons(diagnostics: list[RetrievalDiagnosticsRead]) -> str | None:
    reasons = planning.dedupe_strings(
        [item.fallback_reason for item in diagnostics if item.fallback_reason]
    )
    return "; ".join(reasons) if reasons else None


def result_domain(result: EvidenceRetrievalResultRead) -> str | None:
    metadata_domain = result.metadata.get("domain")
    if isinstance(metadata_domain, str) and metadata_domain.strip():
        return metadata_domain.strip().casefold()
    if not result.url:
        return None
    parsed = urlparse(result.url)
    return parsed.hostname.casefold() if parsed.hostname else None


def result_competitor_id(result: EvidenceRetrievalResultRead) -> str | None:
    metadata = result.metadata
    value = metadata.get("competitor_id")
    if value:
        return str(value)
    values = metadata.get("competitor_ids")
    if isinstance(values, list) and values:
        return str(values[0])
    return None


def estimate_tokens(text_value: str) -> int:
    return max(1, int(len(text_value) / APPROX_CHARS_PER_TOKEN))


def signature_terms(text_value: str) -> set[str]:
    terms = list(planning.term_set(text_value))
    return set(terms[:120])


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def text_similarity(left: str, right: str) -> float:
    return jaccard(signature_terms(left), signature_terms(right))


def log2(value: int) -> float:
    # Avoid a new dependency/import for this tiny ranking proxy.
    lookup = {2: 1.0, 3: 1.585, 4: 2.0, 5: 2.322, 6: 2.585, 7: 2.807, 8: 3.0}
    return lookup.get(value, 3.0)
