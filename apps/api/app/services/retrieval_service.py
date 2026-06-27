import json
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter

from sqlalchemy import Select, cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.ai.litellm_client import ChatMessage, LiteLLMClient, LiteLLMClientError
from app.ai.prompts import EVIDENCE_RETRIEVAL_PROMPT_VERSION
from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import AIRun, AIStep, EvidenceChunk, EvidenceSource
from app.schemas.evidence import (
    EvidenceRetrievalResultRead,
    EvidenceRetrieveCreate,
    RetrievalContextDiagnosticsRead,
    RetrievalDiagnosticsRead,
    RetrievalMode,
    RetrievalQualityReportRead,
    RetrievalQueryPlanRead,
    RetrievalRerankerDiagnosticsRead,
)
from app.services import ai_run_service, embedding_service, project_service
from app.services.common import workflow as workflow_utils

SQL_VECTOR_CANDIDATE_MULTIPLIER = 4
PIPELINE_SUBQUERY_LIMIT = 5
RERANK_CANDIDATE_LIMIT = 16
APPROX_CHARS_PER_TOKEN = 4
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


@dataclass(frozen=True)
class RetrievalRunResult:
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
    project_service.get_project(db, auth, project_id)
    started = perf_counter()
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
    reranked, reranker = _rerank_results(settings, payload.query, plan, fused_results)
    assembled, context = assemble_context_results(settings, reranked, top_k=payload.top_k)
    total_latency = int((perf_counter() - started) * 1000)
    quality = _quality_report(
        selected=assembled,
        candidate_count=len(fused_results),
        total_latency_ms=total_latency,
        reranker_used=reranker.enabled and not reranker.fallback_used,
        token_count=context.token_count,
    )
    primary = diagnostics[0] if diagnostics else _diagnostics(
        settings,
        started,
        index_name=None,
        index_available=False,
        candidate_count=0,
        used_sql_vector_search=False,
        fallback_path_used=False,
        fallback_reason=None,
    )
    diagnostic_payload = primary.model_dump()
    diagnostic_payload.update(
        {
            "candidate_count": sum(item.candidate_count for item in diagnostics),
            "query_latency_ms": total_latency,
            "used_sql_vector_search": any(item.used_sql_vector_search for item in diagnostics),
            "fallback_path_used": any(item.fallback_path_used for item in diagnostics),
            "fallback_reason": _combine_fallback_reasons(diagnostics),
            "query_plan": plan,
            "reranker": reranker,
            "context": context,
            "quality_report": quality,
        }
    )
    pipeline_diagnostics = RetrievalDiagnosticsRead.model_validate(diagnostic_payload)
    return RetrievalSearchResult(diagnostics=pipeline_diagnostics, results=assembled)


def _retrieve_single_query_search(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> RetrievalSearchResult:
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

    query_embedding = embedding_service.embed_text(settings, payload.query)
    should_use_sql = _should_use_sql_vector_search(db, settings)
    if should_use_sql:
        try:
            results, candidate_count = _retrieve_with_sql_vector_search(
                db,
                auth,
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
    candidate_limit = max(payload.top_k, payload.top_k * SQL_VECTOR_CANDIDATE_MULTIPLIER)
    stmt = (
        select(EvidenceChunk, EvidenceSource, distance)
        .join(EvidenceSource, EvidenceSource.id == EvidenceChunk.source_id)
        .where(*conditions, EvidenceChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(candidate_limit)
    )
    rows = db.execute(stmt).all()
    query_terms = _term_set(payload.query)
    scored: list[EvidenceRetrievalResultRead] = []
    for chunk, source, raw_distance in rows:
        distance_value = float(raw_distance or 0)
        semantic_score = max(0.0, 1.0 - distance_value)
        keyword_score = _keyword_score(query_terms, chunk.text)
        score = _combined_score(payload.mode, semantic_score, keyword_score)
        if score <= 0:
            continue
        scored.append(_serialize_result(chunk, source, score, semantic_score, keyword_score))

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
        query_embedding = embedding_service.embed_text(settings, payload.query)
    candidates = _load_candidates(db, auth, project_id, payload)
    return (
        _score_candidates(
            query=payload.query,
            query_embedding=query_embedding,
            candidates=candidates,
            mode=payload.mode,
            top_k=payload.top_k,
        ),
        len(candidates),
    )


def _plan_query(query: str) -> RetrievalQueryPlanRead:
    terms = _term_set(query)
    raw_terms = _raw_term_set(query)
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

    target_entities = _target_entities(query)
    broad = (
        len(terms) >= 8
        or " and " in lowered
        or " or " in lowered
        or any(
            marker in raw_terms
            for marker in {"which", "what", "compare", "strongest", "missing"}
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
    subqueries = _dedupe_strings([item for item in subqueries if item])[:PIPELINE_SUBQUERY_LIMIT]
    return RetrievalQueryPlanRead(
        intent=intent,
        target_entities=target_entities,
        needed_evidence_types=needed_evidence_types,
        subqueries=subqueries,
        decomposed=len(subqueries) > 1,
    )


def _target_entities(query: str) -> list[str]:
    matches = re.findall(r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,2}\b", query)
    ignored = {"What", "Which", "Why", "How", "Should", "Can", "The", "A", "An"}
    return _dedupe_strings([match for match in matches if match.split()[0] not in ignored])[:6]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            deduped.append(value.strip())
    return deduped


def _fuse_results(
    results: list[EvidenceRetrievalResultRead],
) -> list[EvidenceRetrievalResultRead]:
    by_chunk: dict[uuid.UUID, EvidenceRetrievalResultRead] = {}
    match_counts: defaultdict[uuid.UUID, int] = defaultdict(int)
    for result in results:
        match_counts[result.chunk_id] += 1
        existing = by_chunk.get(result.chunk_id)
        if existing is None or result.score > existing.score:
            by_chunk[result.chunk_id] = result
    fused: list[EvidenceRetrievalResultRead] = []
    for result in by_chunk.values():
        metadata = dict(result.metadata)
        metadata["retrieval_match_count"] = match_counts[result.chunk_id]
        fused.append(result.model_copy(update={"metadata": metadata}))
    return sorted(fused, key=lambda item: (item.score, item.created_at), reverse=True)


def _rerank_results(
    settings: Settings,
    query: str,
    plan: RetrievalQueryPlanRead,
    results: list[EvidenceRetrievalResultRead],
) -> tuple[list[EvidenceRetrievalResultRead], RetrievalRerankerDiagnosticsRead]:
    if not settings.retrieval_reranking_enabled:
        ranked = [
            result.model_copy(
                update={
                    "rerank_score": result.score,
                    "final_rank": index + 1,
                    "selection_reason": "Reranking disabled; original retrieval score used.",
                }
            )
            for index, result in enumerate(results)
        ]
        return ranked, RetrievalRerankerDiagnosticsRead(
            enabled=False,
            provider=settings.retrieval_reranker_provider,
        )

    fallback_reason: str | None = None
    ordered_ids: list[uuid.UUID] | None = None
    if settings.retrieval_reranker_provider == "litellm" and not settings.should_use_llm_stub:
        try:
            ordered_ids = _litellm_rerank_order(settings, query, plan, results)
        except Exception as exc:
            fallback_reason = f"LiteLLM reranker failed: {exc}"

    ranked = _deterministic_rerank(query, plan, results, ordered_ids=ordered_ids)
    return ranked, RetrievalRerankerDiagnosticsRead(
        enabled=True,
        provider=settings.retrieval_reranker_provider,
        fallback_used=fallback_reason is not None,
        fallback_reason=fallback_reason,
    )


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
                "of chunk_id strings. "
                "Prefer specific, source-backed evidence and reject generic or weak snippets."
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
        provider_rank_boost = 0.0
        if result.chunk_id in explicit_rank:
            provider_rank_boost = max(0.0, 0.25 - (explicit_rank[result.chunk_id] * 0.01))
        rerank_score = (
            result.score * 0.55
            + overlap * 0.18
            + type_overlap * 0.08
            + min(credibility, 1.0) * 0.08
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


def assemble_context_results(
    settings: Settings,
    results: list[EvidenceRetrievalResultRead],
    *,
    top_k: int | None = None,
) -> tuple[list[EvidenceRetrievalResultRead], RetrievalContextDiagnosticsRead]:
    selected: list[EvidenceRetrievalResultRead] = []
    per_source: defaultdict[uuid.UUID, int] = defaultdict(int)
    token_count = 0
    deduped_count = 0
    dropped_count = 0
    max_results = top_k or len(results)
    signatures: list[set[str]] = []
    for result in _diversify_context_candidates(results):
        score = result.rerank_score if result.rerank_score is not None else result.score
        if score < settings.retrieval_min_context_score:
            dropped_count += 1
            continue
        if per_source[result.source_id] >= settings.retrieval_max_chunks_per_source:
            dropped_count += 1
            continue
        terms = _signature_terms(result.text)
        if any(_jaccard(terms, existing) >= 0.88 for existing in signatures):
            deduped_count += 1
            continue
        estimated_tokens = _estimate_tokens(result.text)
        if selected and token_count + estimated_tokens > settings.retrieval_context_token_budget:
            dropped_count += 1
            continue
        selected.append(
            result.model_copy(
                update={
                    "context_included": True,
                    "selection_reason": (
                        _context_selection_reason(result, per_source[result.source_id])
                    ),
                }
            )
        )
        signatures.append(terms)
        per_source[result.source_id] += 1
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
        min_context_score=settings.retrieval_min_context_score,
    )
    return selected, context


def _diversify_context_candidates(
    results: list[EvidenceRetrievalResultRead],
) -> list[EvidenceRetrievalResultRead]:
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


def _context_selection_reason(result: EvidenceRetrievalResultRead, prior_source_count: int) -> str:
    base = result.selection_reason or "Selected for synthesis context."
    if prior_source_count == 0:
        return f"{base} Prioritized for source diversity."
    return base


def _quality_report(
    *,
    selected: list[EvidenceRetrievalResultRead],
    candidate_count: int,
    total_latency_ms: int,
    reranker_used: bool,
    token_count: int,
) -> RetrievalQualityReportRead:
    source_count = len({result.source_id for result in selected})
    selected_count = len(selected)
    recall_proxy = min(1.0, selected_count / max(candidate_count, 1))
    precision_proxy = (
        sum(1 for result in selected if (result.rerank_score or result.score) >= 0.35)
        / max(selected_count, 1)
    )
    citation_coverage_proxy = (
        sum(1 for result in selected if result.source_id and result.chunk_id)
        / max(selected_count, 1)
    )
    if source_count >= 3 and selected_count >= 3:
        recall_proxy = max(recall_proxy, 0.75)
    return RetrievalQualityReportRead(
        recall_proxy=round(recall_proxy, 3),
        precision_proxy=round(precision_proxy, 3),
        citation_coverage_proxy=round(citation_coverage_proxy, 3),
        unsupported_claim_count=0,
        average_retrieval_latency_ms=total_latency_ms,
        reranker_used=reranker_used,
        context_token_count=token_count,
    )


def _combine_fallback_reasons(diagnostics: list[RetrievalDiagnosticsRead]) -> str | None:
    reasons = _dedupe_strings(
        [item.fallback_reason for item in diagnostics if item.fallback_reason]
    )
    return "; ".join(reasons) if reasons else None


def _metadata_float(metadata: dict[str, object], key: str) -> float | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _freshness_boost(result: EvidenceRetrievalResultRead) -> float:
    created_at = result.created_at
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


def _signature_terms(text_value: str) -> set[str]:
    terms = list(_term_set(text_value))
    return set(terms[:120])


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _estimate_tokens(text_value: str) -> int:
    return max(1, int(len(text_value) / APPROX_CHARS_PER_TOKEN))


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
    query: str,
    query_embedding: list[float] | None,
    candidates: list[RetrievalCandidate],
    mode: RetrievalMode,
    top_k: int,
) -> list[EvidenceRetrievalResultRead]:
    query_terms = _term_set(query)
    scored: list[EvidenceRetrievalResultRead] = []
    for candidate in candidates:
        semantic_score = 0.0
        if query_embedding is not None:
            semantic_score = embedding_service.cosine_similarity(
                query_embedding,
                candidate.chunk.embedding,
            )
        keyword_score = _keyword_score(query_terms, candidate.chunk.text)
        score = _combined_score(mode, semantic_score, keyword_score)
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
    metadata.update(
        {
            "source_classification": source.classification,
            "source_credibility_score": float(source.credibility_score)
            if source.credibility_score is not None
            else None,
            "source_date": source.source_date.isoformat() if source.source_date else None,
            "source_ingested_at": source.ingested_at.isoformat() if source.ingested_at else None,
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


def _combined_score(mode: RetrievalMode, semantic_score: float, keyword_score: float) -> float:
    if mode == "semantic":
        return semantic_score
    if mode == "keyword":
        return keyword_score
    return (semantic_score * 0.65) + (keyword_score * 0.35)


def _keyword_score(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    text_terms = _term_set(text)
    if not text_terms:
        return 0.0
    overlap = query_terms & text_terms
    if not overlap:
        return 0.0
    return len(overlap) / len(query_terms)


def _term_set(text: str) -> set[str]:
    return {term for term in _raw_term_set(text) if term not in STOPWORDS}


def _raw_term_set(text: str) -> set[str]:
    return {
        term
        for term in (part.strip(".,:;!?()[]{}\"'").casefold() for part in text.split())
        if len(term) > 2
    }


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


def _diagnostics(
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
