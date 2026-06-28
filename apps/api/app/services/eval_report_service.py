"""File-backed eval reports, trend summaries, and local observability metrics."""

import json
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import AIRun, AIStep, ApprovalRequest, AuditEvent
from app.services import ai_cache_service, project_service

REPO_ROOT = Path(__file__).resolve().parents[4]
REPORT_DIR_ENV = "THESYS_EVAL_REPORT_DIR"
DEFAULT_REPORT_DIR = REPO_ROOT / "reports" / "evals"


def read_latest_report() -> dict[str, Any]:
    """Return the most recent local eval report if the quality gate has run."""

    path = _report_dir() / "latest.json"
    if not path.exists():
        return {
            "available": False,
            "status": "unavailable",
            "message": "No local eval report found. Run `python3 scripts/eval_quality_gate.py`.",
        }
    return _read_json(path)


def read_eval_trends(limit: int = 20) -> list[dict[str, Any]]:
    """Read recent file-backed eval trend records."""

    path = _report_dir() / "eval_runs.jsonl"
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append({"status": "warning", "message": "Skipped malformed trend record."})
    return records[-max(1, min(limit, 100)) :]


def project_observability_metrics(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
) -> dict[str, Any]:
    """Return OpenTelemetry-compatible metric points for hidden Inspect surfaces."""

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
    steps = (
        list(db.scalars(select(AIStep).where(AIStep.ai_run_id.in_(run_ids)))) if run_ids else []
    )
    approvals = list(
        db.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.workspace_id == auth.workspace_id,
                ApprovalRequest.project_id == project_id,
            )
        )
    )
    audit_counts = _audit_event_counts(db, auth, project_id)
    latest_report = read_latest_report()
    persisted_cache_summary = ai_cache_service.cache_summary(db, auth, project_id=project_id)
    report_cache_summary = latest_report.get("cache", {}) if isinstance(latest_report, dict) else {}
    cache_summary = (
        persisted_cache_summary
        if _cache_value(persisted_cache_summary, "hits")
        or _cache_value(persisted_cache_summary, "misses")
        or _cache_value(persisted_cache_summary, "stale_denials")
        else report_cache_summary
    )
    workflow_counts: dict[str, int] = {}
    for run in runs:
        workflow_counts[run.workflow_type] = workflow_counts.get(run.workflow_type, 0) + 1

    base_attributes = {
        "project_id": str(project_id),
        "workspace_id": str(auth.workspace_id),
        "source": "local",
    }
    metrics = [
        _metric("thesys.ai.workflow.runs", len(runs), "1", base_attributes),
        _metric(
            "thesys.ai.workflow.failures",
            sum(1 for run in runs if run.status == "failed"),
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.ai.workflow.cancellations",
            sum(1 for run in runs if run.status == "cancelled"),
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.ai.workflow.latency.avg",
            _average_run_latency(runs),
            "ms",
            base_attributes,
        ),
        _metric(
            "thesys.ai.model.latency.avg",
            _average_step_latency(_model_steps(steps)),
            "ms",
            {**base_attributes, "step_scope": "model"},
        ),
        _metric(
            "thesys.ai.retrieval.latency.avg",
            _average_step_latency(_retrieval_steps(steps)),
            "ms",
            {**base_attributes, "step_scope": "retrieval"},
        ),
        _metric(
            "thesys.ai.tokens.total",
            sum(run.total_tokens or 0 for run in runs),
            "tokens",
            base_attributes,
        ),
        _metric(
            "thesys.ai.cost.total",
            float(sum((run.total_cost or Decimal("0")) for run in runs)),
            "USD",
            base_attributes,
        ),
        _metric(
            "thesys.ai.budget.denials",
            audit_counts["budget_denials"],
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.ai.cache.hits",
            _cache_value(cache_summary, "hits"),
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.ai.cache.misses",
            _cache_value(cache_summary, "misses"),
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.ai.cache.stale_denials",
            _cache_value(cache_summary, "stale_denials"),
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.ai.cache.saved_tokens",
            _cache_value(cache_summary, "saved_tokens"),
            "tokens",
            base_attributes,
        ),
        _metric(
            "thesys.ai.cache.saved_cost",
            _cache_float(cache_summary, "saved_cost"),
            "USD",
            base_attributes,
        ),
        _metric(
            "thesys.ai.cache.latency_saved",
            _cache_value(cache_summary, "latency_saved_ms"),
            "ms",
            base_attributes,
        ),
        _metric(
            "thesys.ai.timeout.count",
            _count_steps_containing(steps, "timeout"),
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.tool.denials",
            audit_counts["tool_denials"],
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.approvals.pending",
            sum(1 for approval in approvals if approval.status == "pending"),
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.approvals.wait.avg",
            _average_approval_wait_seconds(approvals),
            "s",
            base_attributes,
        ),
        _metric(
            "thesys.provider_egress.denials",
            audit_counts["provider_egress_denials"],
            "1",
            base_attributes,
        ),
        _metric(
            "thesys.provider_egress.policy.enabled",
            1 if settings.provider_egress_policy_enabled else 0,
            "1",
            {
                **base_attributes,
                "allowed_host_count": str(len(settings.provider_egress_allowed_hosts)),
            },
        ),
    ]
    for workflow_type, count in sorted(workflow_counts.items()):
        metrics.append(
            _metric(
                "thesys.ai.workflow.runs.by_type",
                count,
                "1",
                {**base_attributes, "workflow_type": workflow_type},
            )
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "project_id": str(project_id),
        "metrics": metrics,
    }


def _report_dir() -> Path:
    configured = os.environ.get(REPORT_DIR_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_REPORT_DIR


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "available": False,
            "status": "warning",
            "message": f"Eval report is not valid JSON: {path}",
        }


def _metric(
    name: str,
    value: int | float,
    unit: str,
    attributes: dict[str, str],
) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "attributes": attributes,
        "temporality": "cumulative",
    }


def _average_step_latency(steps: list[AIStep]) -> int:
    latencies = [step.latency_ms for step in steps if step.latency_ms is not None]
    return int(sum(latencies) / max(len(latencies), 1))


def _average_run_latency(runs: list[AIRun]) -> int:
    latencies = []
    for run in runs:
        if run.started_at is None or run.completed_at is None:
            continue
        started_at = _utc(run.started_at)
        completed_at = _utc(run.completed_at)
        latencies.append(int((completed_at - started_at).total_seconds() * 1000))
    return int(sum(latencies) / max(len(latencies), 1))


def _model_steps(steps: list[AIStep]) -> list[AIStep]:
    names = ("model", "llm", "structured", "generation", "multimodal", "rerank")
    return [step for step in steps if any(name in step.step_name.casefold() for name in names)]


def _retrieval_steps(steps: list[AIStep]) -> list[AIStep]:
    return [step for step in steps if "retriev" in step.step_name.casefold()]


def _count_steps_containing(steps: list[AIStep], needle: str) -> int:
    lowered = needle.casefold()
    return sum(
        1
        for step in steps
        if lowered in step.status.casefold()
        or (step.error is not None and lowered in step.error.casefold())
    )


def _average_approval_wait_seconds(approvals: list[ApprovalRequest]) -> int:
    now = datetime.now(UTC)
    waits = []
    for approval in approvals:
        created_at = _utc(approval.created_at)
        end = _utc(approval.resolved_at) if approval.resolved_at else now
        waits.append(int((end - created_at).total_seconds()))
    return int(sum(waits) / max(len(waits), 1))


def _audit_event_counts(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> dict[str, int]:
    events = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.workspace_id == auth.workspace_id,
                AuditEvent.project_id == project_id,
                AuditEvent.event_type.in_(
                    ["tool_invocation_denied", "security_policy_denied"]
                ),
            )
        )
    )
    provider_denials = 0
    budget_denials = 0
    for event in events:
        metadata = event.event_metadata or {}
        detail = f"{metadata.get('detail', '')} {event.summary}".casefold()
        if "provider" in detail or "egress" in detail or "allowlist" in detail:
            provider_denials += 1
        if "budget" in detail or "cost" in detail or "token" in detail:
            budget_denials += 1
    return {
        "tool_denials": sum(1 for event in events if event.event_type == "tool_invocation_denied"),
        "policy_denials": sum(
            1 for event in events if event.event_type == "security_policy_denied"
        ),
        "provider_egress_denials": provider_denials,
        "budget_denials": budget_denials,
    }


def _cache_value(cache_summary: Any, key: str) -> int:
    if not isinstance(cache_summary, dict):
        return 0
    value = cache_summary.get(key, 0)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return 0


def _cache_float(cache_summary: Any, key: str) -> float:
    if not isinstance(cache_summary, dict):
        return 0.0
    value = cache_summary.get(key, 0)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
