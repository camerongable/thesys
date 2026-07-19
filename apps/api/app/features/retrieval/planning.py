"""Deterministic retrieval query planning and tokenization helpers."""

import re

from app.schemas.evidence import RetrievalQueryPlanRead

PIPELINE_SUBQUERY_LIMIT = 5
STOPWORDS = {
    "and",
    "are",
    "but",
    "can",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "into",
    "not",
    "our",
    "that",
    "the",
    "this",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "why",
    "with",
    "without",
    "would",
}


def plan_query(query: str) -> RetrievalQueryPlanRead:
    """Create a deterministic lightweight query plan for broad strategic questions."""

    terms = term_set(query)
    raw_terms = raw_term_set(query)
    lowered = query.casefold()
    intent = "general_research"
    intent_markers = {
        "wedge_selection": {"wedge", "positioning", "segment", "focus", "strongest"},
        "pricing": {"pricing", "price", "pay", "willingness", "budget", "monetization"},
        "competitor_analysis": {"competitor", "alternative", "substitute", "incumbent"},
        "validation": {"validate", "validation", "proof", "test", "experiment", "unknown"},
        "customer_pain": {"pain", "problem", "workflow", "urgent", "current"},
    }
    for candidate, markers in intent_markers.items():
        if terms & markers:
            intent = candidate
            break

    needed_evidence_types: list[str] = []
    if terms & {"competitor", "alternative", "substitute", "incumbent"}:
        needed_evidence_types.append("competitor")
    if terms & {"pricing", "price", "pay", "willingness", "budget"}:
        needed_evidence_types.append("pricing")
    if terms & {"pain", "problem", "workflow", "urgent"}:
        needed_evidence_types.append("customer_pain")
    if terms & {"validate", "validation", "proof", "test", "experiment"}:
        needed_evidence_types.append("validation")
    if not needed_evidence_types:
        needed_evidence_types = ["market", "customer_pain", "competitor"]

    broad = (
        len(terms) >= 8
        or " and " in lowered
        or " or " in lowered
        or any(
            marker in raw_terms for marker in {"which", "what", "compare", "strongest", "missing"}
        )
    )
    subqueries = [query.strip()]
    if broad:
        expansions = {
            "competitor": "competitors substitutes alternatives positioning pressure",
            "pricing": "pricing willingness to pay budget paid pilot",
            "customer_pain": "customer pain urgency current workaround workflow",
            "validation": "validation proof experiment success criteria blocker",
            "market": "market landscape trend adoption category",
        }
        for evidence_type in needed_evidence_types:
            expansion = expansions.get(evidence_type)
            if expansion:
                subqueries.append(f"{query.strip()} {expansion}")
        if intent == "wedge_selection":
            subqueries.append(f"{query.strip()} wedge target segment differentiation first proof")
    subqueries = dedupe_strings([item for item in subqueries if item])[:PIPELINE_SUBQUERY_LIMIT]
    return RetrievalQueryPlanRead(
        intent=intent,
        target_entities=target_entities(query),
        needed_evidence_types=needed_evidence_types,
        subqueries=subqueries,
        decomposed=len(subqueries) > 1,
    )


def target_entities(query: str) -> list[str]:
    """Extract title-cased entity candidates from a retrieval query."""

    matches = re.findall(r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,2}\b", query)
    ignored = {"What", "Which", "Why", "How", "Should", "Can", "The", "A", "An"}
    return dedupe_strings([match for match in matches if match.split()[0] not in ignored])[:6]


def dedupe_strings(values: list[str]) -> list[str]:
    """Deduplicate strings case-insensitively while preserving first-seen order."""

    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            deduped.append(value.strip())
    return deduped


def term_set(text: str) -> set[str]:
    return {term for term in raw_term_set(text) if term not in STOPWORDS}


def term_list(text: str) -> list[str]:
    return [term for term in raw_terms(text) if term not in STOPWORDS]


def raw_term_set(text: str) -> set[str]:
    return set(raw_terms(text))


def raw_terms(text: str) -> list[str]:
    return [
        term
        for term in (part.strip(".,:;!?()[]{}\"'").casefold() for part in text.split())
        if len(term) > 2
    ]
