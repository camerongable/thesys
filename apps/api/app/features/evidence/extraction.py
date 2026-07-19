"""Document and text extraction helpers for the evidence feature."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

from app.common import metadata as metadata_utils
from app.features.evidence import source_provenance

TOKEN_RE = re.compile(r"\S+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ParsedSource:
    """Normalized extraction result passed into the chunking/embedding pipeline."""

    title: str | None
    text: str
    content_type: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class TextChunk:
    text: str
    char_start: int
    char_end: int


def parse_html(
    html: str,
    *,
    content_type: str,
    final_url: str | None = None,
    fetched_at: datetime | None = None,
) -> ParsedSource:
    """Extract readable page text plus snapshot and section-lineage metadata."""
    parser = _ReadableHtmlParser()
    parser.feed(html)
    title = normalize_text(parser.title) or None
    text = normalize_text(" ".join(parser.text_parts))
    canonical_url = source_provenance.canonicalize_url(final_url) if final_url else None
    markers = source_provenance.detect_prompt_injection_markers(text)
    metadata: dict[str, Any] = {
        "canonical_url": canonical_url,
        "final_url": final_url,
        "domain": source_provenance.source_domain(canonical_url),
        "fetched_at": fetched_at.isoformat() if fetched_at else None,
        "retrieved_at": fetched_at.isoformat() if fetched_at else None,
        "response_content_type": content_type,
        "extraction_method": "readable_html_parser_v3",
        "extraction_provider": "python_html_parser",
        "extraction_confidence": parser.confidence,
        "readability": {
            "parser": "html.parser",
            "parser_version": "stdlib",
            "policy_version": "readability-html:v3",
            "fallback_used": parser.fallback_used,
            "fallback_reason": parser.fallback_reason,
            "warnings": parser.warnings,
            "maintained_parser": "python-stdlib-html.parser",
        },
        "prompt_injection_markers": markers,
        "text_lineage": {
            "page_title": title,
            "sections": parser.sections[:50],
        },
    }
    if final_url and fetched_at:
        metadata = _merge_metadata(
            metadata,
            source_provenance.html_snapshot_metadata(
                html=html,
                final_url=final_url,
                fetched_at=fetched_at,
                canonical_url=canonical_url,
            ),
        )
    return ParsedSource(title=title, text=text, content_type=content_type, metadata=metadata)


def direct_response_metadata(
    *,
    content: bytes,
    text: str,
    content_type: str | None,
    final_url: str,
    fetched_at: datetime,
) -> dict[str, Any]:
    """Build metadata for non-HTML URL responses decoded directly from bytes."""
    canonical_url = source_provenance.canonicalize_url(final_url)
    return {
        "canonical_url": canonical_url,
        "final_url": final_url,
        "domain": source_provenance.source_domain(canonical_url),
        "fetched_at": fetched_at.isoformat(),
        "retrieved_at": fetched_at.isoformat(),
        "response_content_type": content_type,
        "response_byte_length": len(content),
        "prompt_injection_markers": source_provenance.detect_prompt_injection_markers(text),
        "extraction_method": "direct_response_decode",
    }


def file_metadata(*, filename: str, body: bytes) -> dict[str, Any]:
    """Return stable file identity metadata shared by upload extraction paths."""
    return {
        "filename": filename,
        "file_size_bytes": len(body),
        "file_content_hash": source_provenance.byte_hash(body),
    }


def image_upload_metadata(
    *,
    filename: str,
    content_type: str,
    body: bytes,
    extraction_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge multimodal image extraction metadata with deterministic file identity."""
    return _merge_metadata(
        file_metadata(filename=filename, body=body),
        _merge_metadata(
            extraction_metadata,
            {
                "image_metadata": {
                    "content_type": content_type,
                    "byte_length": len(body),
                    "content_hash": source_provenance.byte_hash(body),
                }
            },
        ),
    )


def pdf_text_metadata(
    *,
    filename: str,
    body: bytes,
    page_texts: list[str],
    normalized_text: str,
) -> dict[str, Any]:
    """Build parser metadata for text-native PDFs before optional OCR fallback."""
    return {
        **file_metadata(filename=filename, body=body),
        "media_type": "pdf",
        "content_type": "application/pdf",
        "extraction_method": "pypdf",
        "extraction_confidence": 0.86,
        "pdf_text_extraction": "pypdf",
        "pdf_page_count": len(page_texts),
        "pdf_page_lineage": source_provenance.pdf_page_lineage(page_texts),
        "extracted_text_length": len(normalized_text),
    }


def pdf_ocr_fallback_metadata(
    *,
    base_metadata: dict[str, Any],
    extraction_metadata: dict[str, Any],
    extraction_provider: str,
    extraction_model: str,
    extraction_warnings: list[str],
    pypdf_text_length: int,
) -> dict[str, Any]:
    """Merge OCR/multimodal fallback metadata into the base PDF parse metadata."""
    method = (
        "pdf_ocr_deterministic"
        if extraction_provider == "deterministic"
        else "pdf_ocr_litellm"
    )
    return _merge_metadata(
        base_metadata,
        {
            **extraction_metadata,
            "pdf_text_extraction": "multimodal_fallback",
            "pypdf_extracted_text_length": pypdf_text_length,
            "ocr_fallback_used": True,
            "extraction_method": extraction_metadata.get("extraction_method", method),
            "extraction_confidence": extraction_metadata.get("extraction_confidence", 0.72),
            "ocr_confidence": extraction_metadata.get("ocr_confidence", 0.72),
            "ocr_fallback": extraction_metadata.get(
                "ocr_fallback",
                {
                    "used": True,
                    "provider": extraction_provider,
                    "model": extraction_model,
                    "method": method,
                    "confidence": extraction_metadata.get("ocr_confidence", 0.72),
                    "page_numbers": [1],
                    "warnings": extraction_warnings,
                },
            ),
        },
    )


def text_upload_metadata(
    *,
    filename: str,
    content_type: str,
    body: bytes,
) -> dict[str, Any]:
    """Build metadata for directly decoded text or Markdown uploads."""
    return {
        **file_metadata(filename=filename, body=body),
        "media_type": "text",
        "content_type": content_type,
        "extraction_method": "direct_decode",
        "extraction_confidence": 0.9,
        "text_extraction": "direct_decode",
    }


def decode_bytes(body: bytes) -> str:
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("latin-1", errors="ignore")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(
    text: str,
    *,
    target_tokens: int = 950,
    overlap_tokens: int = 150,
) -> list[TextChunk]:
    token_values = tokens(text)
    if len(token_values) <= target_tokens:
        return [TextChunk(text=text, char_start=0, char_end=len(text))] if text else []

    chunks: list[TextChunk] = []
    start = 0
    search_from = 0
    while start < len(token_values):
        end = min(start + target_tokens, len(token_values))
        chunk_value = " ".join(token_values[start:end])
        char_start = text.find(chunk_value, search_from)
        if char_start < 0:
            char_start = text.find(chunk_value)
        if char_start < 0:
            char_start = search_from
        char_end = min(len(text), char_start + len(chunk_value))
        chunks.append(TextChunk(text=chunk_value, char_start=char_start, char_end=char_end))
        search_from = max(char_start + 1, char_end - max(overlap_tokens, 1))
        if end == len(token_values):
            break
        start = max(0, end - overlap_tokens)
    return chunks


def tokens(text: str) -> list[str]:
    return [match.group(0) for match in TOKEN_RE.finditer(text)]


def summarize_text(text: str) -> str:
    sentences = [sentence.strip() for sentence in SENTENCE_RE.split(text) if sentence.strip()]
    if not sentences:
        return truncate_text(text, 500)
    return truncate_text(" ".join(sentences[:2]), 700)


def classify_text(source_type: str, title: str | None, text: str) -> str:
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


def preview_text(text: str | None) -> str | None:
    if not text:
        return None
    return truncate_text(text, 220)


def truncate_text(value: str, max_length: int) -> str:
    return value[:max_length]


def _merge_metadata(
    base: dict[str, Any],
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    return metadata_utils.merge_metadata(base, extra)


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text_parts: list[str] = []
        self.sections: list[dict[str, Any]] = []
        self.warnings: list[str] = []
        self.fallback_used = False
        self.fallback_reason: str | None = None
        self.confidence = 0.78
        self._skip_depth = 0
        self._boilerplate_depth = 0
        self._in_title = False
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._current_heading: str | None = None
        self._cursor = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag in {"nav", "footer", "header", "aside", "form"}:
            self._boilerplate_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in {"h1", "h2", "h3"} and self._skip_depth == 0:
            self._heading_tag = tag
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in {"nav", "footer", "header", "aside", "form"} and self._boilerplate_depth > 0:
            self._boilerplate_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag == self._heading_tag:
            heading = normalize_text(" ".join(self._heading_parts))
            if heading:
                self._current_heading = heading[:200]
            self._heading_tag = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += f" {data}"
            return
        if self._skip_depth > 0:
            return
        text = normalize_text(data)
        if not text:
            return
        if self._boilerplate_depth > 0:
            self.warnings.append("boilerplate_text_skipped")
            return
        if self._heading_tag:
            self._heading_parts.append(text)
        start = self._cursor
        end = start + len(text)
        self.text_parts.append(text)
        self.sections.append(
            {
                "section": self._current_heading or normalize_text(self.title) or None,
                "section_heading": self._current_heading or normalize_text(self.title) or None,
                "heading_tag": self._heading_tag,
                "char_start": start,
                "char_end": end,
                "text_preview": truncate_text(text, 300),
            }
        )
        self._cursor = end + 1
