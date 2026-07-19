import pytest

from app.core.config import Settings
from app.security.workflow_budget import WorkflowSecurityBudget


def test_workflow_security_budget_snapshots_all_required_dimensions() -> None:
    budget = WorkflowSecurityBudget.from_settings(
        Settings(
            ai_workflow_max_tokens=12_345,
            ai_workflow_max_cost_usd=2.5,
            security_workflow_max_model_calls=8,
            security_workflow_max_tool_calls=9,
            security_workflow_max_external_queries=10,
            security_workflow_max_retrieved_chunks=11,
            security_workflow_max_duration_seconds=120,
            security_workflow_max_memory_proposals=12,
            security_workflow_max_structured_output_repairs=2,
            security_workflow_max_critique_loops=3,
            security_workflow_max_identical_tool_invocations=4,
            security_workflow_max_alternating_tool_cycles=5,
            security_workflow_max_repeated_retrieval_queries=6,
            security_workflow_max_consecutive_empty_retrievals=7,
            security_workflow_max_failed_source_fetches=8,
            security_workflow_max_rejected_memory_proposals=9,
        )
    )

    assert budget.as_payload() == {
        "max_model_calls": 8,
        "max_tool_calls": 9,
        "max_external_queries": 10,
        "max_retrieved_chunks": 11,
        "max_tokens": 12_345,
        "max_cost_usd": 2.5,
        "max_duration_seconds": 120,
        "max_memory_proposals": 12,
        "max_structured_output_repairs": 2,
        "max_critique_loops": 3,
        "max_identical_tool_invocations": 4,
        "max_alternating_tool_cycles": 5,
        "max_repeated_retrieval_queries": 6,
        "max_consecutive_empty_retrievals": 7,
        "max_failed_source_fetches": 8,
        "max_rejected_memory_proposals": 9,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"max_model_calls": 0},
        {
            "max_model_calls": 1,
            "max_tool_calls": 1,
            "max_external_queries": 1,
            "max_retrieved_chunks": 1,
            "max_tokens": 1,
            "max_cost_usd": -1,
            "max_duration_seconds": 1,
            "max_memory_proposals": 1,
            "max_structured_output_repairs": 0,
            "max_critique_loops": 0,
            "max_identical_tool_invocations": 1,
            "max_alternating_tool_cycles": 1,
            "max_repeated_retrieval_queries": 1,
            "max_consecutive_empty_retrievals": 1,
            "max_failed_source_fetches": 1,
            "max_rejected_memory_proposals": 1,
        },
        {
            "max_model_calls": True,
            "max_tool_calls": 1,
            "max_external_queries": 1,
            "max_retrieved_chunks": 1,
            "max_tokens": 1,
            "max_cost_usd": 1,
            "max_duration_seconds": 1,
            "max_memory_proposals": 1,
            "max_structured_output_repairs": 0,
            "max_critique_loops": 0,
            "max_identical_tool_invocations": 1,
            "max_alternating_tool_cycles": 1,
            "max_repeated_retrieval_queries": 1,
            "max_consecutive_empty_retrievals": 1,
            "max_failed_source_fetches": 1,
            "max_rejected_memory_proposals": 1,
        },
    ],
)
def test_workflow_security_budget_rejects_incomplete_or_invalid_payload(payload) -> None:
    with pytest.raises(ValueError, match="Workflow security budget is invalid"):
        WorkflowSecurityBudget.from_payload(payload)
