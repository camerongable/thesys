"""Isolated worker entry point for bounded PDF extraction.

This module intentionally imports only the standard library until its resource
limit has been established. ``multiprocessing`` imports a worker target module
before executing it, so keeping the target separate prevents a spawned parser
from loading the API configuration and web stack before its memory guard runs.
"""

from __future__ import annotations

import sys
from io import BytesIO
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - Windows does not provide resource limits.
    resource = None  # type: ignore[assignment]


def extract_pdf_in_worker(
    connection: Any,
    body: bytes,
    max_pages: int,
    max_text_chars: int,
    memory_limit_mb: int,
    max_decompression_ratio: float,
) -> None:
    """Extract untrusted PDF text after constraining this child process."""
    try:
        _apply_memory_limit(memory_limit_mb)
        from pypdf import PdfReader
        from pypdf.generic import StreamObject

        reader = PdfReader(BytesIO(body), strict=False)
        if reader.is_encrypted:
            _send(connection, "security", "Password-protected PDFs are not allowed.")
            return
        if _contains_active_content(reader.trailer.get("/Root")):
            _send(connection, "security", "PDF active content is not allowed.")
            return
        if _exceeds_decompression_ratio(
            reader.trailer.get("/Root"),
            max_decompression_ratio=max_decompression_ratio,
            stream_object_type=StreamObject,
        ):
            _send(
                connection,
                "resource",
                "PDF stream exceeds the configured decompression ratio limit.",
            )
            return
        page_count = len(reader.pages)
        if page_count > max_pages:
            _send(connection, "security", f"PDF exceeds {max_pages} page limit.")
            return

        page_texts: list[str] = []
        extracted_characters = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            extracted_characters += len(page_text)
            if extracted_characters > max_text_chars:
                _send(
                    connection,
                    "resource",
                    f"PDF extraction exceeds {max_text_chars} character limit.",
                )
                return
            page_texts.append(page_text)
        _send(connection, "ok", page_texts=page_texts)
    except MemoryError:
        _send(connection, "resource", "PDF extraction exceeded the configured memory limit.")
    except Exception:
        _send(connection, "error", "PDF could not be parsed safely.")
    finally:
        connection.close()


def _apply_memory_limit(memory_limit_mb: int) -> None:
    # macOS reserves a multi-terabyte address space for Python processes, making
    # RLIMIT_AS lower than the current allocation invalid. Linux workers enforce
    # this cap in the hosted deployment; macOS still has timeout/text bounds.
    if resource is None or sys.platform == "darwin":
        return
    limit = memory_limit_mb * 1024 * 1024
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_AS)
    if hard_limit != resource.RLIM_INFINITY:
        limit = min(limit, hard_limit)
    resource.setrlimit(resource.RLIMIT_AS, (limit, hard_limit))


def _contains_active_content(
    value: object,
    *,
    seen: set[int] | None = None,
    depth: int = 0,
) -> bool:
    active_keys = {
        "/AA",
        "/EmbeddedFiles",
        "/JavaScript",
        "/JS",
        "/Launch",
        "/OpenAction",
        "/RichMedia",
    }
    if depth > 64:
        return True
    seen = seen or set()
    if hasattr(value, "get_object"):
        value = value.get_object()
    value_id = id(value)
    if value_id in seen:
        return False
    seen.add(value_id)
    if isinstance(value, dict):
        if active_keys.intersection(str(key) for key in value):
            return True
        return any(
            _contains_active_content(item, seen=seen, depth=depth + 1) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_active_content(item, seen=seen, depth=depth + 1) for item in value)
    return False


def _exceeds_decompression_ratio(
    value: object,
    *,
    max_decompression_ratio: float,
    stream_object_type: type[object],
    seen: set[int] | None = None,
) -> bool:
    seen = seen or set()
    if hasattr(value, "get_object"):
        value = value.get_object()
    value_id = id(value)
    if value_id in seen:
        return False
    seen.add(value_id)
    if isinstance(value, stream_object_type):
        encoded_length = len(value._data)
        if encoded_length and len(value.get_data()) / encoded_length > max_decompression_ratio:
            return True
    if isinstance(value, dict):
        return any(
            _exceeds_decompression_ratio(
                item,
                max_decompression_ratio=max_decompression_ratio,
                stream_object_type=stream_object_type,
                seen=seen,
            )
            for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(
            _exceeds_decompression_ratio(
                item,
                max_decompression_ratio=max_decompression_ratio,
                stream_object_type=stream_object_type,
                seen=seen,
            )
            for item in value
        )
    return False


def _send(
    connection: Any,
    kind: str,
    reason: str | None = None,
    *,
    page_texts: list[str] | None = None,
) -> None:
    payload: dict[str, object] = {"kind": kind}
    if reason is not None:
        payload["reason"] = reason
    if page_texts is not None:
        payload["page_texts"] = page_texts
    connection.send(payload)
