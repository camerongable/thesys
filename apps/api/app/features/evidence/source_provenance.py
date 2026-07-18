"""Source provenance, dedupe, and quality-signal helpers for evidence features."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "spm",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

PROMPT_INJECTION_PATTERNS = {
    "ignore_prior_instructions": re.compile(
        r"\b(ignore|disregard)\s+(all\s+)?(previous|prior|above)\s+instructions\b",
        re.IGNORECASE,
    ),
    "system_prompt_exfiltration": re.compile(
        r"\b(system prompt|developer message|hidden instructions?)\b",
        re.IGNORECASE,
    ),
    "model_role_claim": re.compile(
        r"\b(you are now|act as|pretend to be)\s+(a\s+)?(system|developer|admin)",
        re.IGNORECASE,
    ),
}

_POISONING_PATTERNS = {
    "policy_override": re.compile(
        r"\b(override|bypass|disable|ignore)\s+(the\s+)?(policy|guardrail|safety|security)\b",
        re.IGNORECASE,
    ),
    "tool_schema_reference": re.compile(
        r"\b(tool\s*(schema|call|invocation)|function\s*call|mcp\s*(server|tool))\b",
        re.IGNORECASE,
    ),
    "system_message_impersonation": re.compile(
        r"\b(system|developer|assistant)\s*(message|instruction)\s*:",
        re.IGNORECASE,
    ),
}

SOURCE_QUALITY_POLICY_VERSION = "source-quality:v2"
SNAPSHOT_POLICY_VERSION = "source-snapshot:v1"
SOURCE_TRUST_POLICY_VERSION = "source-trust:v1"


@dataclass(frozen=True)
class FetchFailureClassification:
    category: str
    retryable: bool
    risk_level: str


@dataclass(frozen=True)
class SourceTrust:
    """Deterministic source-trust decision made before evidence is embedded."""

    provenance_type: Literal[
        "user_upload",
        "approved_url",
        "external_search",
        "system_seed",
    ]
    trust_score: float
    injection_score: float
    poisoning_score: float
    security_status: Literal["quarantined", "approved", "blocked"]
    approved_by: str | None
    approved_at: datetime | None
    last_verified_at: datetime
    duplicate_source_count: int
    signals: tuple[str, ...]

    def metadata(self) -> dict[str, Any]:
        return {
            "policy_version": SOURCE_TRUST_POLICY_VERSION,
            "provenance_type": self.provenance_type,
            "trust_score": self.trust_score,
            "injection_score": self.injection_score,
            "poisoning_score": self.poisoning_score,
            "security_status": self.security_status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "last_verified_at": self.last_verified_at.isoformat(),
            "duplicate_source_count": self.duplicate_source_count,
            "signals": list(self.signals),
        }


def canonicalize_url(url: str) -> str:
    """Normalize a URL for project-scoped dedupe without changing fetch safety checks."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    netloc = hostname
    if parsed.port and not (
        (scheme == "http" and parsed.port == 80)
        or (scheme == "https" and parsed.port == 443)
    ):
        netloc = f"{hostname}:{parsed.port}"

    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def content_hash(text: str) -> str:
    """Return a stable hash of normalized extracted text for duplicate detection."""
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def byte_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def source_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return (parsed.hostname or "").lower() or None


def html_snapshot_metadata(
    *,
    html: str,
    final_url: str,
    fetched_at: datetime,
    canonical_url: str | None = None,
) -> dict[str, Any]:
    """Record inspectable snapshot metadata without storing full fetched HTML in JSON."""
    encoded = html.encode("utf-8")
    snapshot_hash = byte_hash(encoded)
    capture_url = final_url
    canonical = canonical_url or canonicalize_url(final_url)
    snapshot_id = f"html:{snapshot_hash[:16]}"
    return {
        "source_snapshot_id": snapshot_id,
        "snapshot": {
            "policy_version": SNAPSHOT_POLICY_VERSION,
            "source_snapshot_id": snapshot_id,
            "capture_url": capture_url,
            "final_url": final_url,
            "canonical_url": canonical,
            "captured_at": fetched_at.isoformat(),
            "byte_size": len(encoded),
            "byte_hash": snapshot_hash,
            "content_hash": snapshot_hash,
            "storage_key": None,
            "storage_absent_reason": "raw HTML snapshots are hash-only in local deterministic mode",
            "redaction_status": "metadata_only_no_raw_body_stored",
            "retention_policy": "metadata_only_project_lifetime",
            "screenshot": {
                "captured": False,
                "available": False,
                "storage_key": None,
                "reason": "screenshot capture is not configured in local ingestion",
            },
        },
        "raw_html_snapshot": {
            "source_snapshot_id": snapshot_id,
            "captured_at": fetched_at.isoformat(),
            "capture_url": capture_url,
            "final_url": final_url,
            "canonical_url": canonical,
            "byte_length": len(encoded),
            "byte_size": len(encoded),
            "byte_hash": snapshot_hash,
            "content_hash": snapshot_hash,
            "storage_key": None,
            "redaction_status": "metadata_only_no_raw_body_stored",
            "retention_policy": "metadata_only_project_lifetime",
            "screenshot": {
                "captured": False,
                "available": False,
                "storage_key": None,
                "reason": "screenshot capture is not configured in local ingestion",
            },
        }
    }


def detect_prompt_injection_markers(text: str) -> list[str]:
    """Detect fetched-page strings that should be treated as evidence-risk signals."""
    return [
        marker
        for marker, pattern in PROMPT_INJECTION_PATTERNS.items()
        if pattern.search(text)
    ]


def assess_source_trust(
    *,
    source_type: str,
    text: str,
    metadata: dict[str, Any],
    approved_by: object | None,
    duplicate_source_count: int = 0,
) -> SourceTrust:
    """Assess instruction and poisoning signals before a source becomes retrievable."""
    prompt_markers = detect_prompt_injection_markers(text)
    poisoning_matches = {
        name: len(pattern.findall(text)) for name, pattern in _POISONING_PATTERNS.items()
    }
    instruction_count = len(prompt_markers) + sum(poisoning_matches.values())
    hidden_unicode = _has_hidden_unicode(text)
    signals = [*prompt_markers]
    signals.extend(name for name, count in poisoning_matches.items() if count)
    if hidden_unicode:
        signals.append("hidden_unicode")
    if duplicate_source_count:
        signals.append("duplicate_source_content")
    signals = sorted(set(signals))

    injection_score = min(
        1.0,
        0.3 * len(prompt_markers)
        + 0.12 * min(instruction_count, 4)
        + (0.2 if hidden_unicode else 0.0),
    )
    poisoning_score = min(
        1.0,
        0.2 * instruction_count
        + 0.3 * sum(1 for count in poisoning_matches.values() if count)
        + (0.2 if hidden_unicode else 0.0)
        + min(duplicate_source_count * 0.35, 0.8),
    )
    quarantined = injection_score >= 0.6 or poisoning_score >= 0.7
    provenance_type = _provenance_type(source_type, metadata)
    base_trust = {
        "user_upload": 0.75,
        "approved_url": 0.65,
        "external_search": 0.5,
        "system_seed": 0.9,
    }[provenance_type]
    trust_score = round(max(0.0, base_trust - injection_score * 0.45 - poisoning_score * 0.35), 3)
    now = datetime.now(UTC)
    security_status: Literal["quarantined", "approved", "blocked"] = (
        "quarantined" if quarantined else "approved"
    )
    return SourceTrust(
        provenance_type=provenance_type,
        trust_score=trust_score,
        injection_score=round(injection_score, 3),
        poisoning_score=round(poisoning_score, 3),
        security_status=security_status,
        approved_by=str(approved_by) if approved_by is not None and not quarantined else None,
        approved_at=now if not quarantined else None,
        last_verified_at=now,
        duplicate_source_count=duplicate_source_count,
        signals=tuple(signals),
    )


def _provenance_type(
    source_type: str,
    metadata: dict[str, Any],
) -> Literal["user_upload", "approved_url", "external_search", "system_seed"]:
    origin = str(metadata.get("origin") or "")
    if origin == "system_seed":
        return "system_seed"
    if origin == "source_discovery" and metadata.get("search_provider"):
        return "external_search"
    if source_type == "url":
        return "approved_url"
    return "user_upload"


def _has_hidden_unicode(text: str) -> bool:
    return any(
        unicodedata.category(character) in {"Cf", "Cc"}
        and character not in {"\n", "\r", "\t"}
        for character in text
    )


def classify_fetch_failure(message: str) -> FetchFailureClassification:
    lowered = message.casefold()
    if "unsafe" in lowered or "blocked" in lowered or "private" in lowered:
        return FetchFailureClassification("blocked_security_policy", False, "high")
    if "exceeded" in lowered or "too large" in lowered:
        return FetchFailureClassification("response_limit_exceeded", False, "medium")
    if "http 404" in lowered or "http 410" in lowered:
        return FetchFailureClassification("not_found", False, "low")
    if "http 429" in lowered:
        return FetchFailureClassification("rate_limited", True, "medium")
    if "http 5" in lowered or "timeout" in lowered or "temporarily" in lowered:
        return FetchFailureClassification("transient_remote_failure", True, "medium")
    if "redirect" in lowered:
        return FetchFailureClassification("redirect_failure", False, "medium")
    return FetchFailureClassification("fetch_failed", False, "medium")


def fetch_failure_metadata(message: str) -> dict[str, Any]:
    """Convert fetch errors into metadata users and evals can inspect later."""
    classification = classify_fetch_failure(message)
    return {
        "fetch_failure": {
            "category": classification.category,
            "retryable": classification.retryable,
            "risk_level": classification.risk_level,
        }
    }


def pdf_page_lineage(page_texts: list[str]) -> list[dict[str, Any]]:
    """Map extracted PDF text back to page-level offsets and hashes."""
    lineage: list[dict[str, Any]] = []
    cursor = 0
    for index, text in enumerate(page_texts, start=1):
        normalized = re.sub(r"\s+", " ", text).strip()
        start = cursor
        end = start + len(normalized)
        lineage.append(
            {
                "page_number": index,
                "char_start": start,
                "char_end": end,
                "text_length": len(normalized),
                "content_hash": content_hash(normalized) if normalized else None,
            }
        )
        cursor = end + 2
    return lineage


def extraction_artifacts(
    *,
    text: str,
    metadata: dict[str, Any],
    extraction_method: str,
) -> dict[str, Any]:
    """Build deterministic extraction artifact metadata for citations and Inspect."""
    normalized = re.sub(r"\s+", " ", text).strip()
    source_snapshot_id = metadata.get("source_snapshot_id") or _source_snapshot_id(metadata)
    confidence = extraction_confidence(metadata)
    artifacts: list[dict[str, Any]] = [
        {
            "artifact_id": source_snapshot_id or f"text:{content_hash(normalized)[:16]}",
            "artifact_type": _artifact_type(metadata),
            "extraction_method": extraction_method,
            "char_start": 0,
            "char_end": len(normalized),
            "confidence": confidence,
        }
    ]
    table_metadata = table_extraction_metadata(text, metadata)
    if table_metadata["table_extraction"]["enabled"]:
        artifacts.extend(table_metadata["table_extraction"]["tables"])
    return {
        "extraction_method": extraction_method,
        "extraction_confidence": confidence,
        "source_snapshot_id": source_snapshot_id,
        "extraction_artifacts": artifacts,
        **table_metadata,
    }


def table_extraction_metadata(text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Extract simple markdown/pipe/tabular tables into structured deterministic metadata."""
    tables: list[dict[str, Any]] = []
    normalized_text = re.sub(r"\s+", " ", text).strip()
    lines = text.splitlines() if "\n" in text else re.split(r"\s{2,}", text)
    current: list[tuple[int, str]] = []
    cursor = 0
    for raw_line in lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        start = normalized_text.find(line, cursor)
        if start < 0:
            start = normalized_text.find(line)
        if start < 0:
            start = max(cursor, 0)
        cursor = start + len(line)
        if _looks_like_table_separator(line) and current:
            continue
        if _looks_like_table_row(line):
            current.append((start, line))
            continue
        if current:
            tables.extend(_table_from_rows(current, metadata, len(tables)))
            current = []
    if current:
        tables.extend(_table_from_rows(current, metadata, len(tables)))

    if not tables:
        return {
            "table_extraction": {
                "enabled": True,
                "table_count": 0,
                "tables": [],
                "confidence": 0.0,
                "reason": "no tabular structure detected",
            }
        }

    confidence = round(sum(table["confidence"] for table in tables) / len(tables), 4)
    return {
        "table_extraction": {
            "enabled": True,
            "table_count": len(tables),
            "tables": tables,
            "confidence": confidence,
            "reason": "deterministic table parser detected structured rows",
        }
    }


def chunk_quote_provenance(
    *,
    source_metadata: dict[str, Any],
    chunk_text: str,
    char_start: int,
    char_end: int,
    chunk_index: int,
) -> dict[str, Any]:
    """Return normalized chunk provenance fields used by retrieval and citations."""
    extraction_method = str(source_metadata.get("extraction_method") or "unknown")
    source_snapshot_id = source_metadata.get("source_snapshot_id") or _source_snapshot_id(
        source_metadata
    )
    page_number = _page_number_for_span(source_metadata.get("pdf_page_lineage"), char_start)
    section = _section_for_span(source_metadata.get("text_lineage"), char_start)
    table = _table_for_span(source_metadata.get("table_extraction"), char_start, char_end)
    confidence = extraction_confidence(source_metadata)
    region = table.get("region") if table else None
    quote_offsets = {
        "normalized_char_start": char_start,
        "normalized_char_end": char_end,
        "chunk_index": chunk_index,
    }
    provenance = {
        "extraction_method": extraction_method,
        "extraction_provider": source_metadata.get("extraction_provider"),
        "extraction_confidence": confidence,
        "source_snapshot_id": source_snapshot_id,
        "page_number": page_number,
        "section_heading": section.get("section_heading") if section else None,
        "table_id": table.get("table_id") if table else None,
        "region": region,
        "quote_offsets": quote_offsets,
        "quote_provenance": {
            "source_artifact_id": table.get("artifact_id") if table else source_snapshot_id,
            "artifact_type": (
                table.get("artifact_type") if table else _artifact_type(source_metadata)
            ),
            "text": chunk_text[:600],
            **quote_offsets,
        },
    }
    return {key: value for key, value in provenance.items() if value is not None}


def extraction_confidence(metadata: dict[str, Any]) -> float:
    """Infer an extraction-confidence score from parser/OCR/table metadata."""
    raw_value = metadata.get("extraction_confidence") or metadata.get("ocr_confidence")
    try:
        if raw_value is not None:
            return round(max(0.0, min(1.0, float(raw_value))), 4)
    except (TypeError, ValueError):
        pass
    method = str(metadata.get("extraction_method") or metadata.get("pdf_text_extraction") or "")
    if method in {"pypdf", "direct_decode", "direct_response_decode"}:
        return 0.86
    if "readable_html" in method or "html" in method:
        return 0.78
    if "multimodal" in method or metadata.get("ocr_fallback_used"):
        return 0.7
    return 0.6


def quality_metadata(
    *,
    source_type: str,
    url: str | None,
    source_date: datetime | None,
    ingested_at: datetime | None,
    classification: str | None,
    credibility_score: Decimal | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build source quality signals used by retrieval diagnostics and inspect panels."""
    reference_date = source_date or ingested_at
    recency_score = _recency_score(reference_date)
    markers = metadata.get("prompt_injection_markers")
    marker_count = len(markers) if isinstance(markers, list) else 0
    domain = source_domain(url)
    risk_level = _risk_level(
        source_type=source_type,
        domain=domain,
        marker_count=marker_count,
        classification=classification,
    )
    extraction_score = extraction_confidence(metadata)
    table_metadata = metadata.get("table_extraction")
    table_confidence = (
        float(table_metadata.get("confidence"))
        if isinstance(table_metadata, dict)
        and isinstance(table_metadata.get("confidence"), int | float)
        else None
    )
    screenshot_available = _screenshot_available(metadata)
    canonical_url = metadata.get("canonical_url")
    final_url = metadata.get("final_url")
    deduped = bool(metadata.get("duplicate_of_source_id") or metadata.get("deduped"))
    retrieval_weight = _retrieval_weight(
        credibility_score=credibility_score,
        recency_score=recency_score,
        risk_level=risk_level,
        extraction_confidence=extraction_score,
    )
    factors = _quality_factors(
        source_type=source_type,
        domain=domain,
        recency_score=recency_score,
        risk_level=risk_level,
        marker_count=marker_count,
        extraction_confidence=extraction_score,
        table_confidence=table_confidence,
        screenshot_available=screenshot_available,
        canonicalized=bool(canonical_url and final_url and canonical_url != final_url),
        deduped=deduped,
    )
    return {
        "source_quality": {
            "policy_version": SOURCE_QUALITY_POLICY_VERSION,
            "source_type": source_type,
            "domain": domain,
            "classification": classification,
            "credibility_score": (
                float(credibility_score) if credibility_score is not None else None
            ),
            "recency_score": recency_score,
            "risk_level": risk_level,
            "prompt_injection_marker_count": marker_count,
            "extraction_confidence": extraction_score,
            "ocr_confidence": metadata.get("ocr_confidence"),
            "table_extraction_confidence": table_confidence,
            "screenshot_available": screenshot_available,
            "canonicalized": bool(canonical_url and final_url and canonical_url != final_url),
            "deduped": deduped,
            "standard_text_extraction_quality": extraction_score,
            "retrieval_weight": retrieval_weight,
            "factors": factors,
            "explanation": _quality_explanation(factors),
        }
    }


def adjusted_credibility_score(
    *,
    source_type: str,
    url: str | None,
    metadata: dict[str, Any],
) -> Decimal:
    """Apply deterministic source-quality heuristics to the base credibility score."""
    base = {
        "url": Decimal("0.70"),
        "file": Decimal("0.65"),
        "transcript": Decimal("0.80"),
        "manual": Decimal("0.55"),
        "note": Decimal("0.50"),
    }.get(source_type, Decimal("0.50"))
    domain = source_domain(url)
    if domain and (domain.endswith(".gov") or domain.endswith(".edu")):
        base += Decimal("0.10")
    if domain and any(marker in domain for marker in ("docs.", "help.", "support.")):
        base += Decimal("0.03")
    markers = metadata.get("prompt_injection_markers")
    if isinstance(markers, list) and markers:
        base -= Decimal("0.15")
    return max(Decimal("0.10"), min(Decimal("0.95"), base))


def _recency_score(reference_date: datetime | None) -> float:
    if reference_date is None:
        return 0.5
    now = datetime.now(UTC)
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=UTC)
    age_days = max((now - reference_date).days, 0)
    if age_days <= 30:
        return 1.0
    if age_days <= 180:
        return 0.8
    if age_days <= 365:
        return 0.6
    return 0.3


def _risk_level(
    *,
    source_type: str,
    domain: str | None,
    marker_count: int,
    classification: str | None,
) -> str:
    if marker_count:
        return "high"
    if source_type == "url" and not domain:
        return "medium"
    if classification == "customer_discovery" and source_type == "transcript":
        return "low"
    if domain and (domain.endswith(".gov") or domain.endswith(".edu")):
        return "low"
    return "medium" if source_type in {"url", "file"} else "low"


def _retrieval_weight(
    *,
    credibility_score: Decimal | None,
    recency_score: float,
    risk_level: str,
    extraction_confidence: float = 0.6,
) -> float:
    credibility = float(credibility_score) if credibility_score is not None else 0.5
    risk_penalty = {"low": 0.0, "medium": 0.05, "high": 0.18}.get(risk_level, 0.05)
    return round(
        max(
            0.1,
            min(
                1.0,
                credibility * 0.56
                + recency_score * 0.2
                + extraction_confidence * 0.24
                - risk_penalty,
            ),
        ),
        4,
    )


def _source_snapshot_id(metadata: dict[str, Any]) -> str | None:
    snapshot = metadata.get("snapshot")
    if isinstance(snapshot, dict) and snapshot.get("source_snapshot_id"):
        return str(snapshot["source_snapshot_id"])
    raw = metadata.get("raw_html_snapshot")
    if isinstance(raw, dict) and raw.get("source_snapshot_id"):
        return str(raw["source_snapshot_id"])
    file_hash = metadata.get("file_content_hash")
    if file_hash:
        return f"file:{str(file_hash)[:16]}"
    content_hash_value = metadata.get("content_hash")
    if content_hash_value:
        return f"text:{str(content_hash_value)[:16]}"
    return None


def _artifact_type(metadata: dict[str, Any]) -> str:
    if metadata.get("raw_html_snapshot"):
        return "readability_text"
    if metadata.get("pdf_page_lineage"):
        return "pdf_text"
    if metadata.get("ocr_fallback_used"):
        return "ocr_text"
    if metadata.get("media_type") == "image":
        return "image_ocr_text"
    return "normalized_text"


def _looks_like_table_row(line: str) -> bool:
    if len(line) < 5:
        return False
    if "|" in line:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        return len([cell for cell in cells if cell and set(cell) != {"-"}]) >= 2
    if "\t" in line:
        return len([cell for cell in line.split("\t") if cell.strip()]) >= 2
    return False


def _looks_like_table_separator(line: str) -> bool:
    if "|" not in line:
        return False
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    return bool(cells) and all(set(cell) <= {"-", ":"} for cell in cells if cell)


def _table_from_rows(
    rows: list[tuple[int, str]],
    metadata: dict[str, Any],
    offset: int,
) -> list[dict[str, Any]]:
    parsed_rows: list[list[str]] = []
    row_offsets: list[tuple[int, int]] = []
    for start, line in rows:
        cells = (
            [cell.strip() for cell in line.strip("|").split("|")]
            if "|" in line
            else [cell.strip() for cell in line.split("\t")]
        )
        cells = [cell for cell in cells if cell and set(cell) != {"-"}]
        if len(cells) >= 2:
            parsed_rows.append(cells)
            row_offsets.append((start, start + len(line)))
    if len(parsed_rows) < 2:
        return []
    headers = parsed_rows[0]
    data_rows = parsed_rows[1:]
    if not data_rows:
        return []
    table_id = f"table-{offset + 1}"
    start = row_offsets[0][0]
    end = row_offsets[-1][1]
    page_number = _page_number_for_span(metadata.get("pdf_page_lineage"), start)
    cells = [
        {
            "row": row_index,
            "column": column_index,
            "header": headers[column_index] if column_index < len(headers) else None,
            "text": value,
        }
        for row_index, row in enumerate(data_rows, start=1)
        for column_index, value in enumerate(row)
    ]
    return [
        {
            "artifact_id": f"{_source_snapshot_id(metadata) or 'text'}:{table_id}",
            "artifact_type": "table",
            "table_id": table_id,
            "headers": headers,
            "rows": data_rows,
            "cells": cells,
            "summary": _table_summary(headers, data_rows),
            "page_number": page_number,
            "region": {
                "type": "table",
                "char_start": start,
                "char_end": end,
            },
            "confidence": 0.76 if len(data_rows) == 1 else 0.84,
        }
    ]


def _table_summary(headers: list[str], rows: list[list[str]]) -> str:
    row_summaries = []
    for row in rows[:3]:
        pairs = [
            f"{headers[index] if index < len(headers) else f'Column {index + 1}'}: {value}"
            for index, value in enumerate(row)
        ]
        row_summaries.append("; ".join(pairs))
    return " | ".join(row_summaries)


def _page_number_for_span(lineage: Any, char_start: int) -> int | None:
    if not isinstance(lineage, list):
        return None
    for page in lineage:
        if not isinstance(page, dict):
            continue
        start = page.get("char_start")
        end = page.get("char_end")
        if isinstance(start, int) and isinstance(end, int) and start <= char_start <= end:
            page_number = page.get("page_number")
            return int(page_number) if isinstance(page_number, int) else None
    return None


def _section_for_span(text_lineage: Any, char_start: int) -> dict[str, Any] | None:
    if not isinstance(text_lineage, dict):
        return None
    sections = text_lineage.get("sections")
    if not isinstance(sections, list):
        return None
    candidate: dict[str, Any] | None = None
    for section in sections:
        if not isinstance(section, dict):
            continue
        start = section.get("char_start")
        end = section.get("char_end")
        if isinstance(start, int) and isinstance(end, int) and start <= char_start <= end:
            return section
        if isinstance(start, int) and start <= char_start:
            candidate = section
    return candidate


def _table_for_span(table_extraction: Any, char_start: int, char_end: int) -> dict[str, Any] | None:
    if not isinstance(table_extraction, dict):
        return None
    tables = table_extraction.get("tables")
    if not isinstance(tables, list):
        return None
    for table in tables:
        if not isinstance(table, dict):
            continue
        region = table.get("region")
        if not isinstance(region, dict):
            continue
        start = region.get("char_start")
        end = region.get("char_end")
        if (
            isinstance(start, int)
            and isinstance(end, int)
            and start <= char_end
            and end >= char_start
        ):
            return table
    return None


def _screenshot_available(metadata: dict[str, Any]) -> bool:
    snapshot = metadata.get("snapshot")
    if isinstance(snapshot, dict):
        screenshot = snapshot.get("screenshot")
        if isinstance(screenshot, dict):
            return bool(screenshot.get("available") or screenshot.get("captured"))
    raw = metadata.get("raw_html_snapshot")
    if isinstance(raw, dict):
        screenshot = raw.get("screenshot")
        if isinstance(screenshot, dict):
            return bool(screenshot.get("available") or screenshot.get("captured"))
    return False


def _quality_factors(
    *,
    source_type: str,
    domain: str | None,
    recency_score: float,
    risk_level: str,
    marker_count: int,
    extraction_confidence: float,
    table_confidence: float | None,
    screenshot_available: bool,
    canonicalized: bool,
    deduped: bool,
) -> list[dict[str, Any]]:
    factors: list[dict[str, Any]] = [
        {"name": "source_type", "impact": "neutral", "detail": source_type},
        {
            "name": "recency",
            "impact": "positive" if recency_score >= 0.8 else "neutral",
            "score": recency_score,
        },
        {
            "name": "extraction_confidence",
            "impact": "positive" if extraction_confidence >= 0.75 else "warning",
            "score": extraction_confidence,
        },
    ]
    if domain and (domain.endswith(".gov") or domain.endswith(".edu")):
        factors.append({"name": "authority_domain", "impact": "positive", "detail": domain})
    if marker_count:
        factors.append(
            {
                "name": "prompt_injection_markers",
                "impact": "negative",
                "count": marker_count,
            }
        )
    if risk_level == "high":
        factors.append({"name": "risk_level", "impact": "negative", "detail": risk_level})
    if table_confidence is not None:
        factors.append(
            {
                "name": "table_extraction_confidence",
                "impact": "positive" if table_confidence >= 0.75 else "warning",
                "score": table_confidence,
            }
        )
    factors.append(
        {
            "name": "screenshot_snapshot",
            "impact": "positive" if screenshot_available else "neutral",
            "available": screenshot_available,
        }
    )
    if canonicalized:
        factors.append({"name": "canonical_url", "impact": "positive"})
    if deduped:
        factors.append({"name": "duplicate_content", "impact": "warning"})
    return factors


def _quality_explanation(factors: list[dict[str, Any]]) -> str:
    positives = [
        str(factor["name"]).replace("_", " ")
        for factor in factors
        if factor.get("impact") == "positive"
    ]
    warnings = [
        str(factor["name"]).replace("_", " ")
        for factor in factors
        if factor.get("impact") in {"warning", "negative"}
    ]
    parts: list[str] = []
    if positives:
        parts.append(f"Positive signals: {', '.join(positives[:4])}.")
    if warnings:
        parts.append(f"Review signals: {', '.join(warnings[:4])}.")
    return " ".join(parts) or "No unusual source-quality signals."
