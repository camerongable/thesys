import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import Settings


class ExternalSearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExternalSearchResult:
    provider: str
    query: str
    rank: int
    url: str
    title: str | None
    snippet: str | None
    score: Decimal
    retrieved_at: datetime
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ExternalSearchBatch:
    provider: str
    enabled: bool
    query_count: int
    result_count: int
    deduped_count: int
    fallback_used: bool
    fallback_reason: str | None
    results: list[ExternalSearchResult]


def search_many(settings: Settings, queries: list[str]) -> ExternalSearchBatch:
    cleaned_queries = _clean_queries(queries)[: settings.external_search_max_queries_per_sprint]
    if not settings.external_search_enabled:
        return ExternalSearchBatch(
            provider=settings.external_search_provider,
            enabled=False,
            query_count=0,
            result_count=0,
            deduped_count=0,
            fallback_used=False,
            fallback_reason=None,
            results=[],
        )

    provider = settings.external_search_provider
    raw_results: list[ExternalSearchResult] = []
    fallback_used = False
    fallback_reason: str | None = None
    try:
        if provider == "tavily":
            raw_results = _search_tavily(settings, cleaned_queries)
        else:
            raw_results = _search_deterministic(settings, cleaned_queries)
    except ExternalSearchError as exc:
        if provider != "tavily":
            raise
        fallback_used = True
        fallback_reason = str(exc)
        raw_results = _search_deterministic(settings, cleaned_queries)
        provider = "deterministic"

    deduped_results = _dedupe_results(raw_results)
    return ExternalSearchBatch(
        provider=provider,
        enabled=True,
        query_count=len(cleaned_queries),
        result_count=len(deduped_results),
        deduped_count=len(raw_results) - len(deduped_results),
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        results=deduped_results,
    )


def diagnostics(batch: ExternalSearchBatch) -> dict[str, Any]:
    return {
        "enabled": batch.enabled,
        "provider": batch.provider,
        "query_count": batch.query_count,
        "result_count": batch.result_count,
        "deduped_count": batch.deduped_count,
        "fallback_used": batch.fallback_used,
        "fallback_reason": batch.fallback_reason,
    }


def _search_tavily(settings: Settings, queries: list[str]) -> list[ExternalSearchResult]:
    if not settings.tavily_api_key or not settings.tavily_api_key.strip():
        raise ExternalSearchError("Tavily search requires TAVILY_API_KEY.")

    results: list[ExternalSearchResult] = []
    headers = {
        "Authorization": f"Bearer {settings.tavily_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=settings.external_search_timeout_seconds) as client:
            for query in queries:
                response = client.post(
                    "https://api.tavily.com/search",
                    headers=headers,
                    json={
                        "query": query,
                        "search_depth": "basic",
                        "include_answer": False,
                        "include_raw_content": False,
                        "max_results": settings.external_search_max_results_per_query,
                    },
                )
                response.raise_for_status()
                body = response.json()
                for index, item in enumerate(body.get("results") or [], start=1):
                    url = str(item.get("url") or "").strip()
                    if not url:
                        continue
                    results.append(
                        ExternalSearchResult(
                            provider="tavily",
                            query=query,
                            rank=index,
                            url=url,
                            title=_clean_optional(item.get("title")),
                            snippet=_clean_optional(item.get("content") or item.get("snippet")),
                            score=_score(item.get("score")),
                            retrieved_at=datetime.now(UTC),
                            metadata={
                                "provider": "tavily",
                                "response_query": body.get("query"),
                                "raw_score": item.get("score"),
                            },
                        )
                    )
    except httpx.HTTPStatusError as exc:
        raise ExternalSearchError(
            f"Tavily search returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise ExternalSearchError(f"Tavily search failed: {exc}") from exc
    except ValueError as exc:
        raise ExternalSearchError("Tavily search response was not valid JSON.") from exc
    return results


def _search_deterministic(settings: Settings, queries: list[str]) -> list[ExternalSearchResult]:
    source_templates = [
        ("market_report", "Market landscape"),
        ("product_page", "Product page"),
        ("pricing_page", "Pricing page"),
        ("forum", "Forum discussion"),
        ("directory", "Directory listing"),
    ]
    results: list[ExternalSearchResult] = []
    for query in queries:
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
        for index, (source_type, label) in enumerate(source_templates, start=1):
            if index > settings.external_search_max_results_per_query:
                break
            score = max(
                Decimal("0.20"),
                Decimal("1.00") - (Decimal(index) * Decimal("0.12")),
            ).quantize(Decimal("0.01"))
            slug = "-".join(_keywords(query)[:5]) or "research"
            url = f"https://example.com/{source_type}/{digest}-{index}-{slug}"
            results.append(
                ExternalSearchResult(
                    provider="deterministic",
                    query=query,
                    rank=index,
                    url=url,
                    title=f"{label}: {query[:80]}",
                    snippet=(
                        f"Deterministic search result for '{query}'. Includes market, "
                        "competitor, pricing, substitute, and validation context."
                    ),
                    score=score,
                    retrieved_at=datetime.now(UTC),
                    metadata={"provider": "deterministic", "source_type_hint": source_type},
                )
            )
    return results


def _clean_queries(queries: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = " ".join(str(query).split())
        marker = normalized.casefold()
        if normalized and marker not in seen:
            cleaned.append(normalized[:500])
            seen.add(marker)
    return cleaned


def _dedupe_results(results: list[ExternalSearchResult]) -> list[ExternalSearchResult]:
    deduped: list[ExternalSearchResult] = []
    seen: set[str] = set()
    for result in results:
        marker = _normalize_url(result.url)
        if marker in seen:
            continue
        deduped.append(result)
        seen.add(marker)
    return deduped


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").casefold()
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def _clean_optional(value: object) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text[:1000] if text else None


def _score(value: object) -> Decimal:
    try:
        score = Decimal(str(value))
    except Exception:
        return Decimal("0.50")
    if score < 0:
        return Decimal("0")
    if score > 1:
        return Decimal("1")
    return score.quantize(Decimal("0.01"))


def _keywords(query: str) -> list[str]:
    return [
        "".join(ch for ch in word.casefold() if ch.isalnum())
        for word in query.split()
        if any(ch.isalnum() for ch in word)
    ]
