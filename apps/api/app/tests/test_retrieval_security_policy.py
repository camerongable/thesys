import uuid
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import EvidenceChunk, EvidenceSource
from app.features.retrieval.security_policy import RetrievalSecurityPolicy
from app.schemas.evidence import EvidenceRetrieveCreate
from app.services import retrieval_service


def test_retrieval_policy_matches_sql_and_python_candidate_eligibility(
    db_session: Session,
) -> None:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    approved_source, approved_chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="internal",
        credibility_score="0.7",
    )
    restricted_source, restricted_chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="restricted",
        credibility_score="0.8",
    )
    low_trust_source, low_trust_chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="internal",
        credibility_score="0.2",
    )
    quarantined_source, quarantined_chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="internal",
        credibility_score="0.9",
        source_trust_status="quarantined",
    )
    db_session.add_all(
        [
            approved_source,
            approved_chunk,
            restricted_source,
            restricted_chunk,
            low_trust_source,
            low_trust_chunk,
            quarantined_source,
            quarantined_chunk,
        ]
    )
    db_session.commit()

    editor_policy = RetrievalSecurityPolicy.for_auth(
        _auth(workspace_id, "editor"),
        minimum_source_trust_score=0.5,
    )
    sql_chunk_ids = set(
        db_session.scalars(
            select(EvidenceChunk.id)
            .join(EvidenceSource, EvidenceSource.id == EvidenceChunk.source_id)
            .where(*editor_policy.sql_conditions(project_id))
        )
    )

    assert sql_chunk_ids == {approved_chunk.id}
    assert editor_policy.allows(source=approved_source, chunk=approved_chunk) is True
    assert editor_policy.allows(source=restricted_source, chunk=restricted_chunk) is False
    assert editor_policy.allows(source=low_trust_source, chunk=low_trust_chunk) is False
    assert editor_policy.allows(source=quarantined_source, chunk=quarantined_chunk) is False

    owner_policy = RetrievalSecurityPolicy.for_auth(
        _auth(workspace_id, "owner"),
        minimum_source_trust_score=0.5,
    )
    assert owner_policy.allows(source=restricted_source, chunk=restricted_chunk) is True


def test_python_fallback_uses_the_same_retrieval_security_policy(db_session: Session) -> None:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    approved_source, approved_chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="internal",
        credibility_score="0.7",
    )
    blocked_source, blocked_chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="internal",
        credibility_score="0.8",
        retrieval_allowed=False,
    )
    db_session.add_all([approved_source, approved_chunk, blocked_source, blocked_chunk])
    db_session.commit()

    candidates = retrieval_service._load_candidates(
        db_session,
        _auth(workspace_id, "editor"),
        get_settings(),
        project_id,
        EvidenceRetrieveCreate(query="approved evidence"),
    )

    assert [candidate.chunk.id for candidate in candidates] == [approved_chunk.id]


def test_cached_results_are_rechecked_after_source_quarantine(db_session: Session) -> None:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source, chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="internal",
        credibility_score="0.7",
    )
    db_session.add_all([source, chunk])
    db_session.commit()
    cached_result = retrieval_service._serialize_result(  # noqa: SLF001
        chunk,
        source,
        score=0.9,
        semantic_score=0.9,
        keyword_score=0.2,
    )

    source.source_metadata = {
        **source.source_metadata,
        "source_trust": {
            **source.source_metadata["source_trust"],
            "security_status": "quarantined",
        },
    }
    db_session.commit()

    results = retrieval_service._revalidate_cached_results(  # noqa: SLF001
        db_session,
        _auth(workspace_id, "editor"),
        get_settings(),
        project_id,
        EvidenceRetrieveCreate(query="approved evidence"),
        [cached_result],
    )

    assert results == []


def test_recent_evidence_reader_uses_the_shared_retrieval_policy(db_session: Session) -> None:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    approved_source, approved_chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="internal",
        credibility_score="0.7",
    )
    quarantined_source, quarantined_chunk = _source_and_chunk(
        workspace_id=workspace_id,
        project_id=project_id,
        data_classification="internal",
        credibility_score="0.9",
        source_trust_status="quarantined",
    )
    db_session.add_all([approved_source, approved_chunk, quarantined_source, quarantined_chunk])
    db_session.commit()

    results = retrieval_service.read_recent_evidence_results(
        db_session,
        _auth(workspace_id, "editor"),
        get_settings(),
        project_id,
        limit=8,
    )

    assert [result.chunk_id for result in results] == [approved_chunk.id]


def _auth(workspace_id: uuid.UUID, role: str) -> SimpleNamespace:
    return SimpleNamespace(workspace_id=workspace_id, role=role)


def _source_and_chunk(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    data_classification: str,
    credibility_score: str,
    retrieval_allowed: bool = True,
    source_trust_status: str = "approved",
) -> tuple[EvidenceSource, EvidenceChunk]:
    source_id = uuid.uuid4()
    source_security = {
        "security_status": "approved",
        "classification_status": "approved",
        "data_classification": data_classification,
    }
    source = EvidenceSource(
        id=source_id,
        workspace_id=workspace_id,
        project_id=project_id,
        source_type="note",
        source_metadata={
            "security": source_security,
            "source_trust": {
                "security_status": source_trust_status,
                "trust_score": float(credibility_score),
            },
        },
        ingestion_status="ready",
        credibility_score=Decimal(credibility_score),
    )
    chunk = EvidenceChunk(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source_id,
        chunk_index=0,
        text="approved evidence",
        chunk_metadata={
            "security": {
                "data_classification": data_classification,
                "retrieval_allowed": retrieval_allowed,
                "source_security_status": "approved",
            }
        },
    )
    return source, chunk
