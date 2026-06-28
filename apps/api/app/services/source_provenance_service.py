"""Source provenance, dedupe, and quality-signal helpers for evidence ingestion."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
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


@dataclass(frozen=True)
class FetchFailureClassification:
    category: str
    retryable: bool
    risk_level: str


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
) -> dict[str, Any]:
    """Record inspectable snapshot metadata without storing full fetched HTML in JSON."""
    return {
        "raw_html_snapshot": {
            "captured_at": fetched_at.isoformat(),
            "final_url": final_url,
            "byte_length": len(html.encode("utf-8")),
            "content_hash": byte_hash(html.encode("utf-8")),
            "screenshot": {
                "captured": False,
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
    return {
        "source_quality": {
            "source_type": source_type,
            "domain": domain,
            "classification": classification,
            "credibility_score": (
                float(credibility_score) if credibility_score is not None else None
            ),
            "recency_score": recency_score,
            "risk_level": risk_level,
            "prompt_injection_marker_count": marker_count,
            "retrieval_weight": _retrieval_weight(
                credibility_score=credibility_score,
                recency_score=recency_score,
                risk_level=risk_level,
            ),
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
) -> float:
    credibility = float(credibility_score) if credibility_score is not None else 0.5
    risk_penalty = {"low": 0.0, "medium": 0.05, "high": 0.18}.get(risk_level, 0.05)
    return round(max(0.1, min(1.0, credibility * 0.75 + recency_score * 0.25 - risk_penalty)), 4)
