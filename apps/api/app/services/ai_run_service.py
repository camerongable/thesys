import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.redaction import redact_payload, redact_text
from app.db.models import AIRun, AIStep


def start_run(
    db: Session,
    auth: AuthContext,
    *,
    workflow_type: str,
    prompt_version: str,
    input_summary: str,
    project_id: uuid.UUID | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
) -> AIRun:
    run = AIRun(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        workflow_type=workflow_type,
        status="running",
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=prompt_version,
        input_summary=redact_text(input_summary, redact_emails=True),
        started_at=datetime.now(UTC),
        created_by=auth.user_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def start_step(
    db: Session,
    run: AIRun,
    *,
    step_name: str,
    input_json: dict[str, Any] | None = None,
) -> AIStep:
    step = AIStep(
        ai_run_id=run.id,
        step_name=step_name,
        status="running",
        input_json=redact_payload(input_json or {}, redact_emails=True),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def complete_step(
    db: Session,
    step: AIStep,
    *,
    output_json: dict[str, Any],
    latency_ms: int,
    tokens: int | None,
    cost: Decimal | None,
) -> AIStep:
    step.status = "succeeded"
    step.output_json = redact_payload(output_json, redact_emails=True)
    step.latency_ms = latency_ms
    step.tokens = tokens
    step.cost = cost
    step.error = None
    db.commit()
    db.refresh(step)
    return step


def fail_step(db: Session, step: AIStep, *, error: str, latency_ms: int | None = None) -> AIStep:
    step.status = "failed"
    step.error = redact_text(error, redact_emails=True)
    step.latency_ms = latency_ms
    db.commit()
    db.refresh(step)
    return step


def complete_run(
    db: Session,
    run: AIRun,
    *,
    output_summary: str,
    total_tokens: int | None,
    total_cost: Decimal | None,
    model_provider: str,
    model_name: str,
) -> AIRun:
    run.status = "succeeded"
    run.output_summary = redact_text(output_summary, redact_emails=True)
    run.total_tokens = total_tokens
    run.total_cost = total_cost
    run.model_provider = model_provider
    run.model_name = model_name
    run.error = None
    run.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)
    return run


def wait_for_human(
    db: Session,
    run: AIRun,
    *,
    output_summary: str,
    total_tokens: int | None,
    total_cost: Decimal | None,
    model_provider: str,
    model_name: str,
) -> AIRun:
    run.status = "waiting_for_human"
    run.output_summary = redact_text(output_summary, redact_emails=True)
    run.total_tokens = total_tokens
    run.total_cost = total_cost
    run.model_provider = model_provider
    run.model_name = model_name
    run.error = None
    db.commit()
    db.refresh(run)
    return run


def cancel_run(db: Session, run: AIRun, *, output_summary: str) -> AIRun:
    run.status = "cancelled"
    run.output_summary = redact_text(output_summary, redact_emails=True)
    run.error = None
    run.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)
    return run


def fail_run(db: Session, run: AIRun, *, error: str) -> AIRun:
    run.status = "failed"
    run.error = redact_text(error, redact_emails=True)
    run.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)
    return run
