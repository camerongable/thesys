"""Pure retrieval scoring helpers."""

import uuid
from collections import Counter
from collections.abc import Mapping

from app.features.retrieval import planning as retrieval_planning
from app.schemas.evidence import RetrievalMode


def combined_score(
    mode: RetrievalMode,
    semantic_score: float,
    keyword_score: float,
    *,
    text_search_enabled: bool,
    text_search_weight: float,
) -> float:
    if mode == "semantic":
        return semantic_score
    if mode == "keyword":
        return keyword_score
    text_weight = text_search_weight if text_search_enabled else 0.35
    return (semantic_score * (1.0 - text_weight)) + (keyword_score * text_weight)


def keyword_score(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    text_terms = retrieval_planning.term_set(text)
    if not text_terms:
        return 0.0
    overlap = query_terms & text_terms
    if not overlap:
        return 0.0
    return len(overlap) / len(query_terms)


def bm25_keyword_scores(
    query_terms: set[str],
    documents: Mapping[uuid.UUID, str],
) -> dict[uuid.UUID, float]:
    if not query_terms or not documents:
        return {}
    docs = {
        chunk_id: retrieval_planning.term_list(text)
        for chunk_id, text in documents.items()
    }
    doc_count = len(docs)
    avgdl = sum(len(terms) for terms in docs.values()) / max(doc_count, 1)
    doc_freq: Counter[str] = Counter()
    for terms in docs.values():
        doc_freq.update(set(terms))

    raw_scores: dict[uuid.UUID, float] = {}
    k1 = 1.5
    b = 0.75
    for chunk_id, terms in docs.items():
        frequencies = Counter(terms)
        score = 0.0
        doc_len = len(terms)
        for term in query_terms:
            if frequencies[term] == 0:
                continue
            idf = max(
                0.0,
                ((doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5)),
            )
            tf = frequencies[term]
            denominator = tf + k1 * (1 - b + b * (doc_len / max(avgdl, 1.0)))
            score += idf * ((tf * (k1 + 1)) / max(denominator, 0.0001))
        raw_scores[chunk_id] = score

    max_score = max(raw_scores.values(), default=0.0)
    if max_score <= 0:
        return {chunk_id: 0.0 for chunk_id in raw_scores}
    return {chunk_id: round(score / max_score, 6) for chunk_id, score in raw_scores.items()}
