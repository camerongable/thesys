"""Citation quality checks shared by generated artifacts and agentic research."""

import uuid
from dataclasses import dataclass

from app.schemas.artifacts import Citation, ClaimDraft
from app.schemas.evidence import EvidenceRetrievalResultRead


@dataclass(frozen=True)
class CitationVerification:
    """Support check for one citation against the retrieved evidence set."""

    citation: Citation
    valid_id: bool
    text_overlap: float
    quote_overlap: float
    supported: bool
    reason: str


@dataclass(frozen=True)
class ClaimVerification:
    claim: ClaimDraft
    verified_citations: list[Citation]
    weak_citations: list[CitationVerification]
    unsupported_reason: str | None


def verify_claims(
    claims: list[ClaimDraft],
    selected_evidence: list[EvidenceRetrievalResultRead],
) -> list[ClaimVerification]:
    """Verify every generated claim against the evidence selected for synthesis."""
    return [_verify_claim(claim, selected_evidence) for claim in claims]


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
        )
    claim_overlap = _overlap(claim_text, evidence.text)
    quote_overlap = _overlap(citation.quote or "", evidence.text) if citation.quote else 1.0
    supported = quote_overlap >= 0.45 and (claim_overlap >= 0.08 or bool(citation.quote))
    return CitationVerification(
        citation=citation,
        valid_id=True,
        text_overlap=round(claim_overlap, 3),
        quote_overlap=round(quote_overlap, 3),
        supported=supported,
        reason="supported" if supported else "weak_text_overlap",
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
    if claim.support_level == "supported" and not verified:
        unsupported_reason = "supported_claim_has_no_verified_citation"
    elif claim.support_level in {"partial", "inference"} and not claim.citations:
        unsupported_reason = "non-supported_claim_has_no_citation"
    return ClaimVerification(
        claim=claim,
        verified_citations=verified,
        weak_citations=weak,
        unsupported_reason=unsupported_reason,
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


def _terms(value: str) -> set[str]:
    return {
        "".join(ch for ch in token.casefold() if ch.isalnum())
        for token in value.split()
        if len("".join(ch for ch in token.casefold() if ch.isalnum())) >= 4
    }
