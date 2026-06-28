"""OpenTelemetry-compatible local observability metric assembly."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.db.models import AIRun, AIStep, ApprovalRequest, AuditEvent
from app.schemas.evals import EvalMetricPointRead


def project_observability_payload(
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    runs: list[AIRun],
    steps: list[AIStep],
    approvals: list[ApprovalRequest],
    audit_counts: dict[str, int],
    cache_summary: Any,
    provider_egress_policy_enabled: bool,
    provider_egress_allowed_hosts: list[str],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the hidden Inspect metric payload from preloaded project data."""

    workflow_counts: dict[str, int] = {}
    for run in runs:
        workflow_counts[run.workflow_type] = workflow_counts.get(run.workflow_type, 0) + 1

    base_attributes = {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "source": "local",
    }
    metrics = [
        metric("thesys.ai.workflow.runs", len(runs), "1", base_attributes),
        metric(
            "thesys.ai.workflow.failures",
            sum(1 for run in runs if run.status == "failed"),
            "1",
            base_attributes,
        ),
        metric(
            "thesys.ai.workflow.cancellations",
            sum(1 for run in runs if run.status == "cancelled"),
            "1",
            base_attributes,
        ),
        metric(
            "thesys.ai.workflow.latency.avg",
            average_run_latency(runs),
            "ms",
            base_attributes,
        ),
        metric(
            "thesys.ai.model.latency.avg",
            average_step_latency(model_steps(steps)),
            "ms",
            {**base_attributes, "step_scope": "model"},
        ),
        metric(
            "thesys.ai.retrieval.latency.avg",
            average_step_latency(retrieval_steps(steps)),
            "ms",
            {**base_attributes, "step_scope": "retrieval"},
        ),
        metric(
            "thesys.ai.tokens.total",
            sum(run.total_tokens or 0 for run in runs),
            "tokens",
            base_attributes,
        ),
        metric(
            "thesys.ai.cost.total",
            float(sum((run.total_cost or Decimal("0")) for run in runs)),
            "USD",
            base_attributes,
        ),
        metric(
            "thesys.ai.budget.denials",
            audit_counts["budget_denials"],
            "1",
            base_attributes,
        ),
        metric(
            "thesys.ai.cache.hits",
            cache_value(cache_summary, "hits"),
            "1",
            base_attributes,
        ),
        metric(
            "thesys.ai.cache.misses",
            cache_value(cache_summary, "misses"),
            "1",
            base_attributes,
        ),
        metric(
            "thesys.ai.cache.stale_denials",
            cache_value(cache_summary, "stale_denials"),
            "1",
            base_attributes,
        ),
        metric(
            "thesys.ai.cache.saved_tokens",
            cache_value(cache_summary, "saved_tokens"),
            "tokens",
            base_attributes,
        ),
        metric(
            "thesys.ai.cache.saved_cost",
            cache_float(cache_summary, "saved_cost"),
            "USD",
            base_attributes,
        ),
        metric(
            "thesys.ai.cache.latency_saved",
            cache_value(cache_summary, "latency_saved_ms"),
            "ms",
            base_attributes,
        ),
        metric(
            "thesys.ai.timeout.count",
            count_steps_containing(steps, "timeout"),
            "1",
            base_attributes,
        ),
        metric(
            "thesys.tool.denials",
            audit_counts["tool_denials"],
            "1",
            base_attributes,
        ),
        metric(
            "thesys.approvals.pending",
            sum(1 for approval in approvals if approval.status == "pending"),
            "1",
            base_attributes,
        ),
        metric(
            "thesys.approvals.wait.avg",
            average_approval_wait_seconds(approvals),
            "s",
            base_attributes,
        ),
        metric(
            "thesys.provider_egress.denials",
            audit_counts["provider_egress_denials"],
            "1",
            base_attributes,
        ),
        metric(
            "thesys.provider_egress.policy.enabled",
            1 if provider_egress_policy_enabled else 0,
            "1",
            {
                **base_attributes,
                "allowed_host_count": str(len(provider_egress_allowed_hosts)),
            },
        ),
    ]
    for workflow_type, count in sorted(workflow_counts.items()):
        metrics.append(
            metric(
                "thesys.ai.workflow.runs.by_type",
                count,
                "1",
                {**base_attributes, "workflow_type": workflow_type},
            )
        )
    return {
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "project_id": str(project_id),
        "metrics": metrics,
    }


def metric(
    name: str,
    value: int | float,
    unit: str,
    attributes: dict[str, str],
) -> dict[str, Any]:
    return EvalMetricPointRead(
        name=name,
        value=value,
        unit=unit,
        attributes=attributes,
        temporality="cumulative",
    ).model_dump()


def average_step_latency(steps: list[AIStep]) -> int:
    latencies = [step.latency_ms for step in steps if step.latency_ms is not None]
    return int(sum(latencies) / max(len(latencies), 1))


def average_run_latency(runs: list[AIRun]) -> int:
    latencies = []
    for run in runs:
        if run.started_at is None or run.completed_at is None:
            continue
        started_at = utc(run.started_at)
        completed_at = utc(run.completed_at)
        latencies.append(int((completed_at - started_at).total_seconds() * 1000))
    return int(sum(latencies) / max(len(latencies), 1))


def model_steps(steps: list[AIStep]) -> list[AIStep]:
    names = ("model", "llm", "structured", "generation", "multimodal", "rerank")
    return [step for step in steps if any(name in step.step_name.casefold() for name in names)]


def retrieval_steps(steps: list[AIStep]) -> list[AIStep]:
    return [step for step in steps if "retriev" in step.step_name.casefold()]


def count_steps_containing(steps: list[AIStep], needle: str) -> int:
    lowered = needle.casefold()
    return sum(
        1
        for step in steps
        if lowered in step.status.casefold()
        or (step.error is not None and lowered in step.error.casefold())
    )


def audit_event_counts(events: list[AuditEvent]) -> dict[str, int]:
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


def average_approval_wait_seconds(approvals: list[ApprovalRequest]) -> int:
    now = datetime.now(UTC)
    waits = []
    for approval in approvals:
        created_at = utc(approval.created_at)
        end = utc(approval.resolved_at) if approval.resolved_at else now
        waits.append(int((end - created_at).total_seconds()))
    return int(sum(waits) / max(len(waits), 1))


def cache_value(cache_summary: Any, key: str) -> int:
    if not isinstance(cache_summary, dict):
        return 0
    value = cache_summary.get(key, 0)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return 0


def cache_float(cache_summary: Any, key: str) -> float:
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


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
