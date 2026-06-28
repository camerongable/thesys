"""Source-discovery candidate shaping and provenance helpers."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote_plus

from app.ai.litellm_client import ChatMessage
from app.ai.prompts import UNTRUSTED_RETRIEVED_CONTENT_RULE
from app.db.models import DiscoveredSource, ResearchSprint
from app.schemas.research import SourceDiscoveryDraft


def source_discovery_messages(sprint: ResearchSprint) -> list[ChatMessage]:
    plan = sprint.plan
    payload = {
        "objective": plan.objective,
        "target_customer_hypotheses": plan.target_customer_hypotheses,
        "research_questions": plan.research_questions,
        "competitor_queries": plan.competitor_queries,
        "market_queries": plan.market_queries,
        "substitute_queries": plan.substitute_queries,
        "requested_source_types": plan.source_types,
        "max_candidates": 10,
    }
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a source discovery planner for a founder strategy workspace. "
                "Generate candidate public sources for a human to review before ingestion. "
                "Do not claim that you browsed the web. Prefer high-signal primary pages, "
                "pricing pages, review directories, forums, market reports, and specific "
                "search-result URLs when a concrete source is uncertain. Each candidate must "
                "explain why it is worth reviewing and which research question it supports. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE}"
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Create a ranked source candidate list from this approved research plan. "
                "Return only the structured JSON.\n\n"
                f"{json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}"
            ),
        ),
    ]


def candidate_specs_from_draft(draft: SourceDiscoveryDraft) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for source in draft.sources:
        url = clean_url(source.url)
        if not url:
            continue
        specs.append(
            {
                "url": url,
                "title": source.title[:500] if source.title else None,
                "snippet": source.snippet,
                "source_type": source.source_type,
                "relevance_score": clamp_score(source.relevance_score),
                "reason_selected": source.reason_selected,
                "associated_research_question": source.associated_research_question,
            }
        )
    return dedupe_specs(specs)


def candidate_specs_from_search(batch: Any) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for result in batch.results:
        url = clean_url(result.url)
        if not url:
            continue
        source_type = infer_source_type(
            result.url,
            result.title,
            result.snippet,
            result.metadata.get("source_type_hint"),
        )
        specs.append(
            {
                "url": url,
                "title": result.title[:500] if result.title else None,
                "snippet": result.snippet,
                "source_type": source_type,
                "relevance_score": clamp_score(result.score),
                "reason_selected": (
                    "External search result selected for human review before ingestion."
                ),
                "associated_research_question": result.query,
                "search_provider": result.provider,
                "search_query": result.query,
                "search_result_rank": result.rank,
                "retrieved_at": result.retrieved_at,
                "risk_level": risk_level(source_type),
                "provenance_metadata": {
                    "search_provider": result.provider,
                    "search_query": result.query,
                    "search_result_rank": result.rank,
                    "retrieved_at": result.retrieved_at.isoformat(),
                    "search_score": str(result.score),
                    **result.metadata,
                },
            }
        )
    return dedupe_specs(specs)


def fallback_candidate_specs(sprint: ResearchSprint) -> list[dict[str, Any]]:
    plan = sprint.plan
    queries = ordered_queries(
        [
            *plan.market_queries,
            *plan.competitor_queries,
            *plan.substitute_queries,
            *plan.research_questions,
        ]
    )
    if not queries:
        queries = [plan.objective]

    specs: list[dict[str, Any]] = []
    for index, query in enumerate(queries[:8]):
        score_base = max(Decimal("0.95") - Decimal(index) * Decimal("0.03"), Decimal("0.62"))
        specs.extend(
            [
                spec(
                    query,
                    "directory",
                    f"https://www.g2.com/search?query={quote_plus(query)}",
                    f"G2 search for {query}",
                    score_base,
                    "Directory pages can reveal named competitors, categories, and review "
                    "patterns.",
                ),
                spec(
                    query,
                    "forum",
                    f"https://www.reddit.com/search/?q={quote_plus(query)}",
                    f"Reddit discussions for {query}",
                    score_base - Decimal("0.04"),
                    "Forum threads can reveal customer pain, substitutes, and language users use.",
                ),
                spec(
                    query,
                    "market_report",
                    f"https://www.google.com/search?q={quote_plus(query + ' market report')}",
                    f"Market report search for {query}",
                    score_base - Decimal("0.08"),
                    "Market landscape sources can help calibrate category maturity and trends.",
                ),
            ]
        )

    for query in plan.competitor_queries[:4]:
        specs.append(
            spec(
                query,
                "pricing_page",
                f"https://www.google.com/search?q={quote_plus(query + ' pricing')}",
                f"Pricing page search for {query}",
                Decimal("0.81"),
                "Pricing pages help test willingness-to-pay and packaging assumptions.",
            )
        )
    return dedupe_specs(specs)


def spec(
    query: str,
    source_type: str,
    url: str,
    title: str,
    score: Decimal,
    reason: str,
) -> dict[str, Any]:
    clean_query = " ".join(query.split())
    return {
        "url": url,
        "title": title[:500],
        "snippet": f"Candidate public source to inspect for: {clean_query}",
        "source_type": source_type,
        "relevance_score": max(min(score, Decimal("1.00")), Decimal("0.00")),
        "reason_selected": reason,
        "associated_research_question": clean_query,
    }


def ordered_queries(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = " ".join(str(value).split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            ordered.append(cleaned)
            seen.add(key)
    return ordered


def search_queries_for_sprint(sprint: ResearchSprint) -> list[str]:
    plan = sprint.plan
    queries = ordered_queries(
        [
            *plan.competitor_queries,
            *plan.substitute_queries,
            *plan.market_queries,
            *plan.research_questions,
        ]
    )
    return queries or [plan.objective]


def dedupe_specs(specs: list[dict[str, object]]) -> list[dict[str, object]]:
    by_url: dict[str, dict[str, object]] = {}
    for spec_item in specs:
        key = normalize_url(str(spec_item["url"]))
        if key not in by_url:
            by_url[key] = spec_item
    return list(by_url.values())


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/").casefold()


def clean_url(url: str) -> str:
    cleaned = " ".join(url.split())
    if not cleaned:
        return ""
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://www.google.com/search?q={quote_plus(cleaned)}"


def clamp_score(score: Decimal) -> Decimal:
    return max(min(score, Decimal("1.00")), Decimal("0.00"))


def infer_source_type(
    url: str,
    title: str | None,
    snippet: str | None,
    hint: object | None,
) -> str:
    allowed = {
        "company_site",
        "pricing_page",
        "product_page",
        "review",
        "forum",
        "blog",
        "market_report",
        "directory",
        "docs",
        "unknown",
    }
    if isinstance(hint, str) and hint in allowed:
        return hint
    combined = f"{url} {title or ''} {snippet or ''}".casefold()
    if any(term in combined for term in ["pricing", "plans", "price"]):
        return "pricing_page"
    if any(term in combined for term in ["reddit", "forum", "community", "discussion"]):
        return "forum"
    if any(term in combined for term in ["review", "g2", "capterra", "trustpilot"]):
        return "review"
    if any(term in combined for term in ["market", "report", "trend", "industry"]):
        return "market_report"
    if any(term in combined for term in ["docs", "documentation", "changelog"]):
        return "docs"
    if any(term in combined for term in ["directory", "alternatives", "list"]):
        return "directory"
    if any(term in combined for term in ["product", "features"]):
        return "product_page"
    return "unknown"


def risk_level(source_type: str) -> str:
    if source_type in {"forum", "review", "unknown"}:
        return "medium"
    return "low"


def snapshot_text(source: DiscoveredSource) -> str:
    return "\n\n".join(
        part
        for part in [
            source.title,
            f"URL: {source.url}",
            source.snippet,
            f"Reason selected: {source.reason_selected}",
            (
                f"Associated research question: {source.associated_research_question}"
                if source.associated_research_question
                else None
            ),
        ]
        if part
    )


def source_evidence_metadata(
    source: DiscoveredSource,
    sprint: ResearchSprint,
) -> dict[str, object]:
    return {
        "origin": "source_discovery",
        "research_sprint_id": str(sprint.id),
        "research_sprint_ids": [str(sprint.id)],
        "research_plan_id": str(sprint.plan.id),
        "discovered_source_id": str(source.id),
        "discovered_source_ids": [str(source.id)],
        "source_candidate_type": source.source_type,
        "source_candidate_types": [source.source_type],
        "source_relevance_score": str(source.relevance_score),
        "reason_selected": source.reason_selected,
        "associated_research_question": source.associated_research_question,
        "search_provider": source.search_provider,
        "search_query": source.search_query,
        "search_result_rank": source.search_result_rank,
        "retrieved_at": source.retrieved_at.isoformat() if source.retrieved_at else None,
        "risk_level": source.risk_level,
        "provenance": source.provenance_metadata or {},
        "research_questions": (
            [source.associated_research_question] if source.associated_research_question else []
        ),
        "assumptions_to_test": sprint.plan.assumptions_to_test,
        "source_fetched_at": datetime.now(UTC).isoformat(),
    }
