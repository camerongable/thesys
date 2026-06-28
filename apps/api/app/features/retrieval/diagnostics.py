"""Retrieval diagnostic DTO shaping."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.core.config import Settings
from app.features.retrieval import context_selection
from app.schemas.evidence import (
    RetrievalContextDiagnosticsRead,
    RetrievalDiagnosticsRead,
    RetrievalQualityReportRead,
    RetrievalQueryPlanRead,
    RetrievalRerankerDiagnosticsRead,
)


def base_diagnostics(
    settings: Settings,
    started: float,
    *,
    index_name: str | None,
    index_available: bool,
    candidate_count: int,
    used_sql_vector_search: bool,
    fallback_path_used: bool,
    fallback_reason: str | None,
) -> RetrievalDiagnosticsRead:
    return RetrievalDiagnosticsRead(
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        embedding_version=settings.embedding_version,
        index_name=index_name,
        index_available=index_available,
        candidate_count=candidate_count,
        query_latency_ms=int((perf_counter() - started) * 1000),
        used_sql_vector_search=used_sql_vector_search,
        fallback_path_used=fallback_path_used,
        fallback_reason=fallback_reason,
    )


def pipeline_diagnostics(
    primary: RetrievalDiagnosticsRead,
    query_diagnostics: list[RetrievalDiagnosticsRead],
    *,
    total_latency_ms: int,
    query_plan: RetrievalQueryPlanRead,
    reranker: RetrievalRerankerDiagnosticsRead,
    context: RetrievalContextDiagnosticsRead,
    quality_report: RetrievalQualityReportRead,
    cache: dict[str, Any] | None,
) -> RetrievalDiagnosticsRead:
    diagnostic_payload = primary.model_dump()
    diagnostic_payload.update(
        {
            "candidate_count": sum(item.candidate_count for item in query_diagnostics),
            "query_latency_ms": total_latency_ms,
            "used_sql_vector_search": any(
                item.used_sql_vector_search for item in query_diagnostics
            ),
            "fallback_path_used": any(item.fallback_path_used for item in query_diagnostics),
            "fallback_reason": context_selection.combine_fallback_reasons(query_diagnostics),
            "query_plan": query_plan,
            "reranker": reranker,
            "context": context,
            "quality_report": quality_report,
            "cache": cache,
        }
    )
    return RetrievalDiagnosticsRead.model_validate(diagnostic_payload)
