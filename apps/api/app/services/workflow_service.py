"""Workflow run lookup services for AI observability screens."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthContext, record_cross_tenant_access_attempt
from app.core.config import Settings
from app.db.models import AIRun, EvidenceChunk, EvidenceSource
from app.features.retrieval.security_policy import RetrievalSecurityPolicy
from app.schemas.workflows import WorkflowRunRead
from app.services import project_service


def get_run(db: Session, auth: AuthContext, run_id: uuid.UUID) -> AIRun:
    """Load one AI run with its recorded steps for trace inspection."""

    run = db.scalar(
        select(AIRun)
        .where(AIRun.id == run_id, AIRun.workspace_id == auth.workspace_id)
        .options(selectinload(AIRun.steps))
    )
    if run is None:
        record_cross_tenant_access_attempt(db, auth, reason_code="workflow_run_scope_denied")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    return run


def list_project_runs(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    limit: int,
) -> list[AIRun]:
    """List recent AI runs for a project, including step-level traces."""

    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(AIRun)
            .where(AIRun.workspace_id == auth.workspace_id, AIRun.project_id == project_id)
            .options(selectinload(AIRun.steps))
            .order_by(AIRun.created_at.desc())
            .limit(limit)
        )
    )


def serialize_run(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    run: AIRun,
) -> WorkflowRunRead:
    """Serialize a trace without replaying evidence that has since been revoked."""
    allowed_pairs, allowed_source_ids, trace_source_ids = _trace_evidence_permissions(
        db,
        auth,
        settings,
        run,
    )
    steps = []
    for step in run.steps:
        output_json = (
            _filter_trace_evidence(
                step.output_json,
                allowed_pairs=allowed_pairs,
                allowed_source_ids=allowed_source_ids,
            )
            if step.output_json is not None
            else None
        )
        steps.append(
            {
                **step.__dict__,
                "output_json": output_json if isinstance(output_json, dict) else None,
            }
        )
    return WorkflowRunRead.model_validate(
        {
            **run.__dict__,
            "output_summary": (
                run.output_summary
                if trace_source_ids.issubset(allowed_source_ids)
                else None
            ),
            "steps": steps,
        }
    )


def _trace_evidence_permissions(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    run: AIRun,
) -> tuple[set[tuple[uuid.UUID, uuid.UUID]], set[uuid.UUID], set[uuid.UUID]]:
    if run.project_id is None:
        return set(), set(), set()
    evidence_pairs: set[tuple[uuid.UUID, uuid.UUID | None]] = set()
    for step in run.steps:
        evidence_pairs.update(_trace_evidence_pairs(step.input_json))
        evidence_pairs.update(_trace_evidence_pairs(step.output_json))
    if not evidence_pairs:
        return set(), set(), set()
    source_ids = {source_id for source_id, _ in evidence_pairs}
    chunk_ids = {chunk_id for _, chunk_id in evidence_pairs if chunk_id is not None}
    rows = db.execute(
        select(EvidenceChunk, EvidenceSource)
        .join(EvidenceSource, EvidenceSource.id == EvidenceChunk.source_id)
        .where(
            EvidenceChunk.workspace_id == auth.workspace_id,
            EvidenceChunk.project_id == run.project_id,
            EvidenceSource.workspace_id == auth.workspace_id,
            EvidenceSource.project_id == run.project_id,
            EvidenceSource.id.in_(source_ids),
            (
                EvidenceChunk.id.in_(chunk_ids)
                if chunk_ids
                else EvidenceChunk.source_id.in_(source_ids)
            ),
        )
    ).all()
    policy = RetrievalSecurityPolicy.for_auth(
        auth,
        minimum_source_trust_score=settings.retrieval_min_source_trust_score,
    )
    allowed_pairs = {
        (source.id, chunk.id)
        for chunk, source in rows
        if policy.allows(source=source, chunk=chunk)
    }
    return (
        allowed_pairs,
        {source_id for source_id, _ in allowed_pairs},
        source_ids,
    )


def _trace_evidence_pairs(
    values: object,
) -> set[tuple[uuid.UUID, uuid.UUID | None]]:
    pairs: set[tuple[uuid.UUID, uuid.UUID | None]] = set()
    if isinstance(values, dict):
        source_id = _uuid_value(values.get("source_id"))
        chunk_id = _uuid_value(values.get("chunk_id"))
        if source_id is not None:
            pairs.add((source_id, chunk_id))
        for value in values.values():
            pairs.update(_trace_evidence_pairs(value))
    elif isinstance(values, list) or isinstance(values, tuple):
        for value in values:
            pairs.update(_trace_evidence_pairs(value))
    return pairs


def _filter_trace_evidence(
    value: object,
    *,
    allowed_pairs: set[tuple[uuid.UUID, uuid.UUID]],
    allowed_source_ids: set[uuid.UUID],
) -> object:
    if isinstance(value, list):
        filtered = [
            _filter_trace_evidence(
                item,
                allowed_pairs=allowed_pairs,
                allowed_source_ids=allowed_source_ids,
            )
            for item in value
        ]
        return [item for item in filtered if item is not _DROP_TRACE_EVIDENCE]
    if not isinstance(value, dict):
        return value
    source_id = _uuid_value(value.get("source_id"))
    chunk_id = _uuid_value(value.get("chunk_id"))
    if source_id is not None:
        allowed = (
            (source_id, chunk_id) in allowed_pairs
            if chunk_id is not None
            else source_id in allowed_source_ids
        )
        if not allowed:
            return _DROP_TRACE_EVIDENCE
    filtered_dict = {
        key: _filter_trace_evidence(
            item,
            allowed_pairs=allowed_pairs,
            allowed_source_ids=allowed_source_ids,
        )
        for key, item in value.items()
    }
    return {
        key: item for key, item in filtered_dict.items() if item is not _DROP_TRACE_EVIDENCE
    }


def _uuid_value(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


_DROP_TRACE_EVIDENCE = object()
