import json
import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AICacheEntry, AICacheEvent
from app.services import ai_cache_service, identity_service


def test_embedding_cache_reuses_within_project_without_cross_project_reuse(
    client: TestClient,
    db_session: Session,
) -> None:
    note_text = (
        "Fitness coaches need faster weekly check-in synthesis from wearable data "
        "while preserving trust in the recommendation rationale."
    )
    first_project = client.post("/api/projects", json={"name": "Embedding cache A"}).json()["id"]
    second_project = client.post("/api/projects", json={"name": "Embedding cache B"}).json()["id"]

    assert _add_note(client, first_project, "First note", note_text).status_code == 201
    assert _add_note(client, first_project, "Second note", note_text).status_code == 201
    assert _add_note(client, second_project, "Other project note", note_text).status_code == 201

    embedding_events = list(
        db_session.scalars(
            select(AICacheEvent)
            .where(AICacheEvent.cache_type == "embedding")
            .order_by(AICacheEvent.created_at)
        )
    )
    event_types = [event.event_type for event in embedding_events]
    assert event_types.count("hit") >= 1
    assert event_types.count("miss") >= 2

    entries = list(
        db_session.scalars(select(AICacheEntry).where(AICacheEntry.cache_type == "embedding"))
    )
    assert {str(entry.project_id) for entry in entries} >= {first_project, second_project}
    assert all(
        "fitness coaches" not in json.dumps(entry.key_payload).casefold()
        for entry in entries
    )
    assert all("text_hash" in entry.key_payload for entry in entries)


def test_retrieval_cache_hits_and_stale_denies_after_evidence_change(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Retrieval cache"}).json()["id"]
    assert _add_note(
        client,
        project_id,
        "Initial evidence",
        (
            "Independent coaches lose time synthesizing weekly check-ins, wearable "
            "signals, and workout logs before each client call."
        ),
    ).status_code == 201

    payload = {
        "query": "weekly check-ins wearable signals coaching recommendations",
        "mode": "hybrid",
        "top_k": 5,
    }
    first = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)
    second = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["diagnostics"]["cache"]["status"] == "miss"
    assert second.json()["diagnostics"]["cache"]["status"] == "hit"

    assert _add_note(
        client,
        project_id,
        "New evidence",
        (
            "A paid pilot requires transparent rationale, CRM notes, and check-in "
            "summaries before coaches will trust automated recommendations."
        ),
    ).status_code == 201
    third = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)

    assert third.status_code == 200
    assert third.json()["diagnostics"]["cache"]["status"] == "stale_denial"
    assert "version changed" in third.json()["diagnostics"]["cache"]["reason"]
    retrieval_events = list(
        db_session.scalars(
            select(AICacheEvent)
            .where(AICacheEvent.cache_type == "retrieval_plan")
            .order_by(AICacheEvent.created_at)
        )
    )
    assert [event.event_type for event in retrieval_events].count("hit") == 1
    assert any(event.event_type == "stale_denial" for event in retrieval_events)

    entries = list(
        db_session.scalars(select(AICacheEntry).where(AICacheEntry.cache_type == "retrieval_plan"))
    )
    assert entries
    assert all(
        "weekly check-ins wearable" not in json.dumps(entry.key_payload).casefold()
        for entry in entries
    )
    assert all(entry.workspace_id != uuid.UUID(int=0) for entry in entries)


def test_retrieval_cache_stale_denies_after_memory_change(
    client: TestClient,
) -> None:
    project_id = _project_with_retrievable_note(client, "Memory invalidates retrieval cache")
    payload = _retrieval_payload()

    initial = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)
    assert initial.status_code == 200
    warm = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)
    assert warm.status_code == 200
    assert warm.json()["diagnostics"]["cache"]["status"] == "hit"

    memory = client.post(
        f"/api/projects/{project_id}/memory/preferences",
        json={
            "title": "Research preference",
            "summary": "Prefer paid-pilot evidence when judging coach willingness to pay.",
            "content": {"preference": "paid pilot evidence first"},
            "source": "test",
        },
    )
    assert memory.status_code == 200
    refreshed = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)

    assert refreshed.status_code == 200
    assert refreshed.json()["diagnostics"]["cache"]["status"] == "stale_denial"
    assert "memory_version" in refreshed.json()["diagnostics"]["cache"]["reason"]


def test_retrieval_cache_stale_denies_after_thesis_change(
    client: TestClient,
) -> None:
    project_id = _project_with_retrievable_note(client, "Thesis invalidates retrieval cache")
    payload = _retrieval_payload()

    initial = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)
    assert initial.status_code == 200
    warm = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)
    assert warm.status_code == 200
    assert warm.json()["diagnostics"]["cache"]["status"] == "hit"

    update = client.patch(
        f"/api/projects/{project_id}/thesis-canvas",
        json={
            "current_thesis": (
                "Independent coaches need at-risk client triage before weekly calls."
            ),
            "wedge": "At-risk client triage",
            "biggest_unknown": "Will coaches pay for automated triage?",
            "proof_needed": "Five coaches agree to a paid pilot.",
            "change_reason": "Narrowed the wedge after reviewing evidence.",
        },
    )
    assert update.status_code == 200
    refreshed = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)

    assert refreshed.status_code == 200
    assert refreshed.json()["diagnostics"]["cache"]["status"] == "stale_denial"
    assert "thesis_version" in refreshed.json()["diagnostics"]["cache"]["reason"]


def test_cache_stale_denies_after_prompt_or_schema_version_change(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AI_SEMANTIC_ANSWER_CACHE_ENABLED", "true")
    get_settings.cache_clear()
    auth = identity_service.ensure_dev_identity(
        db_session,
        email="cache-version@test.local",
        display_name="Cache Version Tester",
    )
    settings = get_settings()
    family = {
        "workspace_id": str(auth.workspace_id),
        "project_id": str(uuid.uuid4()),
        "cache_type": "guide_answer",
        "message_hash": "same-message",
    }
    old_versions = {
        "prompt_version": "guide-chat:v1",
        "expected_schema": "GroundedGuideAnswerDraft:v1",
    }
    new_versions = {
        "prompt_version": "guide-chat:v2",
        "expected_schema": "GroundedGuideAnswerDraft:v2",
    }
    ai_cache_service.store(
        db_session,
        auth,
        cache_type="guide_answer",
        key_payload={**family, "versions": old_versions},
        family_payload=family,
        version_payload=old_versions,
        value_payload={"response": {"answer": "cached"}},
        project_id=None,
    )

    lookup = ai_cache_service.lookup(
        db_session,
        auth,
        settings,
        cache_type="guide_answer",
        key_payload={**family, "versions": new_versions},
        family_payload=family,
        version_payload=new_versions,
        project_id=None,
    )

    assert lookup.value is None
    assert lookup.event is not None
    assert lookup.event.event_type == "stale_denial"
    assert "prompt_version" in (lookup.event.reason or "")
    assert "expected_schema" in (lookup.event.reason or "")


def test_cache_summary_reports_saved_tokens_cost_and_latency(
    client: TestClient,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Cache metric project"}).json()["id"]
    assert _add_note(
        client,
        project_id,
        "Cache metric evidence",
        "Coaches compare weekly check-in summaries, wearable trends, and rationale quality.",
    ).status_code == 201
    payload = {
        "query": "weekly check-in summaries wearable trends",
        "mode": "hybrid",
        "top_k": 3,
    }
    first = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)
    second = client.post(f"/api/projects/{project_id}/evidence/retrieve", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200

    response = client.get(f"/api/projects/{project_id}/evals/observability-metrics")

    assert response.status_code == 200
    metrics = {metric["name"]: metric["value"] for metric in response.json()["metrics"]}
    assert metrics["thesys.ai.cache.hits"] >= 1
    assert metrics["thesys.ai.cache.misses"] >= 1
    assert metrics["thesys.ai.cache.saved_tokens"] >= 1
    assert Decimal(str(metrics["thesys.ai.cache.saved_cost"])) >= Decimal("0")
    assert metrics["thesys.ai.cache.latency_saved"] >= 1


def _add_note(client: TestClient, project_id: str, title: str, text: str):
    return client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={"title": title, "text": text},
    )


def _project_with_retrievable_note(client: TestClient, name: str) -> str:
    project = client.post(
        "/api/projects",
        json={
            "name": name,
            "initial_thesis": "Coaches need faster weekly check-in synthesis.",
        },
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    assert _add_note(
        client,
        project_id,
        "Cache invalidation evidence",
        (
            "Independent coaches lose time synthesizing weekly check-ins, wearable "
            "signals, workout logs, and recommendation rationale before calls."
        ),
    ).status_code == 201
    return project_id


def _retrieval_payload() -> dict[str, object]:
    return {
        "query": "weekly check-ins wearable signals coaching recommendations",
        "mode": "hybrid",
        "top_k": 5,
    }
