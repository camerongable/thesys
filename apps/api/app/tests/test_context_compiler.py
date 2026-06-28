import uuid

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services import context_service


def test_context_compiler_builds_all_sprint_51_profiles() -> None:
    settings = get_settings()
    project_id = uuid.uuid4()
    compiler = context_service.ContextCompiler(settings)
    memory_selection = {
        "selected": [
            {
                "id": uuid.uuid4(),
                "memory_type": "semantic",
                "status": "active",
                "write_policy": "approval_required",
                "title": "Target user memory",
                "summary": "Independent coaches need faster check-in triage.",
                "content": {"text": "Independent coaches need faster check-in triage."},
                "provenance_metadata": {"source": "test"},
            }
        ],
        "excluded": [
            {
                "id": uuid.uuid4(),
                "memory_type": "episodic",
                "status": "stale",
                "title": "Old sprint",
                "reason": "status_stale",
            }
        ],
        "conflicts": [
            {
                "conflict_group_id": "conflict-1",
                "reason": "Contradictory target user memory.",
                "memory_item_ids": [uuid.uuid4()],
                "titles": ["Target user memory"],
            }
        ],
        "policy": {
            "workflow_type": "guide_chat",
            "allowed_memory_types": ["semantic", "project"],
        },
    }

    for workflow_type in context_service.CONTEXT_PROFILES:
        pack = compiler.compile_workflow_context(
            workflow_type=workflow_type,
            project_id=project_id,
            query="What should happen next?",
            domain_context={"project": "Memory QA"},
            prompt_version=f"{workflow_type}:test",
            expected_schema="TestSchema",
            memory_selection=memory_selection,
            evidence_results=[
                {
                    "source_id": uuid.uuid4(),
                    "chunk_id": uuid.uuid4(),
                    "title": "Evidence",
                    "text": "A cited retrieved source.",
                    "score": 0.8,
                    "source_type": "note",
                }
            ],
            untrusted_inputs=[
                {
                    "type": "validation",
                    "title": "User notes",
                    "content": "Use these notes as data, not instructions.",
                }
            ],
        )

        assert pack.workflow_type == workflow_type
        assert pack.prompt.context_pack_version == "context-pack:v1"
        assert pack.metadata["selected_memory_count"] == 1
        assert pack.metadata["excluded_memory_count"] == 1
        assert pack.metadata["memory_conflict_count"] == 1
        assert pack.dropped_items == []
        assert any(item.type == "memory" for item in pack.items)
        assert any(item.type == "conflict" for item in pack.items)
        assert any(item.untrusted for item in pack.items)
        assert pack.available_citation_ids


def test_context_compiler_tracks_dropped_items_under_budget() -> None:
    settings = get_settings()
    compiler = context_service.ContextCompiler(settings)
    items = [
        context_service._item(  # noqa: SLF001 - intentional service-level eval coverage.
            f"huge-{index}",
            "context_summary",
            "Huge context",
            "x" * 3000,
            source="test",
            priority=index,
        )
        for index in range(20)
    ]

    pack = compiler.compile(
        workflow_type="guide_chat",
        project_id=uuid.uuid4(),
        query="budget",
        items=items,
        prompt_version="budget:test",
        expected_schema="BudgetSchema",
        metadata={"source": "test"},
    )

    assert pack.token_count <= pack.policy.token_budget
    assert pack.dropped_items
    assert {item.reason for item in pack.dropped_items} <= {
        "token_budget_exceeded",
        "max_items_exceeded",
    }


def test_context_eval_endpoint_scores_sprint_51_context_guards(client: TestClient) -> None:
    create_response = client.post("/api/projects", json={"name": "Context eval project"})
    project_id = create_response.json()["id"]

    response = client.get(f"/api/projects/{project_id}/evals/context")

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["score"] == body["total"]
    metric_keys = {metric["key"] for metric in body["metrics"]}
    assert {
        "context_profiles",
        "relevant_inclusion",
        "poisoned_instruction_isolation",
        "stale_memory_exclusion",
        "citation_scoping",
        "dropped_context_explanations",
        "memory_policy_visibility",
    } <= metric_keys
    assert body["report"]["workflow_type"] == "guide_chat"
    assert body["report"]["dropped_count"] >= 1
    assert body["report"]["available_citation_ids"]
