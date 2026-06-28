"""Citation audit helpers for agentic research memo drafts."""

from app.features.evidence import citation_verifier
from app.features.research.strategy import clean_list
from app.schemas.artifacts import Citation, ClaimDraft
from app.schemas.evidence import EvidenceRetrievalResultRead
from app.schemas.research import AgenticResearchMemoDraft, ResearchFindingDraft


def audit_citations(
    memo: AgenticResearchMemoDraft,
    selected_evidence: list[EvidenceRetrievalResultRead],
) -> AgenticResearchMemoDraft:
    """Return a memo copy with claims and citations constrained to retrieved evidence."""
    unsupported = list(memo.unsupported_claims)
    claims: list[ClaimDraft] = []
    citations: list[Citation] = []
    for verification in citation_verifier.verify_claims(memo.claims, selected_evidence):
        claim = verification.claim
        if verification.unsupported_reason:
            unsupported.append(f"{claim.text} ({verification.unsupported_reason})")
            claims.append(
                claim.model_copy(update={"support_level": "unsupported", "citations": []})
            )
            continue
        support_level = "partial" if verification.weak_citations else claim.support_level
        claims.append(
            claim.model_copy(
                update={
                    "support_level": support_level,
                    "citations": verification.verified_citations,
                }
            )
        )
        if verification.weak_citations and claim.support_level == "supported":
            unsupported.append(f"{claim.text} (weak_text_overlap)")
        citations.extend(verification.verified_citations)

    audited_findings: list[ResearchFindingDraft] = []
    for finding in memo.findings:
        valid_citations = [
            citation
            for citation in finding.citations
            if citation_verifier.citation_is_supported(
                citation,
                finding.finding,
                selected_evidence,
            ).supported
        ]
        audited_findings.append(finding.model_copy(update={"citations": valid_citations}))
        citations.extend(valid_citations)

    for citation in memo.citations:
        if citation_verifier.citation_is_supported(
            citation,
            citation.quote or citation.title or "",
            selected_evidence,
        ).supported:
            citations.append(citation)

    return memo.model_copy(
        update={
            "findings": audited_findings,
            "claims": claims,
            "citations": citation_verifier.dedupe_citations(citations),
            "unsupported_claims": clean_list(unsupported),
        }
    )
