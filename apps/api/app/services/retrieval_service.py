import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter

from sqlalchemy import Select, cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.ai.prompts import EVIDENCE_RETRIEVAL_PROMPT_VERSION
from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import AIRun, AIStep, EvidenceChunk, EvidenceSource
from app.schemas.evidence import (
    EvidenceRetrievalResultRead,
    EvidenceRetrieveCreate,
    RetrievalDiagnosticsRead,
    RetrievalMode,
)
from app.services import ai_run_service, embedding_service, project_service

SQL_VECTOR_CANDIDATE_MULTIPLIER = 4


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
        step = ai_run_service.complete_step(
            db,
            step,
            output_json={
                "result_count": len(search.results),
                "diagnostics": search.diagnostics.model_dump(mode="json"),
                "results": [result.model_dump(mode="json") for result in search.results],
            },
            latency_ms=search.diagnostics.query_latency_ms,
            tokens=None,
            cost=Decimal("0"),
        )
        run = ai_run_service.complete_run(
            db,
            run,
            output_summary=f"Retrieved {len(search.results)} chunks for query.",
            total_tokens=None,
            total_cost=Decimal("0"),
            model_provider=settings.embedding_provider,
            model_name=settings.embedding_model,
        )
        return RetrievalRunResult(
            run=run,
            step=step,
            mode=payload.mode,
            query=payload.query,
            diagnostics=search.diagnostics,
            results=search.results,
        )
    except Exception as exc:
        ai_run_service.fail_step(db, step, error=str(exc))
        ai_run_service.fail_run(db, run, error=str(exc))
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
        metadata=chunk.chunk_metadata or {},
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
