"""Durable runtime budget reservations for scoped AI workflows."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

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
    sprint, budget = _locked_sprint_and_budget(context)
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


def record_model_usage(
    *,
    total_tokens: int | None,
    total_cost: Decimal | None,
) -> None:
    context = _workflow_budget_context.get()
    if context is None or (total_tokens is None and total_cost is None):
        return
    incoming_tokens = _optional_nonnegative_usage_count(total_tokens)
    incoming_cost = _optional_nonnegative_usage_cost(total_cost)
    sprint, budget = _locked_sprint_and_budget(context)
    usage = dict(sprint.workflow_security_usage or {})
    observed_tokens = _nonnegative_usage_count(usage.get("tokens", 0))
    observed_cost = _nonnegative_usage_cost(usage.get("cost_usd", "0"))
    next_tokens = observed_tokens + (incoming_tokens or 0)
    next_cost = observed_cost + (incoming_cost or Decimal("0"))
    usage["tokens"] = next_tokens
    usage["cost_usd"] = str(next_cost)
    sprint.workflow_security_usage = usage

    if next_tokens > budget.max_tokens:
        _record_usage_budget_exceeded(
            context,
            sprint,
            budget_field="max_tokens",
            observed_field="observed_tokens",
            maximum=budget.max_tokens,
            observed=next_tokens,
            event_type="workflow_token_budget_exceeded",
            summary="Workflow token budget was exhausted after provider execution.",
        )
    if next_cost > budget.max_cost_usd:
        _record_usage_budget_exceeded(
            context,
            sprint,
            budget_field="max_cost_usd",
            observed_field="observed_cost_usd",
            maximum=str(budget.max_cost_usd),
            observed=str(next_cost),
            event_type="workflow_cost_budget_exceeded",
            summary="Workflow cost budget was exhausted after provider execution.",
        )
    context.db.commit()


def reserve_structured_output_repair() -> None:
    context = _workflow_budget_context.get()
    if context is None:
        return
    sprint, budget = _locked_sprint_and_budget(context)
    usage = dict(sprint.workflow_security_usage or {})
    observed_repairs = _nonnegative_usage_count(usage.get("structured_output_repairs", 0))
    if observed_repairs >= budget.max_structured_output_repairs:
        governance_service.record_audit_event(
            context.db,
            context.auth,
            event_type="workflow_structured_output_repair_budget_exceeded",
            actor_type="agent",
            project_id=context.project_id,
            entity_type="research_sprint",
            entity_id=context.research_sprint_id,
            risk_level="high",
            summary=(
                "Workflow structured-output repair budget was exhausted before provider execution."
            ),
            metadata={
                "max_structured_output_repairs": budget.max_structured_output_repairs,
                "observed_structured_output_repairs": observed_repairs,
                "temporal_workflow_id": sprint.temporal_workflow_id,
            },
        )
        context.db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
        )
    usage["structured_output_repairs"] = observed_repairs + 1
    sprint.workflow_security_usage = usage
    context.db.commit()


def _locked_sprint_and_budget(
    context: WorkflowBudgetContext,
) -> tuple[ResearchSprint, WorkflowSecurityBudget]:
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
    return sprint, WorkflowSecurityBudget.from_payload(sprint.workflow_security_budget)


def _record_usage_budget_exceeded(
    context: WorkflowBudgetContext,
    sprint: ResearchSprint,
    *,
    budget_field: str,
    observed_field: str,
    maximum: int | str,
    observed: int | str,
    event_type: str,
    summary: str,
) -> None:
    governance_service.record_audit_event(
        context.db,
        context.auth,
        event_type=event_type,
        actor_type="agent",
        project_id=context.project_id,
        entity_type="research_sprint",
        entity_id=context.research_sprint_id,
        risk_level="high",
        summary=summary,
        metadata={
            budget_field: maximum,
            observed_field: observed,
            "temporal_workflow_id": sprint.temporal_workflow_id,
        },
    )
    context.db.commit()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
    )


def _nonnegative_usage_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Workflow security usage is invalid.")
    return value


def _optional_nonnegative_usage_count(value: int | None) -> int | None:
    return None if value is None else _nonnegative_usage_count(value)


def _nonnegative_usage_cost(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("Workflow security usage is invalid.")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Workflow security usage is invalid.") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Workflow security usage is invalid.")
    return result


def _optional_nonnegative_usage_cost(value: Decimal | None) -> Decimal | None:
    return None if value is None else _nonnegative_usage_cost(value)
