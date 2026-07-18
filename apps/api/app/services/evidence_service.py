"""Evidence ingestion, extraction, chunking, embedding, and source serialization."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.ai.prompts import EVIDENCE_INGESTION_PROMPT_VERSION
from app.common import metadata as metadata_utils
from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
from app.core.security import (
    SecurityValidationError,
    validate_upload,
    validate_url_fetch_target,
    validate_url_response_content_type,
)
from app.db.models import (
    AssumptionEvidenceLink,
    Claim,
    ClaimEvidenceLink,
    CompetitorCandidate,
    CompetitorEvidenceLink,
    DiscoveredSource,
    EvidenceChunk,
    EvidenceSource,
    ProjectMemoryItem,
)
from app.features.evidence import extraction as evidence_extraction
from app.schemas.evidence import EvidenceNoteCreate, EvidenceUrlCreate
from app.services import (
    ai_run_service,
    embedding_service,
    governance_service,
    malware_scanning_service,
    multimodal_extraction_service,
    object_storage_service,
    project_service,
    pseudonymization_service,
    retention_service,
    secure_file_parser_service,
    secure_ingestion_state_service,
    source_provenance_service,
)
from app.services.common import workflow as workflow_utils
from app.services.data_protection_service import data_protection_service

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
        title=data_protection_service.redact_for_model(
            payload.title.strip(), project_id=project_id
        ),
        source_date=payload.source_date,
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    secure_ingestion_state_service.initialize(source)
    db.add(source)
    db.commit()
    db.refresh(source)
    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=payload.text,
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
    secure_ingestion_state_service.initialize(source)
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
    secure_ingestion_state_service.initialize(source)
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
    secure_ingestion_state_service.initialize(source)
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
    require_permission(auth, "write_project")
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
    detected_content_type = upload_validation.detected_content_type
    source_id = uuid.uuid4()
    scan_result = malware_scanning_service.scan_upload(settings, body)
    if scan_result.status is not malware_scanning_service.MalwareScanStatus.CLEAN:
        _quarantine_file_upload(
            db,
            auth,
            project_id=project_id,
            source_id=source_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(body),
            scan_result=scan_result,
        )
        raise EvidenceIngestionError("File evidence ingestion failed.")

    try:
        pdf_extraction = _preflight_file_content(settings, content_type=content_type, body=body)
    except EvidenceSecurityError as exc:
        _record_ingestion_security_event(
            db,
            auth,
            project_id=project_id,
            source_id=None,
            event_type="evidence_upload_rejected",
            summary="Rejected unsafe evidence upload.",
            reason=str(exc),
            metadata={
                "filename": filename,
                "content_type": content_type,
                "detected_content_type": detected_content_type,
                "size_bytes": len(body),
            },
        )
        raise EvidenceIngestionError("File evidence ingestion failed.") from exc

    try:
        storage_key = object_storage_service.put_evidence_object(
            settings,
            workspace_id=auth.workspace_id,
            project_id=project_id,
            source_id=source_id,
            filename=filename,
            body=body,
            content_type=content_type,
        )
    except object_storage_service.ObjectStorageError:
        governance_service.record_audit_event(
            db,
            auth,
            event_type="object_storage_write_denied",
            actor_type="user",
            project_id=project_id,
            entity_type="evidence_source",
            entity_id=source_id,
            risk_level="medium",
            summary="Evidence object storage failed closed.",
            metadata={"content_type": content_type, "size_bytes": len(body)},
        )
        db.commit()
        raise EvidenceIngestionError("File evidence ingestion failed.") from None

    source = EvidenceSource(
        id=source_id,
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="file",
        title=data_protection_service.redact_for_model(filename, project_id=project_id),
        object_storage_key=storage_key,
        source_metadata={
            "content_type": content_type,
            "detected_content_type": detected_content_type,
            "security": {
                "security_status": "quarantined",
                "classification_status": "pending",
                "malware_status": "clean",
            },
        },
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    secure_ingestion_state_service.initialize(source)
    secure_ingestion_state_service.transition(
        source,
        secure_ingestion_state_service.SecureIngestionState.MALWARE_SCANNING,
    )
    secure_ingestion_state_service.transition(
        source,
        secure_ingestion_state_service.SecureIngestionState.EXTRACTION_PENDING,
    )
    db.add(source)
    governance_service.record_audit_event(
        db,
        auth,
        event_type="object_stored",
        actor_type="user",
        project_id=project_id,
        entity_type="evidence_source",
        entity_id=source_id,
        risk_level="low",
        summary="Stored a private evidence object.",
        metadata={
            "content_type": content_type,
            "size_bytes": len(body),
            "storage_mode": settings.object_storage_mode,
        },
    )
    db.commit()
    db.refresh(source)

    try:
        parsed = _parse_file(
            settings=settings,
            filename=filename,
            content_type=content_type,
            body=body,
            pdf_extraction=pdf_extraction,
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
    secure_ingestion_state_service.initialize(source)
    secure_ingestion_state_service.transition(
        source,
        secure_ingestion_state_service.SecureIngestionState.EXTRACTION_PENDING,
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
    settings: Settings,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
) -> None:
    source = get_source(db, auth, project_id, source_id)
    require_permission(auth, "write_project")
    deletion_impact = _invalidate_source_derivatives(db, source)
    if source.object_storage_key:
        object_storage_service.delete_evidence_object(
            settings,
            workspace_id=auth.workspace_id,
            project_id=project_id,
            source_id=source.id,
            key=source.object_storage_key,
        )
        governance_service.record_audit_event(
            db,
            auth,
            event_type="object_deleted",
            actor_type="user",
            project_id=project_id,
            entity_type="evidence_source",
            entity_id=source.id,
            risk_level="medium",
            summary="Deleted a private evidence object.",
            metadata={"storage_mode": settings.object_storage_mode},
        )
    db.delete(source)
    db.flush()
    remaining_chunks = db.scalar(
        select(func.count()).select_from(EvidenceChunk).where(EvidenceChunk.source_id == source_id)
    )
    if remaining_chunks:
        raise EvidenceIngestionError("Evidence deletion did not remove all retrievable chunks.")
    governance_service.record_audit_event(
        db,
        auth,
        event_type="evidence_source_deletion_propagated",
        actor_type="user",
        project_id=project_id,
        entity_type="evidence_source",
        entity_id=source_id,
        risk_level="high",
        summary="Deleted evidence source and invalidated dependent derived data.",
        metadata={
            **deletion_impact,
            "object_deleted": source.object_storage_key is not None,
            "retrieval_revoked": True,
        },
    )
    db.commit()


def prepare_source_download(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
) -> object_storage_service.ObjectDownload:
    source = get_source(db, auth, project_id, source_id)
    if not source.object_storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence source has no stored object.",
        )
    content_type = str(
        (source.source_metadata or {}).get("content_type") or "application/octet-stream"
    )
    try:
        download = object_storage_service.prepare_evidence_download(
            settings,
            workspace_id=auth.workspace_id,
            project_id=project_id,
            source_id=source.id,
            key=source.object_storage_key,
            filename=source.title or "evidence-download",
            content_type=content_type,
        )
    except object_storage_service.ObjectStorageError:
        governance_service.record_audit_event(
            db,
            auth,
            event_type="signed_url_denied",
            actor_type="user",
            project_id=project_id,
            entity_type="evidence_source",
            entity_id=source.id,
            risk_level="medium",
            summary="Denied an evidence object download.",
            metadata={"storage_mode": settings.object_storage_mode},
        )
        db.commit()
        raise

    event_type = (
        "signed_url_created"
        if download.storage_mode == "s3"
        else "object_download_authorized"
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type=event_type,
        actor_type="user",
        project_id=project_id,
        entity_type="evidence_source",
        entity_id=source.id,
        risk_level="low",
        summary="Authorized an evidence object download.",
        metadata={
            "storage_mode": download.storage_mode,
            "expires_at": download.expires_at.isoformat(),
            "content_type": download.content_type,
        },
    )
    db.commit()
    return download


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
    stmt = (
        select(EvidenceChunk, EvidenceSource)
        .join(EvidenceSource, EvidenceSource.id == EvidenceChunk.source_id)
        .where(EvidenceChunk.workspace_id == auth.workspace_id)
    )
    if scope == "project":
        stmt = stmt.where(EvidenceChunk.project_id == project_id)
    elif scope != "workspace":
        raise ValueError(f"Unsupported re-embedding scope: {scope}")

    rows = list(db.execute(stmt.order_by(EvidenceChunk.created_at.asc())).all())
    chunks = [chunk for chunk, _source in rows]
    eligible = [
        chunk
        for chunk, source in rows
        if data_protection_service.is_source_approved(source.source_metadata)
        and data_protection_service.is_chunk_retrievable(chunk.chunk_metadata)
        and (force or _chunk_needs_reembedding(chunk, settings))
    ]
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
        input_summary=str(source.id),
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
        secure_ingestion_state_service.initialize(source)
        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.EXTRACTION_PENDING,
        )
        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.EXTRACTED,
        )
        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.CLASSIFICATION_PENDING,
        )
        protected_source_text = pseudonymization_service.create_searchable_copy(
            db,
            auth,
            settings,
            project_id=source.project_id,
            text=text,
        )
        normalized = _normalize_text(text)
        if not normalized:
            raise EvidenceIngestionError("Evidence source did not contain extractable text.")
        if len(normalized) > settings.max_extracted_text_chars:
            raise EvidenceIngestionError(
                f"Extracted text exceeds {settings.max_extracted_text_chars} character limit."
            )

        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.CLASSIFIED,
        )
        if protected_source_text.pii_status == "redacted":
            secure_ingestion_state_service.transition(
                source,
                secure_ingestion_state_service.SecureIngestionState.PII_REVIEW_PENDING,
            )
        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.APPROVED_FOR_EMBEDDING,
        )

        searchable_text = _normalize_text(protected_source_text.text)
        chunks = _chunk_text(searchable_text)
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
        existing_security = (source.source_metadata or {}).get("security")
        malware_status = (
            existing_security.get("malware_status")
            if isinstance(existing_security, dict)
            else "not_scanned"
        )
        source_security_metadata = {
            "data_classification": protected_source_text.data_classification.value,
            "pii_status": protected_source_text.pii_status,
            "pii_entity_types": list(protected_source_text.pii_entity_types),
            "security_status": "approved",
            "classification_status": "approved",
            "malware_status": malware_status,
            "sanitization_version": protected_source_text.sanitization_version,
            "retention_expires_at": retention_service.expires_at(
                settings,
                retention_service.RetentionAsset.SANITIZED_TEXT,
                created_at=source.created_at,
            ).isoformat(),
        }
        processed_metadata = _merge_metadata(
            source.source_metadata or {},
            _merge_metadata(
                base_metadata,
                source_provenance_service.extraction_artifacts(
                    text=protected_source_text.text,
                    metadata=base_metadata,
                    extraction_method=extraction_method,
                ),
            ),
        )
        processed_metadata["security"] = source_security_metadata
        processed_metadata["retention"] = retention_service.evidence_retention_metadata(
            settings,
            created_at=source.created_at,
        )
        prompt_markers = source_provenance_service.detect_prompt_injection_markers(searchable_text)
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
        source.title = _truncate(
            data_protection_service.redact_for_model(
                title or source.title or source.url or "Untitled evidence",
                project_id=source.project_id,
            ),
            500,
        )
        source.raw_text = searchable_text
        source.summary = _summarize(searchable_text)
        source.classification = _classify(source.source_type, source.title, searchable_text)
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
            chunk_security_metadata = {
                "data_classification": protected_source_text.data_classification.value,
                "pii_status": protected_source_text.pii_status,
                "retrieval_allowed": True,
                "sanitization_version": protected_source_text.sanitization_version,
                "source_security_status": "approved",
                "retention_expires_at": retention_service.expires_at(
                    settings,
                    retention_service.RetentionAsset.EMBEDDING,
                    created_at=source.created_at,
                ).isoformat(),
            }
            chunk_metadata = _merge_metadata(
                _merge_metadata(
                    {
                        "source_title": source.title,
                        "source_type": source.source_type,
                        "url": source.url,
                        "content_hash": content_hash,
                        "source_metadata": source.source_metadata or {},
                        **embedding_service.embedding_metadata(settings),
                    },
                    _merge_metadata(source.source_metadata, quote_provenance),
                ),
                {"security": chunk_security_metadata},
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

        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.EMBEDDED,
        )
        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.RETRIEVABLE,
        )

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
    secure_ingestion_state_service.initialize(source)
    current_state = secure_ingestion_state_service.state(source)
    if current_state is secure_ingestion_state_service.SecureIngestionState.RETRIEVABLE:
        return
    if current_state not in {
        secure_ingestion_state_service.SecureIngestionState.FAILED,
        secure_ingestion_state_service.SecureIngestionState.QUARANTINED,
    }:
        secure_ingestion_state_service.transition(
            source,
            secure_ingestion_state_service.SecureIngestionState.FAILED,
        )
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
        existing = chunk.chunk_metadata or {}
        merged = _merge_metadata(existing, metadata)
        existing_security = existing.get("security")
        incoming_security = metadata.get("security")
        if isinstance(existing_security, dict) and isinstance(incoming_security, dict):
            merged["security"] = {**existing_security, **incoming_security}
        chunk.chunk_metadata = merged


def _invalidate_source_derivatives(db: Session, source: EvidenceSource) -> dict[str, int]:
    """Invalidate data that would otherwise retain support from a deleted source."""
    source_claim_links = list(
        db.scalars(
            select(ClaimEvidenceLink).where(ClaimEvidenceLink.evidence_source_id == source.id)
        )
    )
    linked_claim_ids = {link.claim_id for link in source_claim_links}
    linked_claims = {
        claim.id: claim
        for claim in db.scalars(
            select(Claim).where(Claim.id.in_(linked_claim_ids))
        )
    }
    invalidated_claims: list[Claim] = []
    for claim in linked_claims.values():
        alternate_link = db.scalar(
            select(ClaimEvidenceLink.id)
            .where(
                ClaimEvidenceLink.claim_id == claim.id,
                ClaimEvidenceLink.evidence_source_id != source.id,
            )
            .limit(1)
        )
        if alternate_link is None:
            claim.support_level = "unsupported"
            invalidated_claims.append(claim)

    db.execute(delete(ClaimEvidenceLink).where(ClaimEvidenceLink.evidence_source_id == source.id))
    db.execute(
        delete(AssumptionEvidenceLink).where(AssumptionEvidenceLink.evidence_source_id == source.id)
    )
    db.execute(
        delete(CompetitorEvidenceLink).where(CompetitorEvidenceLink.evidence_source_id == source.id)
    )
    db.execute(
        update(DiscoveredSource)
        .where(DiscoveredSource.evidence_source_id == source.id)
        .values(evidence_source_id=None)
    )
    candidates = list(
        db.scalars(
            select(CompetitorCandidate).where(
                CompetitorCandidate.workspace_id == source.workspace_id,
                CompetitorCandidate.project_id == source.project_id,
            )
        )
    )
    source_id = str(source.id)
    candidate_reference_count = 0
    for candidate in candidates:
        references_source = (
            candidate.evidence_source_id == source.id or source_id in candidate.source_ids
        )
        if not references_source:
            continue
        candidate_reference_count += 1
        if candidate.evidence_source_id == source.id:
            candidate.evidence_source_id = None
        candidate.source_ids = [item for item in candidate.source_ids if item != source_id]

    invalidated_version_ids = {
        claim.artifact_version_id
        for claim in invalidated_claims
        if claim.artifact_version_id is not None
    }
    stale_memory_count = 0
    for item in db.scalars(
        select(ProjectMemoryItem).where(
            ProjectMemoryItem.workspace_id == source.workspace_id,
            ProjectMemoryItem.project_id == source.project_id,
        )
    ):
        references_source = (
            (item.source_entity_type == "evidence_source" and item.source_entity_id == source.id)
            or (item.entity_type == "evidence_source" and item.entity_id == source.id)
            or (
                item.source_entity_type == "artifact_version"
                and item.source_entity_id in invalidated_version_ids
            )
        )
        if not references_source or item.status not in {"active", "proposed"}:
            continue
        item.status = "stale"
        item.provenance_metadata = {**(item.provenance_metadata or {}), "evidence_deleted": True}
        stale_memory_count += 1

    chunk_count = len(source.chunks)
    return {
        "chunks_deleted": chunk_count,
        "claim_links_deleted": len(source_claim_links),
        "claims_invalidated": len(invalidated_claims),
        "competitor_references_cleared": candidate_reference_count,
        "memory_items_staled": stale_memory_count,
    }


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
    pdf_extraction: secure_file_parser_service.PDFExtraction | None = None,
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
        if pdf_extraction is None:
            try:
                pdf_extraction = secure_file_parser_service.extract_pdf(settings, body=body)
            except secure_file_parser_service.PDFParserError as exc:
                raise EvidenceIngestionError("PDF could not be parsed safely.") from exc
        page_texts = pdf_extraction.page_texts
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


def _preflight_file_content(
    settings: Settings,
    *,
    content_type: str,
    body: bytes,
) -> secure_file_parser_service.PDFExtraction | None:
    if content_type != "application/pdf":
        return None
    try:
        return secure_file_parser_service.extract_pdf(settings, body=body)
    except secure_file_parser_service.PDFSecurityError as exc:
        raise EvidenceSecurityError(str(exc)) from exc
    except secure_file_parser_service.PDFResourceLimitError as exc:
        raise EvidenceSecurityError(str(exc)) from exc
    except secure_file_parser_service.PDFParserError as exc:
        raise EvidenceSecurityError("PDF could not be parsed safely.") from exc


def _validate_fetch_target(url: str, settings: Settings | None = None) -> None:
    try:
        validate_url_fetch_target(url, settings)
    except SecurityValidationError as exc:
        raise EvidenceSecurityError(exc.reason) from exc


def _quarantine_file_upload(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    filename: str,
    content_type: str,
    size_bytes: int,
    scan_result: malware_scanning_service.MalwareScanResult,
) -> None:
    source = EvidenceSource(
        id=source_id,
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="file",
        title=data_protection_service.redact_for_model(filename, project_id=project_id),
        ingestion_status="quarantined",
        ingestion_error="File was quarantined before parsing.",
        source_metadata={
            "content_type": content_type,
            "file_size_bytes": size_bytes,
            "security": {
                "data_classification": "restricted",
                "pii_status": "not_scanned",
                "pii_entity_types": [],
                "security_status": "quarantined",
                "classification_status": "pending",
                "malware_status": scan_result.status.value,
            },
        },
        created_by=auth.user_id,
    )
    secure_ingestion_state_service.initialize(source)
    secure_ingestion_state_service.transition(
        source,
        secure_ingestion_state_service.SecureIngestionState.MALWARE_SCANNING,
    )
    secure_ingestion_state_service.transition(
        source,
        secure_ingestion_state_service.SecureIngestionState.QUARANTINED,
    )
    db.add(source)
    governance_service.record_audit_event(
        db,
        auth,
        event_type="evidence_upload_quarantined",
        actor_type="user",
        project_id=project_id,
        entity_type="evidence_source",
        entity_id=source_id,
        risk_level="high",
        summary="Quarantined an evidence upload before parsing.",
        metadata={
            "content_type": content_type,
            "size_bytes": size_bytes,
            "malware_status": scan_result.status.value,
            "signature": scan_result.signature,
            "reason": scan_result.reason,
        },
    )
    db.commit()


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
