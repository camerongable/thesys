"""Worker-owned Temporal schedule for durable workflow timeout reconciliation."""

from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleUpdate,
)

from app.core.config import Settings
from app.temporal.workflows import WorkflowTimeoutReconciliationWorkflow

WORKFLOW_TIMEOUT_RECONCILIATION_SCHEDULE_ID = "workflow-timeout-reconciliation-v1"


def workflow_timeout_reconciliation_schedule(settings: Settings) -> Schedule:
    """Build the idempotent timeout-reconciliation schedule definition."""
    return Schedule(
        action=ScheduleActionStartWorkflow(
            WorkflowTimeoutReconciliationWorkflow.run,
            id=WORKFLOW_TIMEOUT_RECONCILIATION_SCHEDULE_ID,
            task_queue=settings.temporal_task_queue,
            execution_timeout=timedelta(seconds=settings.temporal_workflow_timeout_seconds),
        ),
        spec=ScheduleSpec(
            intervals=[
                ScheduleIntervalSpec(
                    every=timedelta(
                        minutes=settings.workflow_timeout_reconciliation_interval_minutes
                    )
                )
            ]
        ),
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
    )


async def ensure_workflow_timeout_reconciliation_schedule(
    client: Client,
    settings: Settings,
) -> None:
    """Create or reconcile the global schedule before the worker accepts work."""
    if not settings.workflow_timeout_reconciliation_schedule_enabled:
        return
    schedule = workflow_timeout_reconciliation_schedule(settings)
    try:
        await client.create_schedule(WORKFLOW_TIMEOUT_RECONCILIATION_SCHEDULE_ID, schedule)
    except ScheduleAlreadyRunningError:
        handle = client.get_schedule_handle(WORKFLOW_TIMEOUT_RECONCILIATION_SCHEDULE_ID)
        await handle.update(lambda _input: ScheduleUpdate(schedule=schedule))
