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


@dataclass(frozen=True)
class ModelCallRateContext:
    db: Session
    auth: AuthContext
    settings: Settings
    project_id: uuid.UUID


_workflow_budget_context: ContextVar[WorkflowBudgetContext | None] = ContextVar(
    "workflow_budget_context",
    default=None,
)
_model_call_rate_context: ContextVar[ModelCallRateContext | None] = ContextVar(
    "model_call_rate_context",
    default=None,
)


@contextmanager
def model_call_rate_scope(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
) -> Iterator[None]:
    token = _model_call_rate_context.set(
        ModelCallRateContext(db=db, auth=auth, settings=settings, project_id=project_id)
    )
    try:
        yield
    finally:
        _model_call_rate_context.reset(token)


@contextmanager
def workflow_budget_scope(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID,
) -> Iterator[None]:
    rate_token = _model_call_rate_context.set(
        ModelCallRateContext(db=db, auth=auth, settings=settings, project_id=project_id)
    )
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
        _model_call_rate_context.reset(rate_token)


def reserve_model_call() -> None:
    rate_context = _model_call_rate_context.get()
    if rate_context is not None:
        from app.services import security_policy_service

        security_policy_service.enforce_model_call_rate_limit(
            rate_context.db,
            rate_context.auth,
            rate_context.settings,
            project_id=rate_context.project_id,
        )
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


def record_provider_failure(*, failure_kind: str, status_code: int | None = None) -> None:
    """Persist a bounded provider failure when a scoped workflow can be attributed."""
    context = _workflow_budget_context.get()
    if context is None:
        return
    sprint, _ = _locked_sprint_and_budget(context)
    from app.services import security_event_service

    attributes: dict[str, str | int] = {
        "provider": "litellm",
        "failure_kind": failure_kind,
    }
    if status_code is not None:
        attributes["status_code"] = status_code
    security_event_service.record_security_event(
        context.db,
        workspace_id=context.auth.workspace_id,
        project_id=context.project_id,
        user_id=context.auth.user_id,
        temporal_workflow_id=sprint.temporal_workflow_id,
        event_type="provider_failure",
        severity="medium",
        source="workflow",
        summary="A model provider request failed before a usable response was returned.",
        attributes=attributes,
        settings=context.settings,
    )
    context.db.commit()


def record_provider_prompt_pii(
    *,
    pii_entity_types: tuple[str, ...],
    redacted_message_count: int,
) -> None:
    """Record provider-bound prompt redaction for an attributed workflow only."""
    context = _workflow_budget_context.get()
    if context is None or redacted_message_count < 1:
        return
    sprint, _ = _locked_sprint_and_budget(context)
    from app.services import security_event_service

    entity_types = sorted(
        {
            entity_type[:80]
            for entity_type in pii_entity_types
            if isinstance(entity_type, str) and entity_type
        }
    )[:20]
    if not entity_types:
        return
    security_event_service.record_security_event(
        context.db,
        workspace_id=context.auth.workspace_id,
        project_id=context.project_id,
        user_id=context.auth.user_id,
        temporal_workflow_id=sprint.temporal_workflow_id,
        event_type="pii_redaction_in_provider_prompt",
        severity="medium",
        source="workflow",
        summary="Redacted sensitive entities before a model provider request.",
        attributes={
            "provider": "litellm",
            "pii_entity_types": entity_types,
            "redacted_message_count": min(redacted_message_count, 100),
        },
        settings=context.settings,
    )
    context.db.commit()


def record_model_output_secret(*, secret_entity_types: tuple[str, ...]) -> None:
    """Record a model-output secret only when a workflow can be attributed."""
    context = _workflow_budget_context.get()
    if context is None:
        return
    entity_types = sorted(
        {
            entity_type[:80]
            for entity_type in secret_entity_types
            if isinstance(entity_type, str) and entity_type
        }
    )[:20]
    if not entity_types:
        return
    sprint, _ = _locked_sprint_and_budget(context)
    from app.services import security_event_service

    security_event_service.record_security_event(
        context.db,
        workspace_id=context.auth.workspace_id,
        project_id=context.project_id,
        user_id=context.auth.user_id,
        temporal_workflow_id=sprint.temporal_workflow_id,
        event_type="secret_detected_in_model_output",
        severity="high",
        source="workflow",
        summary="A secret was redacted from a model provider response.",
        attributes={
            "provider": "litellm",
            "detected_entity_types": entity_types,
        },
        settings=context.settings,
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


def reserve_critique_loop() -> None:
    context = _workflow_budget_context.get()
    if context is None:
        return
    sprint, budget = _locked_sprint_and_budget(context)
    usage = dict(sprint.workflow_security_usage or {})
    observed_loops = _nonnegative_usage_count(usage.get("critique_loops", 0))
    if observed_loops >= budget.max_critique_loops:
        governance_service.record_audit_event(
            context.db,
            context.auth,
            event_type="workflow_critique_loop_budget_exceeded",
            actor_type="agent",
            project_id=context.project_id,
            entity_type="research_sprint",
            entity_id=context.research_sprint_id,
            risk_level="high",
            summary="Workflow critique-loop budget was exhausted before critique execution.",
            metadata={
                "max_critique_loops": budget.max_critique_loops,
                "observed_critique_loops": observed_loops,
                "temporal_workflow_id": sprint.temporal_workflow_id,
            },
        )
        context.db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
        )
    usage["critique_loops"] = observed_loops + 1
    sprint.workflow_security_usage = usage
    context.db.commit()


def enforce_repeated_source_fetch_failure_limit(
    *,
    source_id: uuid.UUID,
    observed_failed_fetches: int,
) -> None:
    context = _workflow_budget_context.get()
    if context is None:
        return
    observed_failed_fetches = _nonnegative_usage_count(observed_failed_fetches)
    sprint, budget = _locked_sprint_and_budget(context)
    if observed_failed_fetches < budget.max_failed_source_fetches:
        return
    governance_service.record_audit_event(
        context.db,
        context.auth,
        event_type="workflow_repeated_source_fetch_failure_detected",
        actor_type="agent",
        project_id=context.project_id,
        entity_type="discovered_source",
        entity_id=source_id,
        risk_level="high",
        summary="Workflow stopped before retrying a repeatedly failed source fetch.",
        metadata={
            "max_failed_source_fetches": budget.max_failed_source_fetches,
            "observed_failed_fetches": observed_failed_fetches,
            "temporal_workflow_id": sprint.temporal_workflow_id,
        },
    )
    context.db.commit()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
    )


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
