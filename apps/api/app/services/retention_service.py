"""Retention policy registry and local cleanup primitives."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import (
    AIRun,
    AIStep,
    ArtifactVersion,
    AuditEvent,
    AuthenticationEvent,
    EvidenceSource,
    PiiTokenMapping,
)


class RetentionAsset(StrEnum):
    RAW_SOURCE_OBJECT = "raw_source_object"
    SANITIZED_TEXT = "sanitized_text"
    EMBEDDING = "embedding"
    PII_TOKEN_MAP = "pii_token_map"
    MODEL_PROMPT = "model_prompt"
    MODEL_OUTPUT = "model_output"
    LANGSMITH_TRACE = "langsmith_trace"
    AUDIT_EVENT = "audit_event"
    SECURITY_EVENT = "security_event"
    TEMPORAL_HISTORY = "temporal_history"


@dataclass(frozen=True)
class RetentionPolicy:
    asset: RetentionAsset
    days: int
    enforcement_boundary: str


@dataclass(frozen=True)
class LocalRetentionCleanupResult:
    """Counts returned by a workspace-scoped local-record retention purge."""

    model_prompts_redacted: int = 0
    model_outputs_redacted: int = 0
    trace_references_cleared: int = 0
    audit_events_deleted: int = 0
    security_events_deleted: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def policies(settings: Settings) -> dict[RetentionAsset, RetentionPolicy]:
    return {
        RetentionAsset.RAW_SOURCE_OBJECT: RetentionPolicy(
            RetentionAsset.RAW_SOURCE_OBJECT, settings.s3_retention_days, "object_storage"
        ),
        RetentionAsset.SANITIZED_TEXT: RetentionPolicy(
            RetentionAsset.SANITIZED_TEXT, settings.retention_sanitized_text_days, "database"
        ),
        RetentionAsset.EMBEDDING: RetentionPolicy(
            RetentionAsset.EMBEDDING, settings.retention_embedding_days, "database"
        ),
        RetentionAsset.PII_TOKEN_MAP: RetentionPolicy(
            RetentionAsset.PII_TOKEN_MAP, settings.retention_pii_token_map_days, "database"
        ),
        RetentionAsset.MODEL_PROMPT: RetentionPolicy(
            RetentionAsset.MODEL_PROMPT, settings.retention_model_prompt_days, "database"
        ),
        RetentionAsset.MODEL_OUTPUT: RetentionPolicy(
            RetentionAsset.MODEL_OUTPUT, settings.retention_model_output_days, "database"
        ),
        RetentionAsset.LANGSMITH_TRACE: RetentionPolicy(
            RetentionAsset.LANGSMITH_TRACE,
            settings.retention_langsmith_trace_days,
            "langsmith_provider",
        ),
        RetentionAsset.AUDIT_EVENT: RetentionPolicy(
            RetentionAsset.AUDIT_EVENT, settings.retention_audit_event_days, "database"
        ),
        RetentionAsset.SECURITY_EVENT: RetentionPolicy(
            RetentionAsset.SECURITY_EVENT, settings.retention_security_event_days, "database"
        ),
        RetentionAsset.TEMPORAL_HISTORY: RetentionPolicy(
            RetentionAsset.TEMPORAL_HISTORY,
            settings.retention_temporal_history_days,
            "temporal_provider",
        ),
    }


def expires_at(
    settings: Settings,
    asset: RetentionAsset,
    *,
    created_at: datetime | None = None,
) -> datetime:
    baseline = created_at or datetime.now(UTC)
    if baseline.tzinfo is None:
        baseline = baseline.replace(tzinfo=UTC)
    return baseline + timedelta(days=policies(settings)[asset].days)


def evidence_retention_metadata(
    settings: Settings,
    *,
    created_at: datetime,
) -> dict[str, str]:
    return {
        "raw_source_object_expires_at": expires_at(
            settings, RetentionAsset.RAW_SOURCE_OBJECT, created_at=created_at
        ).isoformat(),
        "sanitized_text_expires_at": expires_at(
            settings, RetentionAsset.SANITIZED_TEXT, created_at=created_at
        ).isoformat(),
        "embedding_expires_at": expires_at(
            settings, RetentionAsset.EMBEDDING, created_at=created_at
        ).isoformat(),
    }


def purge_expired_evidence_sources(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    """Delete expired workspace sources through the normal propagation path."""
    from app.services import evidence_service

    current_time = now or datetime.now(UTC)
    sources = list(
        db.scalars(
            select(EvidenceSource).where(EvidenceSource.workspace_id == auth.workspace_id)
        )
    )
    expired = [
        source
        for source in sources
        if _expired_source(source, current_time)
    ]
    for source in expired:
        evidence_service.delete_source(
            db,
            auth,
            settings,
            source.project_id,
            source.id,
            deletion_reason="retention_expired",
        )
    return len(expired)


def purge_expired_pii_token_mappings(
    db: Session,
    auth: AuthContext,
    *,
    now: datetime | None = None,
) -> int:
    """Delete only the caller workspace's expired reversible PII mappings."""
    current_time = now or datetime.now(UTC)
    result = db.execute(
        delete(PiiTokenMapping).where(
            PiiTokenMapping.workspace_id == auth.workspace_id,
            PiiTokenMapping.retention_expires_at <= current_time,
        ).execution_options(synchronize_session=False)
    )
    db.commit()
    return int(result.rowcount or 0)


def purge_expired_local_records(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> LocalRetentionCleanupResult:
    """Enforce local retention for one tenant without deleting run accounting.

    Execution status, timing, token, and cost fields remain available for product
    operations. Prompts, outputs, errors, and local trace links are removed on
    their individual schedules. Pre-authentication events lack a workspace and
    deliberately require a separate platform-maintenance path.
    """
    current_time = now or datetime.now(UTC)
    workspace_run_ids = select(AIRun.id).where(AIRun.workspace_id == auth.workspace_id)

    prompt_cutoff = _retention_cutoff(settings, RetentionAsset.MODEL_PROMPT, current_time)
    prompt_result = db.execute(
        update(AIRun)
        .where(
            AIRun.workspace_id == auth.workspace_id,
            AIRun.created_at <= prompt_cutoff,
            AIRun.input_summary.is_not(None),
        )
        .values(input_summary=None)
        .execution_options(synchronize_session=False)
    )
    prompt_step_result = db.execute(
        update(AIStep)
        .where(
            AIStep.ai_run_id.in_(workspace_run_ids),
            AIStep.created_at <= prompt_cutoff,
            AIStep.input_json.is_not(None),
        )
        .values(input_json=None)
        .execution_options(synchronize_session=False)
    )

    output_cutoff = _retention_cutoff(settings, RetentionAsset.MODEL_OUTPUT, current_time)
    output_result = db.execute(
        update(AIRun)
        .where(
            AIRun.workspace_id == auth.workspace_id,
            AIRun.created_at <= output_cutoff,
            or_(AIRun.output_summary.is_not(None), AIRun.error.is_not(None)),
        )
        .values(output_summary=None, error=None)
        .execution_options(synchronize_session=False)
    )
    output_step_result = db.execute(
        update(AIStep)
        .where(
            AIStep.ai_run_id.in_(workspace_run_ids),
            AIStep.created_at <= output_cutoff,
            or_(AIStep.output_json.is_not(None), AIStep.error.is_not(None)),
        )
        .values(output_json=None, error=None)
        .execution_options(synchronize_session=False)
    )

    trace_cutoff = _retention_cutoff(settings, RetentionAsset.LANGSMITH_TRACE, current_time)
    trace_result = db.execute(
        update(AIRun)
        .where(
            AIRun.workspace_id == auth.workspace_id,
            AIRun.created_at <= trace_cutoff,
            or_(AIRun.langsmith_trace_id.is_not(None), AIRun.langsmith_trace_url.is_not(None)),
        )
        .values(langsmith_trace_id=None, langsmith_trace_url=None)
        .execution_options(synchronize_session=False)
    )
    trace_step_result = db.execute(
        update(AIStep)
        .where(
            AIStep.ai_run_id.in_(workspace_run_ids),
            AIStep.created_at <= trace_cutoff,
            or_(
                AIStep.langsmith_trace_id.is_not(None),
                AIStep.langsmith_run_id.is_not(None),
                AIStep.langsmith_trace_url.is_not(None),
            ),
        )
        .values(langsmith_trace_id=None, langsmith_run_id=None, langsmith_trace_url=None)
        .execution_options(synchronize_session=False)
    )
    artifact_trace_result = db.execute(
        update(ArtifactVersion)
        .where(
            ArtifactVersion.workspace_id == auth.workspace_id,
            ArtifactVersion.created_at <= trace_cutoff,
            or_(
                ArtifactVersion.langsmith_trace_id.is_not(None),
                ArtifactVersion.langsmith_trace_url.is_not(None),
            ),
        )
        .values(langsmith_trace_id=None, langsmith_trace_url=None)
        .execution_options(synchronize_session=False)
    )

    audit_cutoff = _retention_cutoff(settings, RetentionAsset.AUDIT_EVENT, current_time)
    audit_result = db.execute(
        delete(AuditEvent)
        .where(
            AuditEvent.workspace_id == auth.workspace_id,
            AuditEvent.created_at <= audit_cutoff,
        )
        .execution_options(synchronize_session=False)
    )
    security_cutoff = _retention_cutoff(settings, RetentionAsset.SECURITY_EVENT, current_time)
    security_result = db.execute(
        delete(AuthenticationEvent)
        .where(
            AuthenticationEvent.workspace_id == auth.workspace_id,
            AuthenticationEvent.created_at <= security_cutoff,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()

    return LocalRetentionCleanupResult(
        model_prompts_redacted=_affected_rows(prompt_result) + _affected_rows(prompt_step_result),
        model_outputs_redacted=_affected_rows(output_result) + _affected_rows(output_step_result),
        trace_references_cleared=(
            _affected_rows(trace_result)
            + _affected_rows(trace_step_result)
            + _affected_rows(artifact_trace_result)
        ),
        audit_events_deleted=_affected_rows(audit_result),
        security_events_deleted=_affected_rows(security_result),
    )


def purge_expired_unscoped_authentication_events(
    db: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    """Delete expired pre-authentication events through the worker-only path."""
    if settings.database_runtime_role != "worker":
        raise RuntimeError("Unscoped authentication-event cleanup requires the worker role.")
    current_time = now or datetime.now(UTC)
    cutoff = _retention_cutoff(settings, RetentionAsset.SECURITY_EVENT, current_time)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        deleted = db.scalar(select(func.purge_expired_pre_authentication_events(cutoff)))
        db.commit()
        return int(deleted or 0)

    result = db.execute(
        delete(AuthenticationEvent)
        .where(
            AuthenticationEvent.workspace_id.is_(None),
            AuthenticationEvent.user_id.is_(None),
            AuthenticationEvent.created_at <= cutoff,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return _affected_rows(result)


def _expired_source(source: EvidenceSource, now: datetime) -> bool:
    security = (source.source_metadata or {}).get("security")
    if not isinstance(security, dict):
        return False
    expires_value = security.get("retention_expires_at")
    if not isinstance(expires_value, str):
        return False
    try:
        expires_at_value = datetime.fromisoformat(expires_value)
    except ValueError:
        return False
    if expires_at_value.tzinfo is None:
        expires_at_value = expires_at_value.replace(tzinfo=UTC)
    return expires_at_value <= now


def _retention_cutoff(settings: Settings, asset: RetentionAsset, now: datetime) -> datetime:
    return now - timedelta(days=policies(settings)[asset].days)


def _affected_rows(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)
