import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.features.retrieval.sufficiency import assess_retrieval_sufficiency
from app.schemas.evidence import EvidenceRetrievalResultRead, RetrievalQueryPlanRead


def test_retrieval_sufficiency_requires_relevant_approved_evidence() -> None:
    plan = RetrievalQueryPlanRead(
        intent="customer_pain",
        subqueries=["coach pain"],
    )
    result = EvidenceRetrievalResultRead(
        source_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        title="Coach interview",
        url=None,
        source_type="note",
        chunk_index=0,
        text="Coach pain is caused by reviewing weekly client check-ins.",
        score=0.9,
        semantic_score=0.9,
        keyword_score=0.9,
        rerank_score=0.9,
        metadata={"source_trust": {"security_status": "approved"}},
        created_at=datetime.now(UTC),
    )

    sufficient = assess_retrieval_sufficiency([result], plan)
    insufficient = assess_retrieval_sufficiency([], plan)

    assert sufficient.sufficient is True
    assert sufficient.relevant_source_count == 1
    assert sufficient.trusted_source_ratio == 1
    assert insufficient.sufficient is False
    assert insufficient.reasons


def test_guide_abstains_when_evidence_retrieval_is_insufficient(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Evidence gap"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "What evidence supports this idea?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "do not have enough reliable project evidence" in body["answer"]
    assert "hypothesis" in body["answer"]
    assert body["confidence_level"] == "unknown"
    assert body["used_llm"] is False
    assert body["retrieval_diagnostics"]["sufficiency"]["sufficient"] is False
    assert body["unsupported_or_missing_evidence"]


def test_streamed_guide_abstains_when_evidence_retrieval_is_insufficient(
    client: TestClient,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Streamed evidence gap"}).json()["id"]

    with client.stream(
        "POST",
        f"/api/projects/{project_id}/guide/chat/stream",
        json={"message": "What evidence supports this idea?"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "do not have enough reliable project evidence" in body
    assert '"sufficient": false' in body
