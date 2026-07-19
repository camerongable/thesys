"""File-backed eval reports, trend summaries, and local observability metrics."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import AIRun, AIStep, ApprovalRequest, AuditEvent
from app.features.evals import observability_metrics, report_files
from app.services import ai_cache_service, project_service

REPORT_DIR_ENV = report_files.REPORT_DIR_ENV
DEFAULT_REPORT_DIR = report_files.DEFAULT_REPORT_DIR


def read_latest_report() -> dict[str, Any]:
    """Compatibility wrapper for feature-owned eval report file reading."""

    return report_files.read_latest_report()


def read_eval_trends(limit: int = 20) -> list[dict[str, Any]]:
    """Compatibility wrapper for feature-owned eval trend file reading."""

    return report_files.read_eval_trends(limit=limit)


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
    return observability_metrics.project_observability_payload(
        project_id=project_id,
        workspace_id=auth.workspace_id,
        runs=runs,
        steps=steps,
        approvals=approvals,
        audit_counts=audit_counts,
        cache_summary=cache_summary,
        provider_egress_policy_enabled=settings.provider_egress_policy_enabled,
        provider_egress_allowed_hosts=settings.provider_egress_allowed_hosts,
    )


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
    return observability_metrics.audit_event_counts(events)


_metric = observability_metrics.metric
_average_step_latency = observability_metrics.average_step_latency
_average_run_latency = observability_metrics.average_run_latency
_model_steps = observability_metrics.model_steps
_retrieval_steps = observability_metrics.retrieval_steps
_count_steps_containing = observability_metrics.count_steps_containing
_audit_event_counts_from_events = observability_metrics.audit_event_counts
_average_approval_wait_seconds = observability_metrics.average_approval_wait_seconds
_cache_value = observability_metrics.cache_value
_cache_float = observability_metrics.cache_float
_utc = observability_metrics.utc
