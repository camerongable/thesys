"""Deterministic retrieval-sufficiency assessment for evidence-grounded answers."""

from __future__ import annotations

from app.features.retrieval.context_selection import result_domain
from app.features.retrieval.planning import term_set
from app.schemas.evidence import (
    EvidenceRetrievalResultRead,
    RetrievalQueryPlanRead,
    RetrievalSufficiencyRead,
)

MINIMUM_RELEVANCE = 0.35


def assess_retrieval_sufficiency(
    selected: list[EvidenceRetrievalResultRead],
    query_plan: RetrievalQueryPlanRead,
) -> RetrievalSufficiencyRead:
    """Explain whether selected evidence can support a factual generated answer."""

    relevance_scores = [_relevance(result) for result in selected]
    relevant = [
        result
        for result, score in zip(selected, relevance_scores, strict=True)
        if score >= MINIMUM_RELEVANCE
    ]
    source_ids = {result.source_id for result in relevant}
    source_diversity = _source_diversity(relevant, source_ids)
    average_relevance = sum(relevance_scores) / max(len(relevance_scores), 1)
    trusted_source_ratio = _trusted_source_ratio(relevant)
    subqueries = query_plan.subqueries or [query_plan.intent]
    coverage_by_subquestion = {
        subquery: _subquestion_coverage(subquery, relevant) for subquery in subqueries
    }
    reasons: list[str] = []
    if not relevant:
        reasons.append("No retrieved source met the minimum relevance threshold.")
    if average_relevance < MINIMUM_RELEVANCE:
        reasons.append("Average retrieval relevance is below the minimum threshold.")
    if relevant and trusted_source_ratio < 1.0:
        reasons.append("Not every relevant source has approved trust metadata.")
    if not any(coverage_by_subquestion.values()):
        reasons.append("No relevant evidence covers any planned subquestion.")
    return RetrievalSufficiencyRead(
        relevant_source_count=len(source_ids),
        source_diversity=round(source_diversity, 3),
        average_relevance=round(average_relevance, 3),
        trusted_source_ratio=round(trusted_source_ratio, 3),
        coverage_by_subquestion={
            query: round(coverage, 3) for query, coverage in coverage_by_subquestion.items()
        },
        sufficient=not reasons,
        reasons=reasons,
    )


def _relevance(result: EvidenceRetrievalResultRead) -> float:
    score = result.rerank_score if result.rerank_score is not None else result.score
    return max(0.0, min(1.0, score))


def _source_diversity(
    results: list[EvidenceRetrievalResultRead],
    source_ids: set[object],
) -> float:
    if not results:
        return 0.0
    identities = {result_domain(result) or str(result.source_id) for result in results}
    return len(identities) / max(len(source_ids), 1)


def _trusted_source_ratio(results: list[EvidenceRetrievalResultRead]) -> float:
    source_statuses: dict[object, bool] = {}
    for result in results:
        source_trust = result.metadata.get("source_trust")
        is_approved = (
            isinstance(source_trust, dict)
            and source_trust.get("security_status") == "approved"
        )
        source_statuses[result.source_id] = (
            source_statuses.get(result.source_id, False) or is_approved
        )
    return sum(source_statuses.values()) / max(len(source_statuses), 1)


def _subquestion_coverage(
    subquery: str,
    results: list[EvidenceRetrievalResultRead],
) -> float:
    terms = term_set(subquery)
    if not terms:
        return 1.0 if results else 0.0
    return 1.0 if any(terms & term_set(result.text) for result in results) else 0.0
