"""AI workflow cost, latency, and circuit-breaker accounting."""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import AIRun, AIStep
from app.services import project_service


@dataclass(frozen=True)
class AICostReport:
    """Aggregated AI usage and budget status for one project."""

    run_count: int
    step_count: int
    failed_run_count: int
    total_tokens: int
    total_cost: Decimal
    average_step_latency_ms: int
    budget_status: str
    circuit_breaker_status: str
    workflow_breakdown: list[dict[str, Any]]


def project_ai_cost_report(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
) -> AICostReport:
    """Summarize persisted AI run/step usage against configured budgets."""
    project_service.get_project(db, auth, project_id)
    runs = list(
        db.scalars(
            select(AIRun).where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
            )
        )
    )
    run_ids = [run.id for run in runs]
    steps = list(db.scalars(select(AIStep).where(AIStep.ai_run_id.in_(run_ids)))) if run_ids else []
    total_tokens = sum(run.total_tokens or 0 for run in runs)
    total_cost = sum((run.total_cost or Decimal("0")) for run in runs)
    latencies = [step.latency_ms for step in steps if step.latency_ms is not None]
    failed_run_count = sum(1 for run in runs if run.status == "failed")
    return AICostReport(
        run_count=len(runs),
        step_count=len(steps),
        failed_run_count=failed_run_count,
        total_tokens=total_tokens,
        total_cost=total_cost,
        average_step_latency_ms=int(sum(latencies) / max(len(latencies), 1)),
        budget_status=_budget_status(settings, total_tokens, total_cost),
        circuit_breaker_status=_circuit_status(settings, failed_run_count),
        workflow_breakdown=_workflow_breakdown(runs),
    )


def _budget_status(settings: Settings, total_tokens: int, total_cost: Decimal) -> str:
    if total_tokens > settings.ai_workflow_max_tokens:
        return "token_budget_exceeded"
    if total_cost > Decimal(str(settings.ai_workflow_max_cost_usd)):
        return "cost_budget_exceeded"
    return "within_budget"


def _circuit_status(settings: Settings, failed_run_count: int) -> str:
    if failed_run_count >= settings.ai_provider_failure_circuit_threshold:
        return "provider_failure_threshold_reached"
    return "closed"


def _workflow_breakdown(runs: list[AIRun]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for run in runs:
        item = grouped.setdefault(
            run.workflow_type,
            {"workflow_type": run.workflow_type, "runs": 0, "tokens": 0, "cost": Decimal("0")},
        )
        item["runs"] += 1
        item["tokens"] += run.total_tokens or 0
        item["cost"] += run.total_cost or Decimal("0")
    return [
        {
            "workflow_type": item["workflow_type"],
            "runs": item["runs"],
            "tokens": item["tokens"],
            "cost": str(item["cost"]),
        }
        for item in sorted(grouped.values(), key=lambda value: value["workflow_type"])
    ]
