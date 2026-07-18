import uuid
from datetime import UTC, datetime

from app.features.retrieval.security_ranking import apply_security_ranking
from app.schemas.evidence import EvidenceRetrievalResultRead


def test_security_ranking_drops_unsafe_results_and_penalizes_duplicate_sources() -> None:
    first_duplicate = _result(
        score=0.9,
        source_content_hash="same-content",
        source_trust={"security_status": "approved", "poisoning_score": 0.1},
    )
    second_duplicate = _result(
        score=0.88,
        source_content_hash="same-content",
        source_trust={"security_status": "approved", "poisoning_score": 0.1},
    )
    independent = _result(
        score=0.82,
        source_content_hash="independent-content",
        source_trust={"security_status": "approved", "poisoning_score": 0.0},
    )
    quarantined = _result(
        score=1.0,
        source_content_hash="unsafe-content",
        source_trust={"security_status": "quarantined", "poisoning_score": 1.0},
    )

    ranked = apply_security_ranking(
        [first_duplicate, second_duplicate, independent, quarantined]
    )

    assert [result.chunk_id for result in ranked] == [
        independent.chunk_id,
        first_duplicate.chunk_id,
        second_duplicate.chunk_id,
    ]
    assert all(result.chunk_id != quarantined.chunk_id for result in ranked)
    assert ranked[1].metadata["duplicate_source_count"] == 2
    assert ranked[1].metadata["duplicate_source_penalty"] == 0.12
    assert ranked[1].metadata["security_risk_penalty"] > 0


def _result(
    *,
    score: float,
    source_content_hash: str,
    source_trust: dict[str, object],
) -> EvidenceRetrievalResultRead:
    return EvidenceRetrievalResultRead(
        source_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        title="Evidence",
        url=None,
        source_type="note",
        chunk_index=0,
        text="Fitness coaches need evidence.",
        score=score,
        semantic_score=score,
        keyword_score=score,
        metadata={
            "source_content_hash": source_content_hash,
            "source_trust": source_trust,
        },
        created_at=datetime.now(UTC),
    )
