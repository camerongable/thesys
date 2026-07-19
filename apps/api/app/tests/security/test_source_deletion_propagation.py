import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Artifact,
    ArtifactVersion,
    AuditEvent,
    Claim,
    ClaimEvidenceLink,
    Decision,
    DecisionLink,
    EvidenceChunk,
    EvidenceSource,
    EvidenceSourceTombstone,
    ProjectMemoryItem,
)


def test_source_deletion_removes_retrieval_and_invalidates_derivatives(
    client: TestClient,
    db_session: Session,
) -> None:
    project = client.post("/api/projects", json={"name": "Deletion propagation"}).json()
    project_id = project["id"]
    source_response = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={
            "title": "Evidence to delete",
            "text": (
                "Coaches pay for weekly check-in synthesis and need audit-ready recommendations."
            ),
        },
    )
    assert source_response.status_code == 201
    source_id = uuid.UUID(source_response.json()["id"])
    source = db_session.scalar(select(EvidenceSource).where(EvidenceSource.id == source_id))
    chunk = db_session.scalar(select(EvidenceChunk).where(EvidenceChunk.source_id == source_id))
    assert source is not None and chunk is not None

    artifact = Artifact(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        artifact_type="research_memo",
        title="Evidence-backed memo",
    )
    db_session.add(artifact)
    db_session.flush()
    version = ArtifactVersion(
        workspace_id=source.workspace_id,
        artifact_id=artifact.id,
        version=1,
        markdown_content="Memo",
        structured_content={},
    )
    db_session.add(version)
    db_session.flush()
    claim = Claim(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        artifact_version_id=version.id,
        text="Weekly synthesis has willingness-to-pay.",
        support_level="supported",
    )
    memory = ProjectMemoryItem(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        memory_type="semantic",
        status="active",
        write_policy="derived_read_only",
        source_entity_type="artifact_version",
        source_entity_id=version.id,
        title="Derived willingness-to-pay signal",
        summary="Derived from the evidence-backed memo.",
    )
    provenance_linked_memory = ProjectMemoryItem(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        memory_type="semantic",
        status="active",
        write_policy="derived_read_only",
        source_entity_type="research_sprint",
        source_entity_id=uuid.uuid4(),
        title="Source-linked recommendation",
        summary="A durable recommendation linked through secure source provenance.",
        provenance_metadata={"source_ids": [str(source.id)]},
    )
    db_session.add_all([claim, memory, provenance_linked_memory])
    db_session.flush()
    db_session.add(
        ClaimEvidenceLink(
            claim_id=claim.id,
            evidence_source_id=source.id,
            evidence_chunk_id=chunk.id,
        )
    )
    decision = Decision(
        workspace_id=source.workspace_id,
        project_id=source.project_id,
        decision_type="build",
        title="Build check-in synthesis",
        review_date=(datetime.now(UTC) + timedelta(days=14)).date(),
    )
    db_session.add(decision)
    db_session.flush()
    db_session.add(
        DecisionLink(
            decision_id=decision.id,
            linked_type="evidence",
            linked_id=source.id,
        )
    )
    db_session.commit()

    deleted = client.delete(f"/api/projects/{project_id}/evidence/{source_id}")

    assert deleted.status_code == 204
    db_session.expire_all()
    assert db_session.scalar(select(EvidenceSource).where(EvidenceSource.id == source_id)) is None
    assert (
        db_session.scalar(select(EvidenceChunk).where(EvidenceChunk.source_id == source_id)) is None
    )
    tombstone = db_session.scalar(
        select(EvidenceSourceTombstone).where(EvidenceSourceTombstone.source_id == source_id)
    )
    assert tombstone is not None
    assert tombstone.workspace_id == source.workspace_id
    assert tombstone.project_id == source.project_id
    assert tombstone.source_type == "note"
    assert tombstone.deletion_reason == "user_deleted"
    assert tombstone.deletion_metadata["deletion_impact"]["chunks_deleted"] == 1
    assert tombstone.deletion_metadata["source_trust_status"] == "approved"
    assert (
        db_session.scalar(select(ClaimEvidenceLink).where(ClaimEvidenceLink.claim_id == claim.id))
        is None
    )
    stored_claim = db_session.scalar(select(Claim).where(Claim.id == claim.id))
    stored_memory = db_session.scalar(
        select(ProjectMemoryItem).where(ProjectMemoryItem.id == memory.id)
    )
    stored_provenance_linked_memory = db_session.scalar(
        select(ProjectMemoryItem).where(ProjectMemoryItem.id == provenance_linked_memory.id)
    )
    stored_decision = db_session.scalar(select(Decision).where(Decision.id == decision.id))
    assert stored_claim is not None and stored_claim.support_level == "unsupported"
    assert stored_memory is not None and stored_memory.status == "stale"
    assert stored_provenance_linked_memory is not None
    assert stored_provenance_linked_memory.status == "stale"
    assert stored_provenance_linked_memory.provenance_metadata["requires_reverification"] is True
    assert stored_decision is not None
    assert stored_decision.review_date == datetime.now(UTC).date()
    assert db_session.scalar(
        select(DecisionLink).where(DecisionLink.decision_id == decision.id)
    ) is None

    retrieval = client.post(
        f"/api/projects/{project_id}/evidence/retrieve",
        json={"query": "weekly check-in synthesis", "mode": "hybrid", "top_k": 5},
    )
    assert retrieval.status_code == 200
    assert retrieval.json()["results"] == []

    event = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "evidence_source_deletion_propagated",
            AuditEvent.entity_id == source_id,
        )
    )
    assert event is not None
    assert event.event_metadata == {
        "chunks_deleted": 1,
        "claim_links_deleted": 1,
        "claims_invalidated": 1,
        "competitor_references_cleared": 0,
        "decision_links_deleted": 1,
        "decisions_requiring_review": 1,
        "memory_items_staled": 2,
        "object_deleted": False,
        "request_id": event.event_metadata["request_id"],
        "retrieval_revoked": True,
        "tombstone_id": str(tombstone.id),
    }
    assert str(uuid.UUID(event.event_metadata["request_id"])) == event.event_metadata["request_id"]
