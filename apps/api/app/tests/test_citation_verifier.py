import uuid
from datetime import UTC, datetime

from app.schemas.artifacts import Citation, ClaimDraft
from app.schemas.evidence import EvidenceRetrievalResultRead
from app.services import citation_verifier_service


def test_citation_verifier_rejects_missing_ids_and_weak_overlap() -> None:
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    evidence = _result(
        source_id=source_id,
        chunk_id=chunk_id,
        text=(
            "Independent coaches spend hours reviewing weekly client check-ins "
            "before deciding who needs attention."
        ),
    )
    supported = ClaimDraft(
        text="Independent coaches spend hours reviewing weekly client check-ins.",
        support_level="supported",
        citations=[Citation(source_id=source_id, chunk_id=chunk_id, quote=evidence.text[:120])],
    )
    missing = ClaimDraft(
        text="Enterprise hospitals have approved annual budgets.",
        support_level="supported",
        citations=[Citation(source_id=uuid.uuid4(), chunk_id=uuid.uuid4())],
    )
    weak = ClaimDraft(
        text="Enterprise hospitals have approved annual budgets.",
        support_level="supported",
        citations=[Citation(source_id=source_id, chunk_id=chunk_id)],
    )

    supported_result, missing_result, weak_result = citation_verifier_service.verify_claims(
        [supported, missing, weak],
        [evidence],
    )

    assert supported_result.verified_citations
    assert missing_result.unsupported_reason == "supported_claim_has_no_verified_citation"
    assert missing_result.weak_citations[0].reason == "citation_id_not_retrieved"
    assert weak_result.unsupported_reason == "supported_claim_has_no_verified_citation"
    assert weak_result.weak_citations[0].reason == "weak_text_overlap"


def _result(
    *,
    source_id: uuid.UUID,
    chunk_id: uuid.UUID,
    text: str,
) -> EvidenceRetrievalResultRead:
    return EvidenceRetrievalResultRead(
        source_id=source_id,
        chunk_id=chunk_id,
        title="Evidence",
        url=None,
        source_type="note",
        chunk_index=0,
        text=text,
        score=0.8,
        semantic_score=0.7,
        keyword_score=0.8,
        metadata={},
        created_at=datetime.now(UTC),
    )
