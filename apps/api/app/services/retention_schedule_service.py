"""Worker-owned Temporal schedule for tenant-scoped retention cleanup."""

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
from app.temporal.workflows import RetentionCleanupWorkflow

RETENTION_CLEANUP_SCHEDULE_ID = "retention-cleanup-v1"


def retention_cleanup_schedule(settings: Settings) -> Schedule:
    """Build the idempotent schedule definition used by the Temporal worker."""
    return Schedule(
        action=ScheduleActionStartWorkflow(
            RetentionCleanupWorkflow.run,
            id=RETENTION_CLEANUP_SCHEDULE_ID,
            task_queue=settings.temporal_task_queue,
            execution_timeout=timedelta(seconds=settings.temporal_workflow_timeout_seconds),
        ),
        spec=ScheduleSpec(
            intervals=[
                ScheduleIntervalSpec(
                    every=timedelta(hours=settings.retention_cleanup_interval_hours)
                )
            ]
        ),
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
    )


async def ensure_retention_cleanup_schedule(client: Client, settings: Settings) -> None:
    """Create or reconcile the global schedule before the worker accepts work."""
    if not settings.retention_cleanup_schedule_enabled:
        return
    schedule = retention_cleanup_schedule(settings)
    try:
        await client.create_schedule(RETENTION_CLEANUP_SCHEDULE_ID, schedule)
    except ScheduleAlreadyRunningError:
        handle = client.get_schedule_handle(RETENTION_CLEANUP_SCHEDULE_ID)
        await handle.update(lambda _input: ScheduleUpdate(schedule=schedule))
