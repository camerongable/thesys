import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Artifact,
    ArtifactVersion,
    AuditEvent,
    Claim,
    ClaimEvidenceLink,
    EvidenceChunk,
    EvidenceSource,
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
    db_session.add_all([claim, memory])
    db_session.flush()
    db_session.add(
        ClaimEvidenceLink(
            claim_id=claim.id,
            evidence_source_id=source.id,
            evidence_chunk_id=chunk.id,
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
    assert (
        db_session.scalar(select(ClaimEvidenceLink).where(ClaimEvidenceLink.claim_id == claim.id))
        is None
    )
    stored_claim = db_session.scalar(select(Claim).where(Claim.id == claim.id))
    stored_memory = db_session.scalar(
        select(ProjectMemoryItem).where(ProjectMemoryItem.id == memory.id)
    )
    assert stored_claim is not None and stored_claim.support_level == "unsupported"
    assert stored_memory is not None and stored_memory.status == "stale"

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
        "memory_items_staled": 1,
        "object_deleted": False,
        "retrieval_revoked": True,
    }
