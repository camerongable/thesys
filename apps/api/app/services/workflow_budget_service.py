"""Durable runtime budget reservations for scoped AI workflows."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import ResearchSprint
from app.security.workflow_budget import WORKFLOW_BUDGET_EXHAUSTED_DETAIL, WorkflowSecurityBudget
from app.services import governance_service


@dataclass(frozen=True)
class WorkflowBudgetContext:
    db: Session
    auth: AuthContext
    settings: Settings
    project_id: uuid.UUID
    research_sprint_id: uuid.UUID


_workflow_budget_context: ContextVar[WorkflowBudgetContext | None] = ContextVar(
    "workflow_budget_context",
    default=None,
)


@contextmanager
def workflow_budget_scope(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID,
) -> Iterator[None]:
    token = _workflow_budget_context.set(
        WorkflowBudgetContext(
            db=db,
            auth=auth,
            settings=settings,
            project_id=project_id,
            research_sprint_id=research_sprint_id,
        )
    )
    try:
        yield
    finally:
        _workflow_budget_context.reset(token)


def reserve_model_call() -> None:
    context = _workflow_budget_context.get()
    if context is None:
        return
    sprint = context.db.scalar(
        select(ResearchSprint)
        .where(
            ResearchSprint.id == context.research_sprint_id,
            ResearchSprint.workspace_id == context.auth.workspace_id,
            ResearchSprint.project_id == context.project_id,
        )
        .with_for_update()
    )
    if sprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research sprint not found.",
        )
    if not sprint.workflow_security_budget:
        sprint.workflow_security_budget = WorkflowSecurityBudget.from_settings(
            context.settings
        ).as_payload()
        context.db.flush()
    budget = WorkflowSecurityBudget.from_payload(sprint.workflow_security_budget)
    usage = dict(sprint.workflow_security_usage or {})
    observed_model_calls = _nonnegative_usage_count(usage.get("model_calls", 0))
    if observed_model_calls >= budget.max_model_calls:
        governance_service.record_audit_event(
            context.db,
            context.auth,
            event_type="workflow_model_call_budget_exceeded",
            actor_type="agent",
            project_id=context.project_id,
            entity_type="research_sprint",
            entity_id=context.research_sprint_id,
            risk_level="high",
            summary="Workflow model-call budget was exhausted before provider execution.",
            metadata={
                "max_model_calls": budget.max_model_calls,
                "observed_model_calls": observed_model_calls,
                "temporal_workflow_id": sprint.temporal_workflow_id,
            },
        )
        context.db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
        )
    usage["model_calls"] = observed_model_calls + 1
    sprint.workflow_security_usage = usage
    context.db.commit()


def _nonnegative_usage_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Workflow security usage is invalid.")
    return value
