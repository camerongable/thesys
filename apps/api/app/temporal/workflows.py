from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

DEFAULT_ACTIVITY_TIMEOUT = timedelta(minutes=5)
LLM_ACTIVITY_TIMEOUT = timedelta(minutes=20)


@workflow.defn
class ResearchSprintWorkflow:
    """Durable orchestration for the V1 research sprint business workflow."""

    def __init__(self) -> None:
        self._plan_approved = False
        self._memory_approved = False
        self._memory_rejected = False
        self._cancel_requested = False

    @workflow.signal
    async def approve_research_plan(self) -> None:
        self._plan_approved = True

    @workflow.signal
    async def approve_memory_updates(self) -> None:
        self._memory_approved = True

    @workflow.signal
    async def reject_memory_updates(self) -> None:
        self._memory_rejected = True

    @workflow.signal
    async def cancel_research_sprint(self) -> None:
        self._cancel_requested = True

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        await _activity("create_or_load_research_plan_activity", payload)
        await _activity(
            "create_approval_request_activity",
            {**payload, "approval_type": "research_plan"},
        )

        await workflow.wait_condition(lambda: self._plan_approved or self._cancel_requested)
        if self._cancel_requested:
            return await _activity("finalize_sprint_activity", {**payload, "status": "cancelled"})

        await _activity("discover_sources_activity", payload)
        await _activity("discover_competitors_activity", payload)
        await _activity("wait_for_optional_source_competitor_review_activity", payload)
        await _activity("ingest_sources_activity", payload)
        await _activity("embed_evidence_activity", payload)
        await _activity("run_langgraph_research_activity", payload, timeout=LLM_ACTIVITY_TIMEOUT)
        await _activity("run_langsmith_eval_activity", payload)
        await _activity("create_memory_update_proposals_activity", payload)
        await _activity(
            "create_approval_request_activity",
            {**payload, "approval_type": "memory_update"},
        )

        await workflow.wait_condition(
            lambda: self._memory_approved or self._memory_rejected or self._cancel_requested
        )
        if self._cancel_requested:
            return await _activity("finalize_sprint_activity", {**payload, "status": "cancelled"})

        if self._memory_approved:
            await _activity("persist_memory_update_activity", {**payload, "decision": "approved"})
        else:
            await _activity("persist_memory_update_activity", {**payload, "decision": "rejected"})

        return await _activity("finalize_sprint_activity", {**payload, "status": "completed"})


async def _activity(
    name: str,
    payload: dict[str, Any],
    *,
    timeout: timedelta = DEFAULT_ACTIVITY_TIMEOUT,
) -> dict[str, Any]:
    return await workflow.execute_activity(
        name,
        payload,
        start_to_close_timeout=timeout,
        retry_policy=RetryPolicy(
            initial_interval=timedelta(seconds=2),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        ),
    )
