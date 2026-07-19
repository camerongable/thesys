"""Citation verification and drilldown shaping helpers for Ask Thesys."""

import re
from dataclasses import dataclass
from typing import Any

from app.schemas.guide import GuideCitationDetailRead

_SUPPORT_TERM_PATTERN = re.compile(r"[a-z0-9][a-z0-9'-]{2,}")
_SUPPORT_STOP_WORDS = {
    "about",
    "after",
    "answer",
    "because",
    "could",
    "does",
    "from",
    "guide",
    "have",
    "into",
    "just",
    "more",
    "most",
    "need",
    "only",
    "other",
    "should",
    "source",
    "than",
    "that",
    "their",
    "these",
    "this",
    "those",
    "what",
    "when",
    "which",
    "with",
    "would",
}


@dataclass(frozen=True)
class VerifiedCitation:
    source_id: str
    chunk_id: str


def verify_grounded_citations(
    search_output: dict[str, Any],
    answer: str,
    citations: list[dict[str, Any]],
) -> list[VerifiedCitation]:
    """Return only citations with an exact retrieved quote that supports the answer."""
    retrieved = _retrieved_chunks(search_output)
    answer_terms = _support_terms(answer)
    verified: list[VerifiedCitation] = []
    seen_sources: set[str] = set()
    for citation in citations:
        source_id = str(citation.get("source_id") or "")
        chunk_id = str(citation.get("chunk_id") or "")
        supporting_quote = str(citation.get("supporting_quote") or "").strip()
        result = retrieved.get((source_id, chunk_id))
        if not source_id or not chunk_id or not supporting_quote or result is None:
            continue
        text = str(result.get("text") or "")
        if _normalized_text(supporting_quote) not in _normalized_text(text):
            continue
        if len(answer_terms & _support_terms(supporting_quote)) < 2:
            continue
        if source_id in seen_sources:
            continue
        seen_sources.add(source_id)
        verified.append(VerifiedCitation(source_id=source_id, chunk_id=chunk_id))
    return verified


def citation_details_from_search(
    search_output: dict[str, Any],
    context_pack: dict[str, Any] | None,
    cited_evidence_ids: list[str],
    *,
    cited_chunk_ids: list[str] | None = None,
    verifier_status: str = "weak",
) -> list[GuideCitationDetailRead]:
    results = search_output.get("results")
    if not isinstance(results, list):
        return []
    cited = set(cited_evidence_ids)
    cited_chunks = set(cited_chunk_ids or [])
    context_item_ids = context_item_ids_by_source(context_pack)
    memory_ids = memory_ids_from_context_pack(context_pack)
    details: list[GuideCitationDetailRead] = []
    seen_sources: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        source_id = str(result.get("source_id") or "")
        if not source_id or source_id not in cited or source_id in seen_sources:
            continue
        chunk_id = str(result.get("chunk_id") or "")
        if cited_chunks and chunk_id not in cited_chunks:
            continue
        seen_sources.add(source_id)
        text = str(result.get("text") or "")
        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        source_quality = (
            metadata.get("source_quality")
            if isinstance(metadata.get("source_quality"), dict)
            else {}
        )
        snapshot = metadata.get("snapshot") if isinstance(metadata.get("snapshot"), dict) else {}
        if not snapshot and isinstance(metadata.get("raw_html_snapshot"), dict):
            snapshot = {"raw_html_snapshot": metadata["raw_html_snapshot"]}
        extraction = citation_extraction_metadata(metadata)
        details.append(
            GuideCitationDetailRead(
                source_id=source_id,
                chunk_id=chunk_id or None,
                title=str(result.get("title")) if result.get("title") else None,
                url=str(result.get("url")) if result.get("url") else None,
                source_type=str(result.get("source_type")) if result.get("source_type") else None,
                excerpt=text[:600] if text else None,
                score=optional_float(result.get("rerank_score") or result.get("score")),
                verifier_status=verifier_status,
                context_item_ids=context_item_ids.get(source_id, []),
                memory_ids=memory_ids,
                metadata=metadata,
                provenance=citation_provenance_metadata(metadata),
                source_quality=source_quality,
                extraction=extraction,
                snapshot=snapshot,
                page_number=optional_int(metadata.get("page_number")),
                section_heading=str(metadata.get("section_heading"))
                if metadata.get("section_heading")
                else None,
                table_id=str(metadata.get("table_id")) if metadata.get("table_id") else None,
                region=metadata.get("region") if isinstance(metadata.get("region"), dict) else None,
                quote_offsets=metadata.get("quote_offsets")
                if isinstance(metadata.get("quote_offsets"), dict)
                else None,
                warnings=citation_warnings(metadata),
            )
        )
    return details


def _retrieved_chunks(search_output: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    results = search_output.get("results")
    if not isinstance(results, list):
        return {}
    return {
        (str(result.get("source_id") or ""), str(result.get("chunk_id") or "")): result
        for result in results
        if isinstance(result, dict) and result.get("source_id") and result.get("chunk_id")
    }


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _support_terms(value: str) -> set[str]:
    return {
        match.group(0)
        for match in _SUPPORT_TERM_PATTERN.finditer(value.casefold())
        if match.group(0) not in _SUPPORT_STOP_WORDS
    }


def citation_extraction_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "extraction_method",
        "extraction_provider",
        "extraction_model",
        "extraction_confidence",
        "ocr_confidence",
        "pdf_text_extraction",
        "table_extraction",
        "readability",
    }
    return {key: metadata[key] for key in keys if key in metadata and metadata[key] is not None}


def citation_provenance_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "source_snapshot_id",
        "page_number",
        "section_heading",
        "table_id",
        "region",
        "quote_offsets",
        "quote_provenance",
    }
    return {key: metadata[key] for key in keys if key in metadata and metadata[key] is not None}


def citation_warnings(metadata: dict[str, Any]) -> list[str]:
    warnings = metadata.get("warnings")
    if isinstance(warnings, list):
        return [str(warning) for warning in warnings]
    source_quality = metadata.get("source_quality")
    if isinstance(source_quality, dict) and source_quality.get("risk_level") == "high":
        return ["high_source_quality_risk"]
    return []


def context_item_ids_by_source(context_pack: dict[str, Any] | None) -> dict[str, list[str]]:
    if not context_pack:
        return {}
    items = context_pack.get("items")
    if not isinstance(items, list):
        return {}
    result: dict[str, list[str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        provenance = item.get("provenance")
        if not isinstance(provenance, dict):
            continue
        metadata = provenance.get("metadata")
        if not isinstance(metadata, dict):
            continue
        source_id = str(metadata.get("source_id") or "")
        item_id = str(item.get("id") or "")
        if source_id and item_id:
            result.setdefault(source_id, []).append(item_id)
    return result


def memory_ids_from_context_pack(context_pack: dict[str, Any] | None) -> list[str]:
    if not context_pack:
        return []
    metadata = context_pack.get("metadata")
    if isinstance(metadata, dict):
        selected_ids = metadata.get("selected_memory_ids")
        if isinstance(selected_ids, list):
            return _unique_strings(str(item) for item in selected_ids if item)
    items = context_pack.get("items")
    if not isinstance(items, list):
        return []
    memory_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "memory":
            continue
        provenance = item.get("provenance")
        if isinstance(provenance, dict) and provenance.get("entity_id"):
            memory_ids.append(str(provenance["entity_id"]))
    return _unique_strings(memory_ids)


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _unique_strings(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
