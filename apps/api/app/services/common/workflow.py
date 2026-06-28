from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AIRun, AIStep
from app.services import ai_run_service


@dataclass(frozen=True)
class CompletedWorkflowStep:
    run: AIRun
    step: AIStep


def complete_zero_cost_step_and_run(
    db: Session,
    *,
    run: AIRun,
    step: AIStep,
    output_json: dict[str, Any],
    output_summary: str,
    latency_ms: int,
    model_provider: str,
    model_name: str,
    tokens: int | None = None,
) -> CompletedWorkflowStep:
    """Complete a deterministic/local workflow step and its owning run together."""
    completed_step = ai_run_service.complete_step(
        db,
        step,
        output_json=output_json,
        latency_ms=latency_ms,
        tokens=tokens,
        cost=Decimal("0"),
    )
    completed_run = ai_run_service.complete_run(
        db,
        run,
        output_summary=output_summary,
        total_tokens=tokens,
        total_cost=Decimal("0"),
        model_provider=model_provider,
        model_name=model_name,
    )
    return CompletedWorkflowStep(run=completed_run, step=completed_step)


def fail_step_and_run(
    db: Session,
    *,
    run: AIRun,
    step: AIStep,
    error: str,
    latency_ms: int | None = None,
) -> CompletedWorkflowStep:
    failed_step = ai_run_service.fail_step(db, step, error=error, latency_ms=latency_ms)
    failed_run = ai_run_service.fail_run(db, run, error=error)
    return CompletedWorkflowStep(run=failed_run, step=failed_step)
