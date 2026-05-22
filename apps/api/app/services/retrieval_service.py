import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.prompts import EVIDENCE_RETRIEVAL_PROMPT_VERSION
from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import AIRun, AIStep, EvidenceChunk, EvidenceSource
from app.schemas.evidence import (
    EvidenceRetrievalResultRead,
    EvidenceRetrieveCreate,
    RetrievalMode,
)
from app.services import ai_run_service, embedding_service, project_service


@dataclass(frozen=True)
class RetrievalRunResult:
    run: AIRun
    step: AIStep
    mode: RetrievalMode
    query: str
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
        model_provider="internal",
        model_name=settings.embedding_model,
    )
    step = ai_run_service.start_step(
        db,
        run,
        step_name=f"{payload.mode}_retrieval",
        input_json=payload.model_dump(mode="json"),
    )
    started = perf_counter()

    try:
        query_embedding = embedding_service.embed_text(settings, payload.query)
        candidates = _load_candidates(db, auth, project_id, payload)
        results = _score_candidates(
            query=payload.query,
            query_embedding=query_embedding,
            candidates=candidates,
            mode=payload.mode,
            top_k=payload.top_k,
        )
        latency_ms = int((perf_counter() - started) * 1000)
        step = ai_run_service.complete_step(
            db,
            step,
            output_json={
                "result_count": len(results),
                "results": [result.model_dump(mode="json") for result in results],
            },
            latency_ms=latency_ms,
            tokens=None,
            cost=Decimal("0"),
        )
        run = ai_run_service.complete_run(
            db,
            run,
            output_summary=f"Retrieved {len(results)} chunks for query.",
            total_tokens=None,
            total_cost=Decimal("0"),
            model_provider="internal",
            model_name=settings.embedding_model,
        )
        return RetrievalRunResult(
            run=run,
            step=step,
            mode=payload.mode,
            query=payload.query,
            results=results,
        )
    except Exception as exc:
        ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        ai_run_service.fail_run(db, run, error=str(exc))
        raise


def _load_candidates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
) -> list[RetrievalCandidate]:
    stmt = (
        select(EvidenceChunk, EvidenceSource)
        .join(EvidenceSource, EvidenceSource.id == EvidenceChunk.source_id)
        .where(
            EvidenceChunk.workspace_id == auth.workspace_id,
            EvidenceChunk.project_id == project_id,
            EvidenceSource.workspace_id == auth.workspace_id,
            EvidenceSource.project_id == project_id,
            EvidenceSource.ingestion_status == "ready",
        )
    )
    if payload.source_types:
        stmt = stmt.where(EvidenceSource.source_type.in_(payload.source_types))
    if payload.created_after is not None:
        stmt = stmt.where(EvidenceSource.created_at >= payload.created_after)
    if payload.created_before is not None:
        stmt = stmt.where(EvidenceSource.created_at <= payload.created_before)

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
    if payload.competitor_id is not None and metadata.get("competitor_id") != str(
        payload.competitor_id
    ):
        return False
    if payload.assumption_id is not None and metadata.get("assumption_id") != str(
        payload.assumption_id
    ):
        return False
    return True


def _matches_freshness(source: EvidenceSource, freshness_days: int | None) -> bool:
    if freshness_days is None:
        return True
    reference = source.source_date or source.ingested_at or source.created_at
    return reference >= datetime.now(UTC) - timedelta(days=freshness_days)


def _score_candidates(
    *,
    query: str,
    query_embedding: list[float],
    candidates: list[RetrievalCandidate],
    mode: RetrievalMode,
    top_k: int,
) -> list[EvidenceRetrievalResultRead]:
    query_terms = _term_set(query)
    scored: list[EvidenceRetrievalResultRead] = []
    for candidate in candidates:
        semantic_score = embedding_service.cosine_similarity(
            query_embedding,
            candidate.chunk.embedding,
        )
        keyword_score = _keyword_score(query_terms, candidate.chunk.text)
        score = _combined_score(mode, semantic_score, keyword_score)
        if score <= 0:
            continue
        scored.append(
            EvidenceRetrievalResultRead(
                source_id=candidate.source.id,
                chunk_id=candidate.chunk.id,
                title=candidate.source.title,
                url=candidate.source.url,
                source_type=candidate.source.source_type,
                chunk_index=candidate.chunk.chunk_index,
                text=candidate.chunk.text,
                score=round(score, 6),
                semantic_score=round(semantic_score, 6),
                keyword_score=round(keyword_score, 6),
                metadata=candidate.chunk.chunk_metadata or {},
                created_at=candidate.chunk.created_at,
            )
        )

    scored.sort(key=lambda result: (result.score, result.created_at), reverse=True)
    return scored[:top_k]


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
