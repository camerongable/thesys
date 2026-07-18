"""Retention policy registry and local cleanup primitives."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import EvidenceSource, PiiTokenMapping


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
        evidence_service.delete_source(db, auth, settings, source.project_id, source.id)
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
