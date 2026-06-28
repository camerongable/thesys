"""FastAPI-facing controls for durable Temporal research sprint workflows."""

import asyncio
import uuid
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
from app.db.models import ResearchSprint
from app.services import governance_service, project_service
from app.temporal.workflows import ResearchSprintWorkflow


class TemporalResearchWorkflowError(RuntimeError):
    pass


def start_research_sprint_workflow(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> ResearchSprint:
    """Start a Temporal workflow for a research sprint when Temporal is enabled."""
    require_permission(auth, "run_research")
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if not settings.temporal_enabled:
        return sprint
    if sprint.status in {"completed", "cancelled", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed, cancelled, or rejected research sprints cannot be started.",
        )
    if sprint.temporal_workflow_id and sprint.status != "failed":
        return sprint

    workflow_id = sprint.temporal_workflow_id or _workflow_id(sprint.id)
    sprint.temporal_workflow_id = workflow_id
    sprint.current_step = "start_temporal_workflow"
    sprint.failure_message = None
    sprint.failed_step = None
    if sprint.plan.status == "draft":
        sprint.status = "waiting_for_approval"
    db.commit()

    try:
        run_id = _run_async(_start_temporal_workflow(settings, _workflow_payload(auth, sprint)))
    except Exception as exc:
        sprint = _get_sprint(db, auth, project_id, sprint_id)
        sprint.status = "failed"
        sprint.current_step = "start_temporal_workflow"
        sprint.failed_step = "start_temporal_workflow"
        sprint.failure_message = str(exc)[:2000]
        db.commit()
        raise TemporalResearchWorkflowError("Temporal workflow start failed.") from exc

    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if run_id:
        sprint.temporal_run_id = run_id
    sprint.current_step = (
        "wait_for_research_plan_approval" if sprint.plan.status == "draft" else "discover_sources"
    )
    if sprint.plan.status == "draft":
        sprint.status = "waiting_for_approval"
    db.commit()
    db.refresh(sprint)

    if sprint.plan.status == "approved":
        signal_research_plan_approved(db, auth, settings, project_id, sprint.id)
    return _get_sprint(db, auth, project_id, sprint_id)


def retry_research_sprint_workflow(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> ResearchSprint:
    """Create a new workflow id and restart a failed/cancelled durable sprint."""
    require_permission(auth, "run_research")
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if sprint.status not in {"failed", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed or cancelled durable research sprints can be retried.",
        )
    sprint.temporal_workflow_id = f"{_workflow_id(sprint.id)}-retry-{uuid.uuid4().hex[:8]}"
    sprint.temporal_run_id = None
    sprint.status = "waiting_for_approval" if sprint.plan.status == "draft" else "approved"
    sprint.current_step = "retry_temporal_workflow"
    sprint.failed_step = None
    sprint.failure_message = None
    sprint.completed_at = None
    db.commit()
    return start_research_sprint_workflow(db, auth, settings, project_id, sprint_id)


def cancel_research_sprint_workflow(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> ResearchSprint:
    """Cancel the durable workflow and mirror cancellation into local sprint state."""
    require_permission(auth, "run_research")
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if not sprint.temporal_workflow_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research sprint has no Temporal workflow to cancel.",
        )
    if settings.temporal_enabled:
        try:
            _run_async(_cancel_temporal_workflow(settings, sprint.temporal_workflow_id))
        except Exception as exc:
            raise TemporalResearchWorkflowError("Temporal workflow cancellation failed.") from exc
    sprint.status = "cancelled"
    sprint.current_step = "cancelled"
    db.commit()
    return _get_sprint(db, auth, project_id, sprint_id)


def signal_research_plan_approved(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> None:
    _signal_if_running(db, auth, settings, project_id, sprint_id, "approve_research_plan")


def signal_memory_updates_approved(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> None:
    _signal_if_running(db, auth, settings, project_id, sprint_id, "approve_memory_updates")


def signal_memory_updates_rejected(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> None:
    _signal_if_running(db, auth, settings, project_id, sprint_id, "reject_memory_updates")


def signal_research_sprint_cancelled(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> None:
    _signal_if_running(db, auth, settings, project_id, sprint_id, "cancel_research_sprint")


def execution_payload(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> dict[str, Any]:
    """Return local and Temporal execution state for workflow inspect panels."""
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    return {
        "sprint": sprint,
        "temporal_enabled": settings.temporal_enabled,
        "temporal_workflow_id": sprint.temporal_workflow_id,
        "temporal_run_id": sprint.temporal_run_id,
        "status": sprint.status,
        "current_step": sprint.current_step,
        "failed_step": sprint.failed_step,
        "failure_message": sprint.failure_message,
        "action_required": _action_required(sprint),
    }


def _signal_if_running(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    signal_name: str,
) -> None:
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if not settings.temporal_enabled or not sprint.temporal_workflow_id:
        return
    try:
        _run_async(_signal_temporal_workflow(settings, sprint.temporal_workflow_id, signal_name))
    except Exception as exc:
        governance_service.record_audit_event(
            db,
            auth,
            event_type="temporal_signal_failed",
            actor_type="system",
            project_id=project_id,
            entity_type="research_sprint",
            entity_id=sprint.id,
            risk_level="medium",
            summary=f"Failed to signal Temporal workflow: {signal_name}.",
            metadata={
                "temporal_workflow_id": sprint.temporal_workflow_id,
                "signal_name": signal_name,
                "error": str(exc)[:1000],
            },
        )
        db.commit()
        raise TemporalResearchWorkflowError("Temporal workflow signal failed.") from exc


def _get_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> ResearchSprint:
    project_service.get_project(db, auth, project_id)
    sprint = db.scalar(
        select(ResearchSprint)
        .where(
            ResearchSprint.id == sprint_id,
            ResearchSprint.workspace_id == auth.workspace_id,
            ResearchSprint.project_id == project_id,
        )
        .options(selectinload(ResearchSprint.plan))
    )
    if sprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research sprint not found.",
        )
    return sprint


def _workflow_id(sprint_id: uuid.UUID) -> str:
    return f"research-sprint-{sprint_id}"


def _workflow_payload(auth: AuthContext, sprint: ResearchSprint) -> dict[str, str]:
    return {
        "workspace_id": str(auth.workspace_id),
        "project_id": str(sprint.project_id),
        "research_sprint_id": str(sprint.id),
        "research_plan_id": str(sprint.research_plan_id),
        "user_id": str(auth.user_id),
        "temporal_workflow_id": sprint.temporal_workflow_id or _workflow_id(sprint.id),
    }


async def _start_temporal_workflow(settings: Settings, payload: dict[str, str]) -> str | None:
    client = await _temporal_client(settings)
    workflow_id = payload.get("temporal_workflow_id") or _workflow_id(
        uuid.UUID(payload["research_sprint_id"])
    )
    try:
        handle = await client.start_workflow(
            ResearchSprintWorkflow.run,
            payload,
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
            execution_timeout=timedelta(seconds=settings.temporal_workflow_timeout_seconds),
        )
    except WorkflowAlreadyStartedError:
        handle = client.get_workflow_handle(workflow_id)
    return (
        getattr(handle, "first_execution_run_id", None)
        or getattr(handle, "result_run_id", None)
        or getattr(handle, "run_id", None)
    )


async def _signal_temporal_workflow(
    settings: Settings,
    workflow_id: str,
    signal_name: str,
) -> None:
    client = await _temporal_client(settings)
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(signal_name)


async def _cancel_temporal_workflow(settings: Settings, workflow_id: str) -> None:
    client = await _temporal_client(settings)
    handle = client.get_workflow_handle(workflow_id)
    await handle.cancel()


async def _temporal_client(settings: Settings) -> Client:
    return await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Temporal client calls must run outside an active event loop.")


def _action_required(sprint: ResearchSprint) -> str | None:
    if sprint.status == "waiting_for_approval":
        return "Approve research plan"
    if sprint.status == "waiting_for_memory_approval":
        return "Approve memory updates"
    if sprint.status == "failed":
        return "Retry or cancel workflow"
    return None
