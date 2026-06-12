import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import AIRun, AIStep, ArtifactVersion, Project, ResearchSprint

logger = logging.getLogger(__name__)

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "master_key",
    "access_key",
)
MAX_STRING_LENGTH = 2000


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    trace_url: str
    enabled: bool
    metadata: dict[str, Any]


def ensure_research_sprint_trace(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project: Project,
    sprint: ResearchSprint,
    *,
    workflow_version: str,
    model_provider: str | None = None,
    model_name: str | None = None,
    run: AIRun | None = None,
) -> TraceContext:
    trace_id = sprint.langsmith_trace_id or str(uuid.uuid4())
    trace_url = sprint.langsmith_trace_url or _trace_url(settings, trace_id)
    metadata = {
        "project_id": str(project.id),
        "research_sprint_id": str(sprint.id),
        "project_stage": project.status,
        "workflow_version": workflow_version,
        "user_id": str(auth.user_id) if auth.user_id else None,
        "model_provider": model_provider,
        "model_name": model_name,
        "started_at": (sprint.started_at or datetime.now(UTC)).isoformat(),
    }

    sprint.langsmith_trace_id = trace_id
    sprint.langsmith_trace_url = trace_url
    if run is not None:
        attach_run_trace(db, run, trace_id, trace_url)
    db.flush()

    if _langsmith_enabled(settings):
        _safe_create_run(
            settings,
            run_id=trace_id,
            name="research_sprint",
            run_type="chain",
            inputs={
                "objective": sprint.plan.objective,
                "research_questions": sprint.plan.research_questions,
            },
            outputs=None,
            metadata=metadata,
        )

    return TraceContext(
        trace_id=trace_id,
        trace_url=trace_url,
        enabled=_langsmith_enabled(settings),
        metadata=metadata,
    )


def ensure_run_trace(
    db: Session,
    settings: Settings,
    run: AIRun,
    *,
    metadata: dict[str, Any],
) -> TraceContext:
    trace_id = run.langsmith_trace_id or str(uuid.uuid4())
    trace_url = run.langsmith_trace_url or _trace_url(settings, trace_id)
    attach_run_trace(db, run, trace_id, trace_url)
    db.flush()

    if _langsmith_enabled(settings):
        _safe_create_run(
            settings,
            run_id=trace_id,
            name=run.workflow_type,
            run_type="chain",
            inputs={"input_summary": run.input_summary},
            outputs=None,
            metadata=metadata,
        )

    return TraceContext(
        trace_id=trace_id,
        trace_url=trace_url,
        enabled=_langsmith_enabled(settings),
        metadata=metadata,
    )


def attach_run_trace(db: Session, run: AIRun, trace_id: str, trace_url: str) -> AIRun:
    run.langsmith_trace_id = trace_id
    run.langsmith_trace_url = trace_url
    db.flush()
    return run


def attach_artifact_version_trace(
    db: Session,
    version: ArtifactVersion,
    trace: TraceContext,
) -> ArtifactVersion:
    version.langsmith_trace_id = trace.trace_id
    version.langsmith_trace_url = trace.trace_url
    db.flush()
    return version


def record_step_span(
    db: Session,
    settings: Settings,
    *,
    run: AIRun,
    step: AIStep,
    trace: TraceContext,
    span_name: str,
    input_json: dict[str, Any] | None,
    output_json: dict[str, Any] | None = None,
    error: str | None = None,
    run_type: str = "chain",
) -> AIStep:
    span_id = step.langsmith_run_id or str(uuid.uuid4())
    step.langsmith_trace_id = trace.trace_id
    step.langsmith_run_id = span_id
    step.langsmith_trace_url = trace.trace_url
    db.flush()

    if trace.enabled:
        metadata = {
            **trace.metadata,
            "ai_run_id": str(run.id),
            "ai_step_id": str(step.id),
            "workflow_type": run.workflow_type,
            "step_name": step.step_name,
            "latency_ms": step.latency_ms,
            "model_provider": run.model_provider,
            "model_name": run.model_name,
        }
        _safe_create_run(
            settings,
            run_id=span_id,
            name=span_name,
            run_type=run_type,
            inputs=input_json or {},
            outputs=output_json or {},
            metadata=metadata,
            parent_run_id=trace.trace_id,
            error=error,
        )

    return step


def complete_trace(
    settings: Settings,
    trace: TraceContext,
    *,
    output_summary: str | None = None,
    error: str | None = None,
    metrics: dict[str, int | float | str | Decimal | None] | None = None,
) -> None:
    if not trace.enabled:
        return
    try:
        from langsmith import Client

        client = Client(api_key=settings.langsmith_api_key, api_url=settings.langsmith_endpoint)
        client.update_run(
            trace.trace_id,
            outputs=_sanitize({"summary": output_summary, "metrics": metrics or {}}),
            error=error,
            end_time=datetime.now(UTC),
        )
    except Exception as exc:  # pragma: no cover - best-effort external telemetry
        logger.warning("LangSmith trace completion failed: %s", exc)


def sanitize_for_observability(value: Any) -> Any:
    return _sanitize(value)


def _langsmith_enabled(settings: Settings) -> bool:
    return bool(settings.langsmith_tracing and settings.langsmith_api_key)


def _trace_url(settings: Settings, trace_id: str) -> str:
    base = settings.langsmith_public_url_base.rstrip("/")
    project = settings.langsmith_project.strip() or "default"
    return f"{base}/o/default/projects/p/{project}/r/{trace_id}"


def _safe_create_run(
    settings: Settings,
    *,
    run_id: str,
    name: str,
    run_type: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any] | None,
    metadata: dict[str, Any],
    parent_run_id: str | None = None,
    error: str | None = None,
) -> None:
    try:
        from langsmith import Client

        client = Client(api_key=settings.langsmith_api_key, api_url=settings.langsmith_endpoint)
        client.create_run(
            name=name,
            run_type=run_type,
            id=run_id,
            parent_run_id=parent_run_id,
            project_name=settings.langsmith_project,
            inputs=_sanitize(inputs),
            outputs=_sanitize(outputs or {}),
            error=error,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            extra={"metadata": _sanitize(metadata)},
        )
    except Exception as exc:  # pragma: no cover - best-effort external telemetry
        logger.warning("LangSmith trace upload failed for %s: %s", name, exc)


def _sanitize(value: Any, *, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(item_key): _sanitize(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value[:100]]
    if isinstance(value, (tuple, set)):
        return [_sanitize(item) for item in list(value)[:100]]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str):
        return value if len(value) <= MAX_STRING_LENGTH else f"{value[:MAX_STRING_LENGTH]}..."
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return _sanitize(value.model_dump(mode="json"))
    return str(value)[:MAX_STRING_LENGTH]


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
