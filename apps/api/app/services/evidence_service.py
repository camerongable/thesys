import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
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
from app.db.models import EvidenceChunk, EvidenceSource
from app.schemas.evidence import EvidenceNoteCreate, EvidenceUrlCreate
from app.services import ai_run_service, embedding_service, object_storage_service, project_service

TOKEN_RE = re.compile(r"\S+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class EvidenceIngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedSource:
    title: str | None
    text: str
    content_type: str | None = None


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
    source = EvidenceSource(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="url",
        title=payload.title.strip() if payload.title else None,
        url=str(payload.url),
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    try:
        parsed = _fetch_url(settings, str(payload.url))
    except Exception as exc:
        _mark_source_failed(db, source, str(exc))
        raise EvidenceIngestionError("URL evidence ingestion failed.") from exc

    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=parsed.text,
        title=source.title or parsed.title or str(payload.url),
        content_type=parsed.content_type,
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
    existing = _find_ready_url_source(db, auth, project_id, url)
    if existing is not None:
        if metadata:
            _merge_source_chunk_metadata(db, existing, metadata)
            db.commit()
        return get_source(db, auth, project_id, existing.id)

    source = EvidenceSource(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="url",
        title=title.strip() if title else None,
        url=url,
        source_date=datetime.now(UTC),
        ingestion_status="processing",
        created_by=auth.user_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    try:
        parsed = _fetch_url(settings, url)
    except Exception as exc:
        if fallback_text and _normalize_text(fallback_text):
            fallback_metadata = _merge_metadata(
                metadata or {},
                {
                    "remote_fetch_error": str(exc),
                    "used_discovery_snapshot": True,
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
        _mark_source_failed(db, source, str(exc))
        raise EvidenceIngestionError(f"URL evidence ingestion failed: {exc}") from exc

    return _process_source_text(
        db,
        auth,
        settings,
        source,
        text=parsed.text,
        title=source.title or parsed.title or url,
        content_type=parsed.content_type,
        metadata=metadata,
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
    source = EvidenceSource(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        source_type="url",
        title=title.strip() if title else None,
        url=url,
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
        title=source.title or url,
        content_type="text/plain",
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
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(body) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_mb} MB upload limit.",
        )

    filename = upload.filename or "uploaded-evidence"
    content_type = upload.content_type or "application/octet-stream"
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
        parsed = _parse_file(filename=filename, content_type=content_type, body=body)
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
        "ingestion_status": source.ingestion_status,
        "ingestion_error": source.ingestion_error,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
        "chunk_count": len(source.chunks),
        "text_preview": _preview(source.raw_text),
    }


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
        model_provider="internal",
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

        chunks = _chunk_text(normalized)
        if not chunks:
            raise EvidenceIngestionError("Evidence source did not produce chunks.")

        db.execute(delete(EvidenceChunk).where(EvidenceChunk.source_id == source.id))
        source.title = _truncate(title or source.title or source.url or "Untitled evidence", 500)
        source.raw_text = normalized
        source.summary = _summarize(normalized)
        source.classification = _classify(source.source_type, source.title, normalized)
        source.credibility_score = _credibility_score(source.source_type)
        source.ingested_at = datetime.now(UTC)
        source.ingestion_status = "ready"
        source.ingestion_error = None

        content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        for index, chunk_text in enumerate(chunks):
            chunk_metadata = _merge_metadata(
                {
                    "source_title": source.title,
                    "source_type": source.source_type,
                    "url": source.url,
                    "content_hash": content_hash,
                    "embedding_model": settings.embedding_model,
                },
                metadata,
            )
            chunk = EvidenceChunk(
                workspace_id=source.workspace_id,
                project_id=source.project_id,
                source_id=source.id,
                chunk_index=index,
                text=chunk_text,
                token_count=len(_tokens(chunk_text)),
                embedding=embedding_service.embed_text(settings, chunk_text),
                chunk_metadata=chunk_metadata,
            )
            db.add(chunk)

        db.commit()
        db.refresh(source)
        source = get_source(db, auth, source.project_id, source.id)
        latency_ms = int((perf_counter() - started) * 1000)
        ai_run_service.complete_step(
            db,
            step,
            output_json={
                "source_id": str(source.id),
                "chunk_count": len(source.chunks),
                "classification": source.classification,
                "summary": source.summary,
            },
            latency_ms=latency_ms,
            tokens=None,
            cost=Decimal("0"),
        )
        ai_run_service.complete_run(
            db,
            run,
            output_summary=source.summary or "",
            total_tokens=None,
            total_cost=Decimal("0"),
            model_provider="internal",
            model_name=settings.embedding_model,
        )
        return source
    except Exception as exc:
        db.rollback()
        _mark_source_failed(db, source, str(exc))
        ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        ai_run_service.fail_run(db, run, error=str(exc))
        if isinstance(exc, EvidenceIngestionError):
            raise
        raise EvidenceIngestionError("Evidence source processing failed.") from exc


def _mark_source_failed(db: Session, source: EvidenceSource, error: str) -> None:
    source.ingestion_status = "failed"
    source.ingestion_error = error[:2000]
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
    if not extra:
        return base

    merged = dict(base)
    for key, value in extra.items():
        if value is None:
            continue
        if key.endswith("_ids") or key in {
            "research_questions",
            "assumptions_to_test",
            "source_candidate_types",
            "discovered_source_ids",
            "competitor_candidate_ids",
            "competitor_ids",
        }:
            existing_values = merged.get(key, [])
            if not isinstance(existing_values, list):
                existing_values = [existing_values]
            new_values = value if isinstance(value, list) else [value]
            ordered: list[Any] = []
            seen: set[str] = set()
            for item in [*existing_values, *new_values]:
                if item is None:
                    continue
                marker = str(item)
                if marker not in seen:
                    ordered.append(item)
                    seen.add(marker)
            merged[key] = ordered
        else:
            merged[key] = value
    return merged


def _fetch_url(settings: Settings, url: str) -> ParsedSource:
    try:
        with httpx.Client(
            timeout=settings.url_fetch_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ThesysBot/0.1 (+local-dev)"},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise EvidenceIngestionError(
            f"URL returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise EvidenceIngestionError(f"Could not fetch URL: {exc}") from exc

    content_type = response.headers.get("content-type", "").split(";")[0].strip().casefold()
    if "html" in content_type:
        return _parse_html(response.text, content_type=content_type)

    text = _decode_bytes(response.content)
    return ParsedSource(title=None, text=text, content_type=content_type or None)


def _parse_file(*, filename: str, content_type: str, body: bytes) -> ParsedSource:
    lowered = filename.casefold()
    if content_type == "application/pdf" or lowered.endswith(".pdf"):
        reader = PdfReader(BytesIO(body))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        return ParsedSource(title=filename, text=text, content_type="application/pdf")

    if (
        content_type.startswith("text/")
        or lowered.endswith(".txt")
        or lowered.endswith(".md")
        or lowered.endswith(".markdown")
    ):
        return ParsedSource(title=filename, text=_decode_bytes(body), content_type=content_type)

    raise EvidenceIngestionError("Only PDF, text, and Markdown uploads are supported in Sprint 4.")


def _parse_html(html: str, *, content_type: str) -> ParsedSource:
    parser = _ReadableHtmlParser()
    parser.feed(html)
    title = _normalize_text(parser.title) or None
    text = _normalize_text(" ".join(parser.text_parts))
    return ParsedSource(title=title, text=text, content_type=content_type)


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


def _credibility_score(source_type: str) -> Decimal:
    if source_type == "url":
        return Decimal("0.70")
    if source_type == "file":
        return Decimal("0.65")
    if source_type == "transcript":
        return Decimal("0.80")
    return Decimal("0.50")


def _preview(text: str | None) -> str | None:
    if not text:
        return None
    return _truncate(text, 220)


def _truncate(value: str, max_length: int) -> str:
    return value[:max_length]


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += f" {data}"
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.text_parts.append(text)
