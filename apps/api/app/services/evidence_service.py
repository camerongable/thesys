import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
from time import perf_counter
from typing import Any

import httpx
from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.ai.prompts import EVIDENCE_INGESTION_PROMPT_VERSION
from app.core.auth import AuthContext
from app.core.config import Settings
from app.core.security import SecurityValidationError, validate_upload, validate_url_fetch_target
from app.db.models import EvidenceChunk, EvidenceSource
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
from app.services.common import metadata as metadata_utils
from app.services.common import workflow as workflow_utils

TOKEN_RE = re.compile(r"\S+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class EvidenceIngestionError(RuntimeError):
    pass


class EvidenceSecurityError(EvidenceIngestionError):
    pass


@dataclass(frozen=True)
class ParsedSource:
    title: str | None
    text: str
    content_type: str | None = None
    metadata: dict[str, Any] | None = None


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
        f"workspaces/{auth.workspace_id}/projects/{project_id}/evidence/"
        f"{uuid.uuid4()}-{filename}"
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
                embedding = embedding_service.embed_text_with_metadata(settings, chunk.text)
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
        processed_metadata = _merge_metadata(
            source.source_metadata or {},
            _merge_metadata(
                {
                    "content_type": content_type,
                    "content_hash": content_hash,
                    "domain": source_provenance_service.source_domain(source.url),
                },
                metadata,
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

        for index, chunk_text in enumerate(chunks):
            embedding = embedding_service.embed_text_with_metadata(settings, chunk_text)
            chunk_metadata = _merge_metadata(
                {
                    "source_title": source.title,
                    "source_type": source.source_type,
                    "url": source.url,
                    "content_hash": content_hash,
                    "source_metadata": source.source_metadata or {},
                    **embedding_service.embedding_metadata(settings),
                },
                source.source_metadata,
            )
            chunk = EvidenceChunk(
                workspace_id=source.workspace_id,
                project_id=source.project_id,
                source_id=source.id,
                chunk_index=index,
                text=chunk_text,
                token_count=len(_tokens(chunk_text)),
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
    _validate_fetch_target(url)
    fetched_at = datetime.now(UTC)

    try:
        with httpx.Client(
            timeout=settings.url_fetch_timeout_seconds,
            headers={"User-Agent": "ThesysBot/0.1 (+local-dev)"},
        ) as client:
            current_url = url
            response: httpx.Response | None = None
            for redirect_count in range(settings.url_fetch_max_redirects + 1):
                _validate_fetch_target(current_url)
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
        raise EvidenceIngestionError(
            f"URL returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise EvidenceIngestionError(f"Could not fetch URL: {exc}") from exc

    content_type = response.headers.get("content-type", "").split(";")[0].strip().casefold()
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
    canonical_url = source_provenance_service.canonicalize_url(str(response.url))
    markers = source_provenance_service.detect_prompt_injection_markers(text)
    return ParsedSource(
        title=None,
        text=text,
        content_type=content_type or None,
        metadata={
            "canonical_url": canonical_url,
            "final_url": str(response.url),
            "domain": source_provenance_service.source_domain(canonical_url),
            "fetched_at": fetched_at.isoformat(),
            "retrieved_at": fetched_at.isoformat(),
            "response_content_type": content_type or None,
            "response_byte_length": len(response.content),
            "prompt_injection_markers": markers,
            "extraction_method": "direct_response_decode",
        },
    )


def _parse_file(
    *,
    settings: Settings,
    filename: str,
    content_type: str,
    body: bytes,
) -> ParsedSource:
    lowered = filename.casefold()
    file_metadata = {
        "filename": filename,
        "file_size_bytes": len(body),
        "file_content_hash": source_provenance_service.byte_hash(body),
    }
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
            metadata=_merge_metadata(
                file_metadata,
                _merge_metadata(
                    extraction.metadata,
                    {
                        "image_metadata": {
                            "content_type": content_type,
                            "byte_length": len(body),
                            "content_hash": source_provenance_service.byte_hash(body),
                        }
                    },
                ),
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
        metadata: dict[str, Any] = {
            **file_metadata,
            "media_type": "pdf",
            "content_type": "application/pdf",
            "pdf_text_extraction": "pypdf",
            "pdf_page_count": len(page_texts),
            "pdf_page_lineage": source_provenance_service.pdf_page_lineage(page_texts),
            "table_extraction": {
                "enabled": False,
                "reason": "table extraction extension point is not configured",
            },
            "extracted_text_length": len(normalized),
        }
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
            metadata = _merge_metadata(
                metadata,
                {
                    **extraction.metadata,
                    "pdf_text_extraction": "multimodal_fallback",
                    "pypdf_extracted_text_length": len(normalized),
                    "ocr_fallback_used": True,
                },
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
            metadata={
                **file_metadata,
                "media_type": "text",
                "content_type": content_type,
                "text_extraction": "direct_decode",
            },
        )

    raise EvidenceIngestionError(
        "Only PDF, text, Markdown, PNG, JPG, JPEG, and WebP uploads are supported."
    )


def _parse_html(
    html: str,
    *,
    content_type: str,
    final_url: str | None = None,
    fetched_at: datetime | None = None,
) -> ParsedSource:
    parser = _ReadableHtmlParser()
    parser.feed(html)
    title = _normalize_text(parser.title) or None
    text = _normalize_text(" ".join(parser.text_parts))
    canonical_url = source_provenance_service.canonicalize_url(final_url) if final_url else None
    markers = source_provenance_service.detect_prompt_injection_markers(text)
    metadata: dict[str, Any] = {
        "canonical_url": canonical_url,
        "final_url": final_url,
        "domain": source_provenance_service.source_domain(canonical_url),
        "fetched_at": fetched_at.isoformat() if fetched_at else None,
        "retrieved_at": fetched_at.isoformat() if fetched_at else None,
        "response_content_type": content_type,
        "extraction_method": "readable_html_parser_v2",
        "prompt_injection_markers": markers,
        "text_lineage": {
            "page_title": title,
            "sections": parser.sections[:50],
        },
    }
    if final_url and fetched_at:
        metadata = _merge_metadata(
            metadata,
            source_provenance_service.html_snapshot_metadata(
                html=html,
                final_url=final_url,
                fetched_at=fetched_at,
            ),
        )
    return ParsedSource(title=title, text=text, content_type=content_type, metadata=metadata)


def _decode_bytes(body: bytes) -> str:
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("latin-1", errors="ignore")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _chunk_text(text: str, *, target_tokens: int = 950, overlap_tokens: int = 150) -> list[str]:
    tokens = _tokens(text)
    if len(tokens) <= target_tokens:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + target_tokens, len(tokens))
        chunks.append(" ".join(tokens[start:end]))
        if end == len(tokens):
            break
        start = max(0, end - overlap_tokens)
    return chunks


def _tokens(text: str) -> list[str]:
    return [match.group(0) for match in TOKEN_RE.finditer(text)]


def _summarize(text: str) -> str:
    sentences = [sentence.strip() for sentence in SENTENCE_RE.split(text) if sentence.strip()]
    if not sentences:
        return _truncate(text, 500)
    return _truncate(" ".join(sentences[:2]), 700)


def _classify(source_type: str, title: str | None, text: str) -> str:
    combined = f"{title or ''} {text[:3000]}".casefold()
    if source_type == "transcript" or any(
        word in combined for word in ["interview", "customer said", "respondent"]
    ):
        return "customer_discovery"
    if any(word in combined for word in ["pricing", "features", "competitor", "alternative"]):
        return "competitor_research"
    if any(word in combined for word in ["market", "report", "trend", "industry", "category"]):
        return "market_research"
    if any(word in combined for word in ["assumption", "risk", "experiment", "validation"]):
        return "validation"
    return "project_note"


def _preview(text: str | None) -> str | None:
    if not text:
        return None
    return _truncate(text, 220)


def _truncate(value: str, max_length: int) -> str:
    return value[:max_length]


def _validate_fetch_target(url: str) -> None:
    try:
        validate_url_fetch_target(url)
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


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text_parts: list[str] = []
        self.sections: list[dict[str, Any]] = []
        self._skip_depth = 0
        self._in_title = False
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._current_heading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in {"h1", "h2", "h3"} and self._skip_depth == 0:
            self._heading_tag = tag
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag == self._heading_tag:
            heading = _normalize_text(" ".join(self._heading_parts))
            if heading:
                self._current_heading = heading[:200]
            self._heading_tag = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += f" {data}"
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                if self._heading_tag:
                    self._heading_parts.append(text)
                self.text_parts.append(text)
                self.sections.append(
                    {
                        "section": self._current_heading or _normalize_text(self.title) or None,
                        "text_preview": _truncate(text, 300),
                    }
                )
