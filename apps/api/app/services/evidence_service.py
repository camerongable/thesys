"""Evidence ingestion, extraction, chunking, embedding, and source serialization."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from time import perf_counter
from typing import Any

import httpx
from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.ai.prompts import EVIDENCE_INGESTION_PROMPT_VERSION
from app.common import metadata as metadata_utils
from app.core.auth import AuthContext
from app.core.config import Settings
from app.core.security import (
    SecurityValidationError,
    validate_upload,
    validate_url_fetch_target,
    validate_url_response_content_type,
)
from app.db.models import EvidenceChunk, EvidenceSource
from app.features.evidence import extraction as evidence_extraction
from app.schemas.evidence import EvidenceNoteCreate, EvidenceUrlCreate
from app.services import (
    ai_run_service,
    embedding_service,
    governance_service,
    multimodal_extraction_service,
    object_storage_service,
    project_service,
    source_provenance_service,
)
from app.services.common import workflow as workflow_utils

ParsedSource = evidence_extraction.ParsedSource
_chunk_text = evidence_extraction.chunk_text
_classify = evidence_extraction.classify_text
_decode_bytes = evidence_extraction.decode_bytes
_direct_response_metadata = evidence_extraction.direct_response_metadata
_file_metadata = evidence_extraction.file_metadata
_image_upload_metadata = evidence_extraction.image_upload_metadata
_normalize_text = evidence_extraction.normalize_text
_parse_html = evidence_extraction.parse_html
_pdf_ocr_fallback_metadata = evidence_extraction.pdf_ocr_fallback_metadata
_pdf_text_metadata = evidence_extraction.pdf_text_metadata
_preview = evidence_extraction.preview_text
_summarize = evidence_extraction.summarize_text
_text_upload_metadata = evidence_extraction.text_upload_metadata
_tokens = evidence_extraction.tokens
_truncate = evidence_extraction.truncate_text


class EvidenceIngestionError(RuntimeError):
    pass


class EvidenceSecurityError(EvidenceIngestionError):
    pass


@dataclass(frozen=True)
class ReembedFailure:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    error: str


@dataclass(frozen=True)
class ReembedResult:
    dry_run: bool
    scope: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_version: str
    scanned_count: int
    eligible_count: int
    skipped_count: int
    reembedded_count: int
    failed_count: int
    failures: list[ReembedFailure]


def list_sources(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[EvidenceSource]:
    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
            )
            .options(selectinload(EvidenceSource.chunks))
            .order_by(EvidenceSource.created_at.desc())
        )
    )


def get_source(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
) -> EvidenceSource:
    source = db.scalar(
        select(EvidenceSource)
        .where(
            EvidenceSource.id == source_id,
            EvidenceSource.workspace_id == auth.workspace_id,
            EvidenceSource.project_id == project_id,
        )
        .options(selectinload(EvidenceSource.chunks))
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence source not found.",
        )
    return source


def add_note_source(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceNoteCreate,
) -> EvidenceSource:
    project_service.get_project(db, auth, project_id)
    source = EvidenceSource(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type=payload.source_type,
        title=payload.title.strip(),
        raw_text=_normalize_text(payload.text),
        source_date=payload.source_date,
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=source.raw_text or "",
        title=source.title,
        content_type="text/plain",
    )


def add_url_source(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceUrlCreate,
) -> EvidenceSource:
    """Fetch, validate, dedupe, and ingest a user-provided URL source."""
    project_service.get_project(db, auth, project_id)
    canonical_url = source_provenance_service.canonicalize_url(str(payload.url))
    existing = _find_ready_url_source(db, auth, project_id, canonical_url)
    if existing is not None:
        return get_source(db, auth, project_id, existing.id)

    source = EvidenceSource(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="url",
        title=payload.title.strip() if payload.title else None,
        url=canonical_url,
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    try:
        parsed = _fetch_url(settings, str(payload.url))
    except EvidenceSecurityError as exc:
        _mark_source_failed(
            db,
            source,
            str(exc),
            metadata=source_provenance_service.fetch_failure_metadata(str(exc)),
        )
        _record_ingestion_security_event(
            db,
            auth,
            project_id=project_id,
            source_id=source.id,
            event_type="evidence_url_fetch_blocked",
            summary="Blocked unsafe URL evidence ingestion.",
            reason=str(exc),
            metadata={"url": str(payload.url)},
        )
        raise EvidenceIngestionError("URL evidence ingestion failed.") from exc
    except Exception as exc:
        _mark_source_failed(
            db,
            source,
            str(exc),
            metadata=source_provenance_service.fetch_failure_metadata(str(exc)),
        )
        raise EvidenceIngestionError("URL evidence ingestion failed.") from exc

    if parsed.metadata and isinstance(parsed.metadata.get("canonical_url"), str):
        source.url = parsed.metadata["canonical_url"]
    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=parsed.text,
        title=source.title or parsed.title or str(payload.url),
        content_type=parsed.content_type,
        metadata=parsed.metadata,
    )


def add_discovered_url_source(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    *,
    url: str,
    title: str | None,
    fallback_text: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EvidenceSource:
    """Fetch and ingest an approved discovery URL into the project evidence graph."""
    project_service.get_project(db, auth, project_id)
    canonical_url = source_provenance_service.canonicalize_url(url)
    existing = _find_ready_url_source(db, auth, project_id, canonical_url)
    if existing is not None:
        if metadata:
            existing.source_metadata = _merge_metadata(existing.source_metadata or {}, metadata)
            _merge_source_chunk_metadata(db, existing, metadata)
            db.commit()
        return get_source(db, auth, project_id, existing.id)

    source = EvidenceSource(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="url",
        title=title.strip() if title else None,
        url=canonical_url,
        source_date=datetime.now(UTC),
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    try:
        parsed = _fetch_url(settings, canonical_url)
    except EvidenceSecurityError as exc:
        _mark_source_failed(
            db,
            source,
            str(exc),
            metadata=source_provenance_service.fetch_failure_metadata(str(exc)),
        )
        _record_ingestion_security_event(
            db,
            auth,
            project_id=project_id,
            source_id=source.id,
            event_type="discovered_source_fetch_blocked",
            summary="Blocked unsafe discovered-source ingestion.",
            reason=str(exc),
            metadata={"url": url, **(metadata or {})},
        )
        raise EvidenceIngestionError("URL evidence ingestion failed.") from exc
    except Exception as exc:
        if fallback_text and _normalize_text(fallback_text):
            fallback_metadata = _merge_metadata(
                metadata or {},
                {
                    "remote_fetch_error": str(exc),
                    "used_discovery_snapshot": True,
                    **source_provenance_service.fetch_failure_metadata(str(exc)),
                },
            )
            return _process_source_text(
                db,
                auth,
                settings,
                source,
                text=fallback_text,
                title=source.title or title or url,
                content_type="text/plain",
                metadata=fallback_metadata,
            )
        _mark_source_failed(
            db,
            source,
            str(exc),
            metadata=source_provenance_service.fetch_failure_metadata(str(exc)),
        )
        raise EvidenceIngestionError(f"URL evidence ingestion failed: {exc}") from exc

    success_metadata = _merge_metadata(metadata or {}, parsed.metadata)
    if parsed.metadata and isinstance(parsed.metadata.get("canonical_url"), str):
        source.url = parsed.metadata["canonical_url"]
    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=parsed.text,
        title=source.title or parsed.title or url,
        content_type=parsed.content_type,
        metadata=success_metadata,
    )


def add_discovered_url_snapshot(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    *,
    url: str,
    title: str | None,
    text: str,
) -> EvidenceSource:
    """Ingest a reviewed discovery candidate without fetching the remote page yet."""
    project_service.get_project(db, auth, project_id)
    canonical_url = source_provenance_service.canonicalize_url(url)
    source = EvidenceSource(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="url",
        title=title.strip() if title else None,
        url=canonical_url,
        raw_text=_normalize_text(text),
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=source.raw_text or text,
        title=source.title or canonical_url,
        content_type="text/plain",
        metadata={
            "canonical_url": canonical_url,
            "domain": source_provenance_service.source_domain(canonical_url),
            "snapshot_ingested_at": datetime.now(UTC).isoformat(),
            "used_discovery_snapshot": True,
        },
    )


def add_file_source(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    upload: UploadFile,
) -> EvidenceSource:
    """Validate and ingest an uploaded evidence file."""
    project_service.get_project(db, auth, project_id)
    body = upload.file.read()
    try:
        upload_validation = validate_upload(
            filename=upload.filename,
            content_type=upload.content_type,
            body=body,
            settings=settings,
        )
    except SecurityValidationError as exc:
        _record_ingestion_security_event(
            db,
            auth,
            project_id=project_id,
            source_id=None,
            event_type="evidence_upload_rejected",
            summary="Rejected unsafe evidence upload.",
            reason=exc.reason,
            metadata={
                "filename": upload.filename,
                "content_type": upload.content_type,
                "size_bytes": len(body),
            },
        )
        if "upload limit" in exc.reason:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=exc.reason,
            ) from exc
        raise EvidenceIngestionError("File evidence ingestion failed.") from exc

    filename = upload_validation.filename
    content_type = upload_validation.content_type
    storage_key = (
        f"workspaces/{auth.workspace_id}/projects/{project_id}/evidence/{uuid.uuid4()}-{filename}"
    )
    object_storage_service.put_object(
        settings,
        key=storage_key,
        body=body,
        content_type=content_type,
    )

    source = EvidenceSource(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="file",
        title=filename,
        object_storage_key=storage_key,
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    try:
        parsed = _parse_file(
            settings=settings,
            filename=filename,
            content_type=content_type,
            body=body,
        )
    except Exception as exc:
        _mark_source_failed(db, source, str(exc))
        raise EvidenceIngestionError("File evidence ingestion failed.") from exc

    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=parsed.text,
        title=parsed.title or filename,
        content_type=parsed.content_type or content_type,
        metadata=parsed.metadata,
    )


def reprocess_source(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
) -> EvidenceSource:
    source = get_source(db, auth, project_id, source_id)
    if not source.raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source has no parsed text to reprocess.",
        )
    source.ingestion_status = "processing"
    source.ingestion_error = None
    db.commit()
    db.refresh(source)
    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=source.raw_text,
        title=source.title,
        content_type=None,
    )


def delete_source(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
) -> None:
    source = get_source(db, auth, project_id, source_id)
    db.delete(source)
    db.commit()


def reembed_evidence(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    *,
    dry_run: bool,
    force: bool,
    scope: str,
) -> ReembedResult:
    """Refresh embeddings when provider/model/dimension/version settings change."""
    project_service.get_project(db, auth, project_id)
    stmt = select(EvidenceChunk).where(EvidenceChunk.workspace_id == auth.workspace_id)
    if scope == "project":
        stmt = stmt.where(EvidenceChunk.project_id == project_id)
    elif scope != "workspace":
        raise ValueError(f"Unsupported re-embedding scope: {scope}")

    chunks = list(db.scalars(stmt.order_by(EvidenceChunk.created_at.asc())))
    eligible = [chunk for chunk in chunks if force or _chunk_needs_reembedding(chunk, settings)]
    failures: list[ReembedFailure] = []
    reembedded_count = 0

    if not dry_run:
        for chunk in eligible:
            try:
                embedding = embedding_service.embed_text_with_metadata_cached(
                    db,
                    auth,
                    settings,
                    chunk.text,
                    project_id=chunk.project_id,
                )
                chunk.embedding = embedding.vector
                chunk.embedding_provider = embedding.provider
                chunk.embedding_model = embedding.model
                chunk.embedding_dimension = embedding.dimension
                chunk.embedding_version = embedding.version
                chunk.embedded_at = embedding.embedded_at
                chunk.embedding_error = None
                chunk.chunk_metadata = _merge_metadata(
                    chunk.chunk_metadata or {},
                    embedding_service.embedding_metadata(settings),
                )
                reembedded_count += 1
            except Exception as exc:
                message = str(exc)
                chunk.embedding_error = message
                failures.append(
                    ReembedFailure(
                        chunk_id=chunk.id,
                        source_id=chunk.source_id,
                        error=message,
                    )
                )
        db.commit()

    return ReembedResult(
        dry_run=dry_run,
        scope=scope,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        embedding_version=settings.embedding_version,
        scanned_count=len(chunks),
        eligible_count=len(eligible),
        skipped_count=len(chunks) - len(eligible),
        reembedded_count=reembedded_count,
        failed_count=len(failures),
        failures=failures,
    )


def serialize_source(source: EvidenceSource) -> dict[str, Any]:
    return {
        "id": source.id,
        "project_id": source.project_id,
        "source_type": source.source_type,
        "title": source.title,
        "url": source.url,
        "object_storage_key": source.object_storage_key,
        "summary": source.summary,
        "source_date": source.source_date,
        "ingested_at": source.ingested_at,
        "classification": source.classification,
        "credibility_score": source.credibility_score,
        "metadata": source.source_metadata or {},
        "ingestion_status": source.ingestion_status,
        "ingestion_error": source.ingestion_error,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
        "chunk_count": len(source.chunks),
        "text_preview": _preview(source.raw_text),
    }


def _chunk_needs_reembedding(chunk: EvidenceChunk, settings: Settings) -> bool:
    return (
        chunk.embedding is None
        or chunk.embedding_provider != settings.embedding_provider
        or chunk.embedding_model != settings.embedding_model
        or chunk.embedding_dimension != settings.embedding_dimension
        or chunk.embedding_version != settings.embedding_version
    )


def _process_source_text(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    source: EvidenceSource,
    *,
    text: str,
    title: str | None,
    content_type: str | None,
    metadata: dict[str, Any] | None = None,
) -> EvidenceSource:
    """Normalize extracted text, build chunks, embed, and persist provenance.

    This is the single path for notes, URLs, files, discovery snapshots, and
    multimodal extraction so chunk metadata stays consistent across source
    types.
    """
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="evidence_ingestion",
        prompt_version=EVIDENCE_INGESTION_PROMPT_VERSION,
        input_summary=(title or source.url or str(source.id))[:500],
        project_id=source.project_id,
        model_provider=settings.embedding_provider,
        model_name=settings.embedding_model,
    )
    step = ai_run_service.start_step(
        db,
        run,
        step_name="parse_chunk_embed",
        input_json={
            "source_id": str(source.id),
            "source_type": source.source_type,
            "content_type": content_type,
        },
    )
    started = perf_counter()

    try:
        normalized = _normalize_text(text)
        if not normalized:
            raise EvidenceIngestionError("Evidence source did not contain extractable text.")
        if len(normalized) > settings.max_extracted_text_chars:
            raise EvidenceIngestionError(
                f"Extracted text exceeds {settings.max_extracted_text_chars} character limit."
            )

        chunks = _chunk_text(normalized)
        if not chunks:
            raise EvidenceIngestionError("Evidence source did not produce chunks.")

        content_hash = source_provenance_service.content_hash(normalized)
        base_metadata = _merge_metadata(
            {
                "content_type": content_type,
                "content_hash": content_hash,
                "domain": source_provenance_service.source_domain(source.url),
            },
            metadata,
        )
        extraction_method = str(
            base_metadata.get("extraction_method")
            or base_metadata.get("pdf_text_extraction")
            or base_metadata.get("text_extraction")
            or "normalized_text"
        )
        processed_metadata = _merge_metadata(
            source.source_metadata or {},
            _merge_metadata(
                base_metadata,
                source_provenance_service.extraction_artifacts(
                    text=text,
                    metadata=base_metadata,
                    extraction_method=extraction_method,
                ),
            ),
        )
        prompt_markers = source_provenance_service.detect_prompt_injection_markers(normalized)
        if prompt_markers:
            processed_metadata["prompt_injection_markers"] = prompt_markers

        if source.source_type == "url":
            duplicate = _find_ready_source_by_content_hash(
                db,
                auth,
                source.project_id,
                content_hash,
                exclude_source_id=source.id,
            )
            if duplicate is not None:
                duplicate.source_metadata = _merge_metadata(
                    duplicate.source_metadata or {},
                    processed_metadata,
                )
                _merge_source_chunk_metadata(db, duplicate, processed_metadata)
                db.delete(source)
                db.commit()
                existing = get_source(db, auth, source.project_id, duplicate.id)
                workflow_utils.complete_zero_cost_step_and_run(
                    db,
                    run=run,
                    step=step,
                    output_json={
                        "source_id": str(existing.id),
                        "duplicate_of_source_id": str(existing.id),
                        "content_hash": content_hash,
                    },
                    latency_ms=int((perf_counter() - started) * 1000),
                    output_summary="Skipped duplicate external source.",
                    model_provider=settings.embedding_provider,
                    model_name=settings.embedding_model,
                )
                return existing

        db.execute(delete(EvidenceChunk).where(EvidenceChunk.source_id == source.id))
        source.title = _truncate(title or source.title or source.url or "Untitled evidence", 500)
        source.raw_text = normalized
        source.summary = _summarize(normalized)
        source.classification = _classify(source.source_type, source.title, normalized)
        source.ingested_at = datetime.now(UTC)
        source.credibility_score = source_provenance_service.adjusted_credibility_score(
            source_type=source.source_type,
            url=source.url,
            metadata=processed_metadata,
        )
        source.source_metadata = _merge_metadata(
            processed_metadata,
            source_provenance_service.quality_metadata(
                source_type=source.source_type,
                url=source.url,
                source_date=source.source_date,
                ingested_at=source.ingested_at,
                classification=source.classification,
                credibility_score=source.credibility_score,
                metadata=processed_metadata,
            ),
        )
        source.ingestion_status = "ready"
        source.ingestion_error = None

        for index, chunk_info in enumerate(chunks):
            embedding = embedding_service.embed_text_with_metadata_cached(
                db,
                auth,
                settings,
                chunk_info.text,
                project_id=source.project_id,
            )
            quote_provenance = source_provenance_service.chunk_quote_provenance(
                source_metadata=source.source_metadata or {},
                chunk_text=chunk_info.text,
                char_start=chunk_info.char_start,
                char_end=chunk_info.char_end,
                chunk_index=index,
            )
            chunk_metadata = _merge_metadata(
                {
                    "source_title": source.title,
                    "source_type": source.source_type,
                    "url": source.url,
                    "content_hash": content_hash,
                    "source_metadata": source.source_metadata or {},
                    **embedding_service.embedding_metadata(settings),
                },
                _merge_metadata(source.source_metadata, quote_provenance),
            )
            chunk = EvidenceChunk(
                workspace_id=source.workspace_id,
                project_id=source.project_id,
                source_id=source.id,
                chunk_index=index,
                text=chunk_info.text,
                token_count=len(_tokens(chunk_info.text)),
                embedding=embedding.vector,
                embedding_provider=embedding.provider,
                embedding_model=embedding.model,
                embedding_dimension=embedding.dimension,
                embedding_version=embedding.version,
                embedded_at=embedding.embedded_at,
                embedding_error=None,
                chunk_metadata=chunk_metadata,
            )
            db.add(chunk)

        db.commit()
        db.refresh(source)
        source = get_source(db, auth, source.project_id, source.id)
        latency_ms = int((perf_counter() - started) * 1000)
        workflow_utils.complete_zero_cost_step_and_run(
            db,
            run=run,
            step=step,
            output_json={
                "source_id": str(source.id),
                "chunk_count": len(source.chunks),
                "classification": source.classification,
                "summary": source.summary,
                "embedding_provider": settings.embedding_provider,
                "embedding_model": settings.embedding_model,
                "embedding_dimension": settings.embedding_dimension,
                "embedding_version": settings.embedding_version,
            },
            latency_ms=latency_ms,
            output_summary=source.summary or "",
            model_provider=settings.embedding_provider,
            model_name=settings.embedding_model,
        )
        return source
    except Exception as exc:
        db.rollback()
        _mark_source_failed(db, source, str(exc))
        workflow_utils.fail_step_and_run(
            db,
            run=run,
            step=step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        if isinstance(exc, EvidenceIngestionError):
            raise
        raise EvidenceIngestionError("Evidence source processing failed.") from exc


def _mark_source_failed(
    db: Session,
    source: EvidenceSource,
    error: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    source.ingestion_status = "failed"
    source.ingestion_error = error[:2000]
    if metadata:
        source.source_metadata = _merge_metadata(source.source_metadata or {}, metadata)
    db.commit()


def _find_ready_url_source(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    url: str,
) -> EvidenceSource | None:
    return db.scalar(
        select(EvidenceSource)
        .where(
            EvidenceSource.workspace_id == auth.workspace_id,
            EvidenceSource.project_id == project_id,
            EvidenceSource.url == url,
            EvidenceSource.ingestion_status == "ready",
        )
        .options(selectinload(EvidenceSource.chunks))
    )


def _find_ready_source_by_content_hash(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    content_hash: str,
    *,
    exclude_source_id: uuid.UUID,
) -> EvidenceSource | None:
    sources = list(
        db.scalars(
            select(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
                EvidenceSource.source_type == "url",
                EvidenceSource.ingestion_status == "ready",
                EvidenceSource.id != exclude_source_id,
            )
            .options(selectinload(EvidenceSource.chunks))
        )
    )
    for source in sources:
        if (source.source_metadata or {}).get("content_hash") == content_hash:
            return source
    return None


def _merge_source_chunk_metadata(
    db: Session,
    source: EvidenceSource,
    metadata: dict[str, Any],
) -> None:
    for chunk in source.chunks:
        chunk.chunk_metadata = _merge_metadata(chunk.chunk_metadata or {}, metadata)


def _merge_metadata(
    base: dict[str, Any],
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    return metadata_utils.merge_metadata(base, extra)


def _fetch_url(settings: Settings, url: str) -> ParsedSource:
    """Fetch a URL with redirect revalidation and response-size limits."""
    _validate_fetch_target(url, settings)
    fetched_at = datetime.now(UTC)

    try:
        with httpx.Client(
            timeout=settings.url_fetch_timeout_seconds,
            headers={"User-Agent": "ThesysBot/0.1 (+local-dev)"},
        ) as client:
            current_url = url
            response: httpx.Response | None = None
            for redirect_count in range(settings.url_fetch_max_redirects + 1):
                _validate_fetch_target(current_url, settings)
                response = client.get(current_url, follow_redirects=False)
                if response.is_redirect:
                    if redirect_count >= settings.url_fetch_max_redirects:
                        raise EvidenceSecurityError("URL exceeded redirect limit.")
                    redirect_url = response.headers.get("location")
                    if not redirect_url:
                        raise EvidenceSecurityError("URL redirect did not include a location.")
                    current_url = str(response.url.join(redirect_url))
                    continue
                response.raise_for_status()
                break
            if response is None:
                raise EvidenceIngestionError("URL did not return a response.")
    except httpx.HTTPStatusError as exc:
        raise EvidenceIngestionError(f"URL returned HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise EvidenceIngestionError(f"Could not fetch URL: {exc}") from exc

    content_type = response.headers.get("content-type", "").split(";")[0].strip().casefold()
    try:
        validate_url_response_content_type(content_type, settings)
    except SecurityValidationError as exc:
        raise EvidenceSecurityError(exc.reason) from exc
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = 0
        if declared_length > settings.url_fetch_max_bytes:
            raise EvidenceSecurityError("URL response exceeded maximum allowed size.")
    if len(response.content) > settings.url_fetch_max_bytes:
        raise EvidenceSecurityError("URL response exceeded maximum allowed size.")
    if "html" in content_type:
        return _parse_html(
            response.text,
            content_type=content_type,
            final_url=str(response.url),
            fetched_at=fetched_at,
        )

    text = _decode_bytes(response.content)
    return ParsedSource(
        title=None,
        text=text,
        content_type=content_type or None,
        metadata=_direct_response_metadata(
            content=response.content,
            text=text,
            content_type=content_type or None,
            final_url=str(response.url),
            fetched_at=fetched_at,
        ),
    )


def _parse_file(
    *,
    settings: Settings,
    filename: str,
    content_type: str,
    body: bytes,
) -> ParsedSource:
    """Route supported uploads through text, PDF, image, or multimodal extraction."""
    lowered = filename.casefold()
    if multimodal_extraction_service.is_image_content(filename, content_type):
        extraction = multimodal_extraction_service.extract_file(
            settings,
            filename=filename,
            content_type=content_type,
            body=body,
            media_type="image",
        )
        return ParsedSource(
            title=extraction.title or filename,
            text=extraction.text,
            content_type=content_type,
            metadata=_image_upload_metadata(
                filename=filename,
                content_type=content_type,
                body=body,
                extraction_metadata=extraction.metadata,
            ),
        )

    if content_type == "application/pdf" or lowered.endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(body))
        except Exception as exc:
            raise EvidenceIngestionError("PDF could not be parsed safely.") from exc
        page_texts = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(page_texts)
        normalized = _normalize_text(text)
        metadata = _pdf_text_metadata(
            filename=filename,
            body=body,
            page_texts=page_texts,
            normalized_text=normalized,
        )
        if (
            settings.multimodal_pdf_fallback_enabled
            and len(normalized) < settings.multimodal_pdf_min_text_chars
        ):
            extraction = multimodal_extraction_service.extract_file(
                settings,
                filename=filename,
                content_type="application/pdf",
                body=body,
                media_type="pdf",
            )
            metadata = _pdf_ocr_fallback_metadata(
                base_metadata=metadata,
                extraction_metadata=extraction.metadata,
                extraction_provider=extraction.provider,
                extraction_model=extraction.model,
                extraction_warnings=extraction.warnings,
                pypdf_text_length=len(normalized),
            )
            return ParsedSource(
                title=extraction.title or filename,
                text=extraction.text,
                content_type="application/pdf",
                metadata=metadata,
            )
        return ParsedSource(
            title=filename,
            text=text,
            content_type="application/pdf",
            metadata=metadata,
        )

    if (
        content_type.startswith("text/")
        or lowered.endswith(".txt")
        or lowered.endswith(".md")
        or lowered.endswith(".markdown")
    ):
        return ParsedSource(
            title=filename,
            text=_decode_bytes(body),
            content_type=content_type,
            metadata=_text_upload_metadata(
                filename=filename,
                content_type=content_type,
                body=body,
            ),
        )

    raise EvidenceIngestionError(
        "Only PDF, text, Markdown, PNG, JPG, JPEG, and WebP uploads are supported."
    )


def _validate_fetch_target(url: str, settings: Settings | None = None) -> None:
    try:
        validate_url_fetch_target(url, settings)
    except SecurityValidationError as exc:
        raise EvidenceSecurityError(exc.reason) from exc


def _record_ingestion_security_event(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID,
    source_id: uuid.UUID | None,
    event_type: str,
    summary: str,
    reason: str,
    metadata: dict[str, Any],
) -> None:
    governance_service.record_audit_event(
        db,
        auth,
        event_type=event_type,
        actor_type="user",
        project_id=project_id,
        entity_type="evidence_source",
        entity_id=source_id,
        risk_level="medium",
        summary=summary,
        metadata={"reason": reason, **metadata},
    )
    db.commit()
