"""Evidence retrieval pipeline for project-scoped RAG.

The pipeline is intentionally inspectable: each search records query planning,
vector/fallback path, reranking, context assembly, and quality proxies so AI
answers can be debugged without exposing those details in the main workflow UI.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from urllib.parse import urlparse

from sqlalchemy import Select, cast, desc, func, literal, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.ai.prompts import EVIDENCE_RETRIEVAL_PROMPT_VERSION
from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import AIRun, AIStep, EvidenceChunk, EvidenceSource
from app.features.retrieval import context_selection as retrieval_context_selection_feature
from app.features.retrieval import diagnostics as retrieval_diagnostics_feature
from app.features.retrieval import planning as retrieval_planning_feature
from app.features.retrieval import reranker as retrieval_reranker_feature
from app.features.retrieval import result_shaping as retrieval_result_shaping_feature
from app.features.retrieval import scoring as retrieval_scoring_feature
from app.schemas.evidence import (
    EvidenceRetrievalResultRead,
    EvidenceRetrieveCreate,
    RetrievalDiagnosticsRead,
    RetrievalMode,
    RetrievalQueryPlanRead,
    RetrievalRerankerDiagnosticsRead,
)
from app.services import (
    ai_cache_service,
    ai_run_service,
    embedding_service,
    project_service,
    retrieval_reranker_service,
)
from app.services.common import workflow as workflow_utils

SQL_VECTOR_CANDIDATE_MULTIPLIER = 4
RERANK_CANDIDATE_LIMIT = 16


@dataclass(frozen=True)
class RetrievalRunResult:
    """Retrieval result plus persisted AI run/step records."""

    run: AIRun
    step: AIStep
    mode: RetrievalMode
    query: str
    diagnostics: RetrievalDiagnosticsRead
    results: list[EvidenceRetrievalResultRead]


@dataclass(frozen=True)
class RetrievalSearchResult:
    diagnostics: RetrievalDiagnosticsRead
    results: list[EvidenceRetrievalResultRead]


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk: EvidenceChunk
    source: EvidenceSource


def retrieve_evidence(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> RetrievalRunResult:
    """Run retrieval and persist an observable AI run around the search."""
    project_service.get_project(db, auth, project_id)
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="evidence_retrieval",
        prompt_version=EVIDENCE_RETRIEVAL_PROMPT_VERSION,
        input_summary=payload.query[:500],
        project_id=project_id,
        model_provider=settings.embedding_provider,
        model_name=settings.embedding_model,
    )
    step = ai_run_service.start_step(
        db,
        run,
        step_name=f"{payload.mode}_retrieval",
        input_json=payload.model_dump(mode="json"),
    )

    try:
        search = retrieve_evidence_search(db, auth, settings, project_id, payload)
        completed = workflow_utils.complete_zero_cost_step_and_run(
            db,
            run=run,
            step=step,
            output_json={
                "result_count": len(search.results),
                "diagnostics": search.diagnostics.model_dump(mode="json"),
                "results": [result.model_dump(mode="json") for result in search.results],
            },
            latency_ms=search.diagnostics.query_latency_ms,
            output_summary=f"Retrieved {len(search.results)} chunks for query.",
            model_provider=settings.embedding_provider,
            model_name=settings.embedding_model,
        )
        return RetrievalRunResult(
            run=completed.run,
            step=completed.step,
            mode=payload.mode,
            query=payload.query,
            diagnostics=search.diagnostics,
            results=search.results,
        )
    except Exception as exc:
        workflow_utils.fail_step_and_run(db, run=run, step=step, error=str(exc))
        raise


def retrieve_evidence_results(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> list[EvidenceRetrievalResultRead]:
    return retrieve_evidence_search(db, auth, settings, project_id, payload).results


def retrieve_evidence_search(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> RetrievalSearchResult:
    return retrieve_evidence_pipeline(db, auth, settings, project_id, payload)


def retrieve_evidence_pipeline(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> RetrievalSearchResult:
    """Plan, retrieve, fuse, rerank, and assemble context for one user query."""
    project_service.get_project(db, auth, project_id)
    started = perf_counter()
    key_payload, family_payload, version_payload = ai_cache_service.retrieval_cache_payloads(
        db,
        auth,
        settings,
        project_id,
        payload,
        context_profile="evidence_retrieval",
    )
    cache_lookup = ai_cache_service.lookup(
        db,
        auth,
        settings,
        cache_type="retrieval_plan",
        key_payload=key_payload,
        family_payload=family_payload,
        version_payload=version_payload,
        project_id=project_id,
        saved_tokens=settings.retrieval_context_token_budget,
        latency_saved_ms=80,
    )
    if cache_lookup.value is not None:
        diagnostics = RetrievalDiagnosticsRead.model_validate(
            cache_lookup.value["diagnostics"]
        )
        diagnostics = diagnostics.model_copy(
            update={
                "query_latency_ms": int((perf_counter() - started) * 1000),
                "cache": ai_cache_service.cache_event_diagnostics(cache_lookup.event),
            }
        )
        results = [
            EvidenceRetrievalResultRead.model_validate(result)
            for result in cache_lookup.value.get("results", [])
        ]
        return RetrievalSearchResult(diagnostics=diagnostics, results=results)

    plan = _plan_query(payload.query)
    subqueries = plan.subqueries or [payload.query]
    all_results: list[EvidenceRetrievalResultRead] = []
    diagnostics: list[RetrievalDiagnosticsRead] = []

    for subquery in subqueries:
        sub_payload = payload.model_copy(
            update={"query": subquery, "top_k": max(payload.top_k, 12)}
        )
        search = _retrieve_single_query_search(db, auth, settings, project_id, sub_payload)
        diagnostics.append(search.diagnostics)
        all_results.extend(search.results)

    fused_results = _fuse_results(all_results)
    reranked, reranker = _rerank_results(
        db,
        auth,
        settings,
        project_id,
        payload.query,
        plan,
        fused_results,
        version_payload,
    )
    assembled, context = assemble_context_results(settings, reranked, top_k=payload.top_k)
    total_latency = int((perf_counter() - started) * 1000)
    quality = _quality_report(
        selected=assembled,
        candidate_count=len(fused_results),
        total_latency_ms=total_latency,
        reranker_used=reranker.enabled and not reranker.fallback_used,
        token_count=context.token_count,
    )
    primary = (
        diagnostics[0]
        if diagnostics
        else _diagnostics(
            settings,
            started,
            index_name=None,
            index_available=False,
            candidate_count=0,
            used_sql_vector_search=False,
            fallback_path_used=False,
            fallback_reason=None,
        )
    )
    pipeline_diagnostics = _pipeline_diagnostics(
        primary,
        diagnostics,
        total_latency_ms=total_latency,
        query_plan=plan,
        reranker=reranker,
        context=context,
        quality_report=quality,
        cache=ai_cache_service.cache_event_diagnostics(cache_lookup.event),
    )
    ai_cache_service.store(
        db,
        auth,
        cache_type="retrieval_plan",
        key_payload=key_payload,
        family_payload=family_payload,
        version_payload=version_payload,
        value_payload={
            "diagnostics": pipeline_diagnostics.model_dump(mode="json"),
            "results": [result.model_dump(mode="json") for result in assembled],
        },
        project_id=project_id,
    )
    return RetrievalSearchResult(diagnostics=pipeline_diagnostics, results=assembled)


def _retrieve_single_query_search(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> RetrievalSearchResult:
    """Retrieve candidates for one subquery using SQL vectors or local fallback."""
    project_service.get_project(db, auth, project_id)
    started = perf_counter()
    index_name, index_available = _pgvector_index_status(db)

    if payload.mode == "keyword":
        results, candidate_count = _retrieve_with_python_scoring(
            db,
            auth,
            settings,
            project_id,
            payload,
            query_embedding=None,
        )
        return RetrievalSearchResult(
            diagnostics=_diagnostics(
                settings,
                started,
                index_name=index_name,
                index_available=index_available,
                candidate_count=candidate_count,
                used_sql_vector_search=False,
                fallback_path_used=False,
                fallback_reason="keyword mode does not require vector ranking",
            ),
            results=results,
        )

    query_embedding = embedding_service.embed_text_with_metadata_cached(
        db,
        auth,
        settings,
        payload.query,
        project_id=project_id,
    ).vector
    should_use_sql = _should_use_sql_vector_search(db, settings)
    if should_use_sql:
        try:
            results, candidate_count = _retrieve_with_sql_vector_search(
                db,
                auth,
                settings,
                project_id,
                payload,
                query_embedding,
            )
            return RetrievalSearchResult(
                diagnostics=_diagnostics(
                    settings,
                    started,
                    index_name=index_name,
                    index_available=index_available,
                    candidate_count=candidate_count,
                    used_sql_vector_search=True,
                    fallback_path_used=False,
                    fallback_reason=None,
                ),
                results=results,
            )
        except Exception as exc:
            if not settings.retrieval_python_fallback_enabled:
                raise
            fallback_reason = f"sql vector search failed: {exc}"
    else:
        fallback_reason = _sql_vector_unavailable_reason(db, settings)

    if settings.retrieval_vector_path == "sql" and not settings.retrieval_python_fallback_enabled:
        raise RuntimeError(f"SQL vector search unavailable: {fallback_reason}")

    results, candidate_count = _retrieve_with_python_scoring(
        db,
        auth,
        settings,
        project_id,
        payload,
        query_embedding=query_embedding,
    )
    return RetrievalSearchResult(
        diagnostics=_diagnostics(
            settings,
            started,
            index_name=index_name,
            index_available=index_available,
            candidate_count=candidate_count,
            used_sql_vector_search=False,
            fallback_path_used=True,
            fallback_reason=fallback_reason,
        ),
        results=results,
    )


def _retrieve_with_sql_vector_search(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
    query_embedding: list[float],
) -> tuple[list[EvidenceRetrievalResultRead], int]:
    conditions = _base_conditions(auth, project_id, payload)
    conditions.extend(_postgres_metadata_conditions(payload))
    filtered_count = _filtered_count(db, conditions)
    if filtered_count == 0:
        return [], 0

    distance = EvidenceChunk.embedding.cosine_distance(query_embedding).label("distance")
    text_rank = (
        _postgres_text_rank(payload.query)
        if settings.retrieval_text_search_enabled
        else literal(0.0)
    )
    text_rank = text_rank.label("text_rank")
    semantic_rank = 1.0 - distance
    combined_rank = (
        semantic_rank * (1.0 - settings.retrieval_text_search_weight)
        + text_rank * settings.retrieval_text_search_weight
    ).label("combined_rank")
    candidate_limit = max(payload.top_k, payload.top_k * SQL_VECTOR_CANDIDATE_MULTIPLIER)
    stmt = (
        select(EvidenceChunk, EvidenceSource, distance, text_rank, combined_rank)
        .join(EvidenceSource, EvidenceSource.id == EvidenceChunk.source_id)
        .where(*conditions, EvidenceChunk.embedding.is_not(None))
        .limit(candidate_limit)
    )
    if payload.mode == "hybrid" and settings.retrieval_text_search_enabled:
        stmt = stmt.order_by(desc(combined_rank), distance)
    else:
        stmt = stmt.order_by(distance)
    rows = db.execute(stmt).all()
    query_terms = _term_set(payload.query)
    scored: list[EvidenceRetrievalResultRead] = []
    for chunk, source, raw_distance, raw_text_rank, raw_combined_rank in rows:
        distance_value = float(raw_distance or 0)
        semantic_score = max(0.0, 1.0 - distance_value)
        keyword_score = max(
            _keyword_score(query_terms, chunk.text),
            min(float(raw_text_rank or 0), 1.0),
        )
        score = (
            min(float(raw_combined_rank or 0), 1.0)
            if payload.mode == "hybrid" and settings.retrieval_text_search_enabled
            else _combined_score(payload.mode, semantic_score, keyword_score, settings)
        )
        if score <= 0:
            continue
        result = _serialize_result(chunk, source, score, semantic_score, keyword_score)
        metadata = dict(result.metadata)
        metadata.update(
            {
                "postgres_text_rank": round(float(raw_text_rank or 0), 6),
                "postgres_combined_rank": round(float(raw_combined_rank or 0), 6),
                "text_search_ranker": "ts_rank_cd(websearch_to_tsquery)",
            }
        )
        scored.append(result.model_copy(update={"metadata": metadata}))

    scored.sort(key=lambda result: (result.score, result.created_at), reverse=True)
    return scored[: payload.top_k], filtered_count


def _retrieve_with_python_scoring(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
    *,
    query_embedding: list[float] | None,
) -> tuple[list[EvidenceRetrievalResultRead], int]:
    if query_embedding is None and payload.mode != "keyword":
        query_embedding = embedding_service.embed_text_with_metadata_cached(
            db,
            auth,
            settings,
            payload.query,
            project_id=project_id,
        ).vector
    candidates = _load_candidates(db, auth, project_id, payload)
    return (
        _score_candidates(
            settings=settings,
            query=payload.query,
            query_embedding=query_embedding,
            candidates=candidates,
            mode=payload.mode,
            top_k=payload.top_k,
        ),
        len(candidates),
    )


_plan_query = retrieval_planning_feature.plan_query
_target_entities = retrieval_planning_feature.target_entities
_dedupe_strings = retrieval_planning_feature.dedupe_strings


_fuse_results = retrieval_result_shaping_feature.fuse_results


def _rerank_results(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    query: str,
    plan: RetrievalQueryPlanRead,
    results: list[EvidenceRetrievalResultRead],
    retrieval_versions: dict[str, object],
) -> tuple[list[EvidenceRetrievalResultRead], RetrievalRerankerDiagnosticsRead]:
    """Apply optional provider reranking with deterministic fallback visibility."""
    key_payload, family_payload, version_payload = ai_cache_service.rerank_cache_payloads(
        auth,
        settings,
        project_id,
        query=query,
        candidate_chunk_ids=[result.chunk_id for result in results[:RERANK_CANDIDATE_LIMIT]],
        retrieval_policy_version=str(retrieval_versions.get("retrieval_policy_version")),
    )
    cache_lookup = ai_cache_service.lookup(
        db,
        auth,
        settings,
        cache_type="rerank_result",
        key_payload=key_payload,
        family_payload=family_payload,
        version_payload=version_payload,
        project_id=project_id,
        saved_tokens=400 if settings.retrieval_reranker_provider == "litellm" else 0,
        latency_saved_ms=40,
    )
    if cache_lookup.value is not None:
        cached_results = [
            EvidenceRetrievalResultRead.model_validate(result)
            for result in cache_lookup.value.get("results", [])
        ]
        cached = cache_lookup.value.get("reranker", {})
        return cached_results, RetrievalRerankerDiagnosticsRead(
            enabled=bool(cached.get("enabled")),
            provider=str(cached.get("provider") or settings.retrieval_reranker_provider),
            adapter=str(cached.get("adapter") or "cache"),
            fallback_used=bool(cached.get("fallback_used", False)),
            fallback_reason=cached.get("fallback_reason"),
            cache=ai_cache_service.cache_event_diagnostics(cache_lookup.event),
        )

    reranked = retrieval_reranker_service.rerank_results(settings, query, plan, results)
    diagnostics = RetrievalRerankerDiagnosticsRead(
        enabled=settings.retrieval_reranking_enabled
        and settings.retrieval_reranker_provider != "none",
        provider=settings.retrieval_reranker_provider,
        adapter=reranked.adapter,
        fallback_used=reranked.fallback_used,
        fallback_reason=reranked.fallback_reason,
        cache=ai_cache_service.cache_event_diagnostics(cache_lookup.event),
    )
    ai_cache_service.store(
        db,
        auth,
        cache_type="rerank_result",
        key_payload=key_payload,
        family_payload=family_payload,
        version_payload=version_payload,
        value_payload={
            "results": [result.model_dump(mode="json") for result in reranked.results],
            "reranker": diagnostics.model_dump(mode="json"),
        },
        project_id=project_id,
    )
    return reranked.results, diagnostics


_litellm_rerank_order = retrieval_reranker_feature._litellm_rerank_order
_deterministic_rerank = retrieval_reranker_feature._deterministic_rerank


assemble_context_results = retrieval_context_selection_feature.assemble_context_results
_diversify_context_candidates = retrieval_context_selection_feature.diversify_context_candidates
_mmr_order = retrieval_context_selection_feature.mmr_order
_context_selection_reason = retrieval_context_selection_feature.context_selection_reason
_quality_report = retrieval_context_selection_feature.quality_report
_ndcg_proxy = retrieval_context_selection_feature.ndcg_proxy
_combine_fallback_reasons = retrieval_context_selection_feature.combine_fallback_reasons


def _metadata_float(metadata: dict[str, object], key: str) -> float | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.hostname.casefold() if parsed.hostname else None


_signature_terms = retrieval_context_selection_feature.signature_terms
_jaccard = retrieval_context_selection_feature.jaccard
_text_similarity = retrieval_context_selection_feature.text_similarity
_result_domain = retrieval_context_selection_feature.result_domain
_result_competitor_id = retrieval_context_selection_feature.result_competitor_id
_estimate_tokens = retrieval_context_selection_feature.estimate_tokens


def _base_conditions(
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> list[object]:
    conditions: list[object] = [
        EvidenceChunk.workspace_id == auth.workspace_id,
        EvidenceChunk.project_id == project_id,
        EvidenceSource.workspace_id == auth.workspace_id,
        EvidenceSource.project_id == project_id,
        EvidenceSource.ingestion_status == "ready",
    ]
    if payload.source_types:
        conditions.append(EvidenceSource.source_type.in_(payload.source_types))
    if payload.created_after is not None:
        conditions.append(EvidenceSource.created_at >= payload.created_after)
    if payload.created_before is not None:
        conditions.append(EvidenceSource.created_at <= payload.created_before)
    if payload.freshness_days is not None:
        reference = func.coalesce(
            EvidenceSource.source_date,
            EvidenceSource.ingested_at,
            EvidenceSource.created_at,
        )
        conditions.append(reference >= datetime.now(UTC) - timedelta(days=payload.freshness_days))
    return conditions


def _postgres_metadata_conditions(payload: EvidenceRetrieveCreate) -> list[object]:
    conditions: list[object] = []
    if payload.competitor_id is not None:
        conditions.append(_postgres_metadata_id_condition("competitor", payload.competitor_id))
    if payload.assumption_id is not None:
        conditions.append(_postgres_metadata_id_condition("assumption", payload.assumption_id))
    if payload.research_sprint_id is not None:
        conditions.append(
            _postgres_metadata_id_condition("research_sprint", payload.research_sprint_id)
        )
    return conditions


def _postgres_metadata_id_condition(prefix: str, item_id: uuid.UUID):
    metadata = cast(EvidenceChunk.chunk_metadata, JSONB)
    expected = str(item_id)
    return or_(
        metadata.contains({f"{prefix}_id": expected}),
        metadata.contains({f"{prefix}_ids": [expected]}),
    )


def _postgres_text_rank(query: str):
    ts_query = func.websearch_to_tsquery("english", query)
    ts_vector = func.to_tsvector("english", func.coalesce(EvidenceChunk.text, ""))
    return func.ts_rank_cd(ts_vector, ts_query)


def _filtered_count(db: Session, conditions: list[object]) -> int:
    count_stmt = (
        select(func.count(EvidenceChunk.id))
        .select_from(EvidenceChunk)
        .join(EvidenceSource, EvidenceSource.id == EvidenceChunk.source_id)
        .where(*conditions, EvidenceChunk.embedding.is_not(None))
    )
    return int(db.scalar(count_stmt) or 0)


def _load_candidates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> list[RetrievalCandidate]:
    stmt: Select = (
        select(EvidenceChunk, EvidenceSource)
        .join(EvidenceSource, EvidenceSource.id == EvidenceChunk.source_id)
        .where(*_base_conditions(auth, project_id, payload))
    )
    rows = db.execute(stmt).all()
    candidates = [RetrievalCandidate(chunk=chunk, source=source) for chunk, source in rows]
    return [
        candidate
        for candidate in candidates
        if _matches_metadata_filters(candidate, payload)
        and _matches_freshness(candidate.source, payload.freshness_days)
    ]


def _matches_metadata_filters(
    candidate: RetrievalCandidate,
    payload: EvidenceRetrieveCreate,
) -> bool:
    metadata = candidate.chunk.chunk_metadata or {}
    if payload.competitor_id is not None and not _metadata_contains_id(
        metadata,
        "competitor",
        payload.competitor_id,
    ):
        return False
    if payload.assumption_id is not None and not _metadata_contains_id(
        metadata,
        "assumption",
        payload.assumption_id,
    ):
        return False
    if payload.research_sprint_id is not None and not _metadata_contains_id(
        metadata,
        "research_sprint",
        payload.research_sprint_id,
    ):
        return False
    return True


def _metadata_contains_id(metadata: dict[str, object], prefix: str, item_id: uuid.UUID) -> bool:
    expected = str(item_id)
    if metadata.get(f"{prefix}_id") == expected:
        return True
    values = metadata.get(f"{prefix}_ids")
    return isinstance(values, list) and expected in {str(value) for value in values}


def _matches_freshness(source: EvidenceSource, freshness_days: int | None) -> bool:
    if freshness_days is None:
        return True
    reference = source.source_date or source.ingested_at or source.created_at
    return reference >= datetime.now(UTC) - timedelta(days=freshness_days)


def _score_candidates(
    *,
    settings: Settings,
    query: str,
    query_embedding: list[float] | None,
    candidates: list[RetrievalCandidate],
    mode: RetrievalMode,
    top_k: int,
) -> list[EvidenceRetrievalResultRead]:
    query_terms = _term_set(query)
    keyword_scores = _bm25_keyword_scores(query_terms, candidates)
    scored: list[EvidenceRetrievalResultRead] = []
    for candidate in candidates:
        semantic_score = 0.0
        if query_embedding is not None:
            semantic_score = embedding_service.cosine_similarity(
                query_embedding,
                candidate.chunk.embedding,
            )
        keyword_score = keyword_scores.get(candidate.chunk.id, 0.0)
        score = _combined_score(mode, semantic_score, keyword_score, settings)
        if score <= 0:
            continue
        scored.append(
            _serialize_result(
                candidate.chunk,
                candidate.source,
                score,
                semantic_score,
                keyword_score,
            )
        )

    scored.sort(key=lambda result: (result.score, result.created_at), reverse=True)
    return scored[:top_k]


def _serialize_result(
    chunk: EvidenceChunk,
    source: EvidenceSource,
    score: float,
    semantic_score: float,
    keyword_score: float,
) -> EvidenceRetrievalResultRead:
    metadata = dict(chunk.chunk_metadata or {})
    source_quality = metadata.get("source_quality")
    if not isinstance(source_quality, dict):
        source_metadata = metadata.get("source_metadata")
        if isinstance(source_metadata, dict) and isinstance(
            source_metadata.get("source_quality"),
            dict,
        ):
            source_quality = source_metadata["source_quality"]
    reference_date = source.source_date or source.ingested_at or source.created_at
    metadata.update(
        {
            "source_classification": source.classification,
            "source_credibility_score": float(source.credibility_score)
            if source.credibility_score is not None
            else None,
            "source_date": source.source_date.isoformat() if source.source_date else None,
            "source_ingested_at": source.ingested_at.isoformat() if source.ingested_at else None,
            "domain": _domain_from_url(source.url),
            "freshness_score": _freshness_score(reference_date),
            "source_quality": source_quality if isinstance(source_quality, dict) else None,
            "source_quality_retrieval_weight": (
                source_quality.get("retrieval_weight")
                if isinstance(source_quality, dict)
                else None
            ),
            "source_quality_explanation": (
                source_quality.get("explanation") if isinstance(source_quality, dict) else None
            ),
        }
    )
    return EvidenceRetrievalResultRead(
        source_id=source.id,
        chunk_id=chunk.id,
        title=source.title,
        url=source.url,
        source_type=source.source_type,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        score=round(score, 6),
        semantic_score=round(semantic_score, 6),
        keyword_score=round(keyword_score, 6),
        metadata=metadata,
        embedding_provider=chunk.embedding_provider,
        embedding_model=chunk.embedding_model,
        embedding_dimension=chunk.embedding_dimension,
        embedding_version=chunk.embedding_version,
        embedded_at=chunk.embedded_at,
        created_at=chunk.created_at,
    )


def _combined_score(
    mode: RetrievalMode,
    semantic_score: float,
    keyword_score: float,
    settings: Settings,
) -> float:
    return retrieval_scoring_feature.combined_score(
        mode,
        semantic_score,
        keyword_score,
        text_search_enabled=settings.retrieval_text_search_enabled,
        text_search_weight=settings.retrieval_text_search_weight,
    )


_keyword_score = retrieval_scoring_feature.keyword_score


def _bm25_keyword_scores(
    query_terms: set[str],
    candidates: list[RetrievalCandidate],
) -> dict[uuid.UUID, float]:
    return retrieval_scoring_feature.bm25_keyword_scores(
        query_terms,
        {candidate.chunk.id: candidate.chunk.text for candidate in candidates},
    )


_term_set = retrieval_planning_feature.term_set
_term_list = retrieval_planning_feature.term_list
_raw_term_set = retrieval_planning_feature.raw_term_set
_raw_terms = retrieval_planning_feature.raw_terms


def _should_use_sql_vector_search(db: Session, settings: Settings) -> bool:
    if settings.retrieval_vector_path == "python":
        return False
    return _is_postgres(db)


def _sql_vector_unavailable_reason(db: Session, settings: Settings) -> str:
    if settings.retrieval_vector_path == "python":
        return "configured retrieval vector path is python"
    if not _is_postgres(db):
        return "database dialect is not postgres"
    return "sql vector search is unavailable"


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _pgvector_index_status(db: Session) -> tuple[str | None, bool]:
    if not _is_postgres(db):
        return None, False
    for index_name in ("ix_evidence_chunks_embedding_hnsw", "ix_evidence_chunks_embedding_ivfflat"):
        try:
            exists = db.scalar(text("select to_regclass(:index_name)"), {"index_name": index_name})
        except Exception:
            return None, False
        if exists:
            return index_name, True
    return None, False


_diagnostics = retrieval_diagnostics_feature.base_diagnostics
_pipeline_diagnostics = retrieval_diagnostics_feature.pipeline_diagnostics
