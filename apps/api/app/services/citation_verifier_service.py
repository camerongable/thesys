"""Citation quality checks shared by generated artifacts and agentic research."""

import uuid
from dataclasses import dataclass
from typing import Literal

from app.schemas.artifacts import Citation, ClaimDraft
from app.schemas.evidence import EvidenceRetrievalResultRead

CitationSupportStatus = Literal[
    "supported",
    "weakly_supported",
    "unsupported",
    "source_missing",
    "stale_source",
    "filtered_as_unsafe",
]


@dataclass(frozen=True)
class CitationVerification:
    """Support check for one citation against the retrieved evidence set."""

    citation: Citation
    valid_id: bool
    text_overlap: float
    quote_overlap: float
    supported: bool
    reason: str
    status: CitationSupportStatus


@dataclass(frozen=True)
class ClaimVerification:
    claim: ClaimDraft
    verified_citations: list[Citation]
    weak_citations: list[CitationVerification]
    unsupported_reason: str | None
    outcome: CitationSupportStatus


def verify_claims(
    claims: list[ClaimDraft],
    selected_evidence: list[EvidenceRetrievalResultRead],
) -> list[ClaimVerification]:
    """Verify every generated claim against the evidence selected for synthesis."""
    return [_verify_claim(claim, selected_evidence) for claim in claims]


def claim_outcome_records(verifications: list[ClaimVerification]) -> list[dict[str, object]]:
    """Serialize claim support outcomes for artifact metadata and evals."""
    return [
        {
            "claim": verification.claim.text,
            "outcome": verification.outcome,
            "unsupported_reason": verification.unsupported_reason,
            "verified_citation_count": len(verification.verified_citations),
            "weak_citation_count": len(verification.weak_citations),
            "weak_citation_reasons": [
                {"reason": item.reason, "status": item.status}
                for item in verification.weak_citations
            ],
        }
        for verification in verifications
    ]


def audited_claim_outcome_records(claims: list[ClaimDraft]) -> list[dict[str, object]]:
    """Summarize already-audited claim support for persisted artifact content."""
    return [
        {
            "claim": claim.text,
            "outcome": _outcome_from_support_level(claim.support_level, bool(claim.citations)),
            "support_level": claim.support_level,
            "citation_count": len(claim.citations),
        }
        for claim in claims
    ]


def citation_is_supported(
    citation: Citation,
    claim_text: str,
    selected_evidence: list[EvidenceRetrievalResultRead],
) -> CitationVerification:
    """Check citation IDs and rough text/quote overlap against retrieved evidence."""
    evidence = _evidence_for_citation(citation, selected_evidence)
    if evidence is None:
        return CitationVerification(
            citation=citation,
            valid_id=False,
            text_overlap=0.0,
            quote_overlap=0.0,
            supported=False,
            reason="citation_id_not_retrieved",
            status="source_missing",
        )
    if _is_filtered_as_unsafe(evidence):
        return CitationVerification(
            citation=citation,
            valid_id=True,
            text_overlap=0.0,
            quote_overlap=0.0,
            supported=False,
            reason="source_filtered_as_unsafe",
            status="filtered_as_unsafe",
        )
    claim_overlap = _overlap(claim_text, evidence.text)
    quote_overlap = _overlap(citation.quote or "", evidence.text) if citation.quote else 1.0
    supported = quote_overlap >= 0.45 and (claim_overlap >= 0.08 or bool(citation.quote))
    status: CitationSupportStatus = "supported" if supported else "weakly_supported"
    if _is_stale(evidence):
        supported = False
        status = "stale_source"
    return CitationVerification(
        citation=citation,
        valid_id=True,
        text_overlap=round(claim_overlap, 3),
        quote_overlap=round(quote_overlap, 3),
        supported=supported,
        reason="supported" if supported else status,
        status=status,
    )


def _verify_claim(
    claim: ClaimDraft,
    selected_evidence: list[EvidenceRetrievalResultRead],
) -> ClaimVerification:
    checks = [
        citation_is_supported(citation, claim.text, selected_evidence)
        for citation in claim.citations
    ]
    verified = [check.citation for check in checks if check.supported]
    weak = [check for check in checks if not check.supported]
    unsupported_reason = None
    outcome: CitationSupportStatus = "supported" if verified else "unsupported"
    if claim.support_level == "supported" and not verified:
        unsupported_reason = "supported_claim_has_no_verified_citation"
        outcome = _weakest_status(weak)
    elif claim.support_level in {"partial", "inference"} and not claim.citations:
        unsupported_reason = "non-supported_claim_has_no_citation"
        outcome = "unsupported"
    elif weak:
        outcome = "weakly_supported"
    return ClaimVerification(
        claim=claim,
        verified_citations=verified,
        weak_citations=weak,
        unsupported_reason=unsupported_reason,
        outcome=outcome,
    )


def _evidence_for_citation(
    citation: Citation,
    selected_evidence: list[EvidenceRetrievalResultRead],
) -> EvidenceRetrievalResultRead | None:
    by_chunk: dict[uuid.UUID, EvidenceRetrievalResultRead] = {
        result.chunk_id: result for result in selected_evidence
    }
    by_source: dict[uuid.UUID, EvidenceRetrievalResultRead] = {
        result.source_id: result for result in selected_evidence
    }
    if citation.chunk_id is not None:
        return by_chunk.get(citation.chunk_id)
    return by_source.get(citation.source_id)


def _overlap(left: str, right: str) -> float:
    left_terms = _terms(left)
    right_terms = _terms(right)
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / max(len(left_terms), 1)


def _weakest_status(weak: list[CitationVerification]) -> CitationSupportStatus:
    for status in ("filtered_as_unsafe", "source_missing", "stale_source", "weakly_supported"):
        if any(item.status == status for item in weak):
            return status
    return "unsupported"


def _outcome_from_support_level(support_level: str, has_citation: bool) -> CitationSupportStatus:
    if support_level == "supported" and has_citation:
        return "supported"
    if support_level == "partial" and has_citation:
        return "weakly_supported"
    return "unsupported"


def _is_filtered_as_unsafe(evidence: EvidenceRetrievalResultRead) -> bool:
    markers = evidence.metadata.get("prompt_injection_markers")
    return isinstance(markers, list) and bool(markers)


def _is_stale(evidence: EvidenceRetrievalResultRead) -> bool:
    freshness = evidence.metadata.get("freshness_score")
    try:
        return freshness is not None and float(freshness) <= 0.1
    except (TypeError, ValueError):
        return False


def _terms(value: str) -> set[str]:
    return {
        "".join(ch for ch in token.casefold() if ch.isalnum())
        for token in value.split()
        if len("".join(ch for ch in token.casefold() if ch.isalnum())) >= 4
    }
