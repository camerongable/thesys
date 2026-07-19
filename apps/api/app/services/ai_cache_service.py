"""Versioned AI cache storage and metrics for cost/latency optimization."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import (
    AICacheEntry,
    AICacheEvent,
    Assumption,
    Decision,
    EvidenceChunk,
    EvidenceSource,
    ProjectMemoryItem,
    ProjectThesis,
    Risk,
)
from app.features.retrieval.security_policy import RETRIEVAL_SECURITY_POLICY_VERSION
from app.schemas.evidence import EvidenceRetrieveCreate

CacheType = Literal["embedding", "retrieval_plan", "rerank_result", "guide_answer"]

CACHE_SCHEMA_VERSION = "ai-cache:v1"
EMBEDDING_NORMALIZATION_VERSION = "embedding-normalization:v1"
CHUNKING_VERSION = "chunking:v1"
RETRIEVAL_POLICY_VERSION = "retrieval-policy:v3"
RERANK_SCORE_NORMALIZATION_VERSION = "rerank-score-normalization:v1"
GUIDE_ANSWER_CACHE_VERSION = "guide-answer-cache:v1"
SOURCE_QUALITY_POLICY_VERSION = "source-quality:v1"


@dataclass(frozen=True)
class CacheLookup:
    """Cache lookup result plus the telemetry event written for the access."""

    value: dict[str, Any] | None
    event: AICacheEvent | None

    @property
    def hit(self) -> bool:
        return self.value is not None and self.event is not None and self.event.event_type == "hit"


def lookup(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    cache_type: CacheType,
    key_payload: dict[str, Any],
    family_payload: dict[str, Any],
    version_payload: dict[str, Any],
    project_id: uuid.UUID | None,
    saved_tokens: int = 0,
    saved_cost: Decimal | str | float = Decimal("0"),
    latency_saved_ms: int = 0,
) -> CacheLookup:
    """Return a cached value or record why recomputation is required."""

    key_payload = _normalized(key_payload)
    family_payload = _normalized(family_payload)
    version_payload = _normalized(version_payload)
    key_hash = stable_hash({"key": key_payload, "versions": version_payload})
    family_hash = stable_hash(family_payload)
    enabled, disabled_reason = _cache_enabled(settings, cache_type)
    if not enabled:
        event = _record_event(
            db,
            auth,
            cache_type=cache_type,
            event_type="disabled",
            project_id=project_id,
            key_hash=key_hash,
            family_hash=family_hash,
            reason=disabled_reason,
        )
        return CacheLookup(value=None, event=event)

    entry = _find_entry(db, auth, cache_type, project_id, key_hash)
    if entry is not None and entry.status == "active" and _not_expired(entry):
        if _versions_match(entry.version_payload, version_payload):
            entry.hit_count += 1
            entry.last_accessed_at = datetime.now(UTC)
            event = _record_event(
                db,
                auth,
                cache_type=cache_type,
                event_type="hit",
                project_id=project_id,
                entry=entry,
                key_hash=key_hash,
                family_hash=family_hash,
                saved_tokens=saved_tokens,
                saved_cost=saved_cost,
                latency_saved_ms=latency_saved_ms,
                metadata={"cache_schema_version": CACHE_SCHEMA_VERSION},
            )
            db.commit()
            db.refresh(event)
            return CacheLookup(value=dict(entry.value_payload or {}), event=event)

        entry.status = "stale"
        reason = _stale_reason(entry.version_payload, version_payload)
        event = _record_event(
            db,
            auth,
            cache_type=cache_type,
            event_type="stale_denial",
            project_id=project_id,
            entry=entry,
            key_hash=key_hash,
            family_hash=family_hash,
            reason=reason,
            metadata={
                "cached_versions": entry.version_payload,
                "current_versions": version_payload,
            },
        )
        db.commit()
        db.refresh(event)
        return CacheLookup(value=None, event=event)

    stale_family = _find_family_entry(db, auth, cache_type, project_id, family_hash)
    if stale_family is not None:
        reason = _stale_reason(stale_family.version_payload, version_payload)
        event = _record_event(
            db,
            auth,
            cache_type=cache_type,
            event_type="stale_denial",
            project_id=project_id,
            entry=stale_family,
            key_hash=key_hash,
            family_hash=family_hash,
            reason=reason,
            metadata={
                "cached_key_hash": stale_family.key_hash,
                "current_key_hash": key_hash,
                "cached_versions": stale_family.version_payload,
                "current_versions": version_payload,
            },
        )
        db.commit()
        db.refresh(event)
        return CacheLookup(value=None, event=event)

    event = _record_event(
        db,
        auth,
        cache_type=cache_type,
        event_type="miss",
        project_id=project_id,
        key_hash=key_hash,
        family_hash=family_hash,
        reason="no matching cache entry",
    )
    db.commit()
    db.refresh(event)
    return CacheLookup(value=None, event=event)


def store(
    db: Session,
    auth: AuthContext,
    *,
    cache_type: CacheType,
    key_payload: dict[str, Any],
    family_payload: dict[str, Any],
    version_payload: dict[str, Any],
    value_payload: dict[str, Any],
    project_id: uuid.UUID | None,
) -> AICacheEntry:
    """Create or update a cache entry and record the write event."""

    key_payload = _normalized(key_payload)
    family_payload = _normalized(family_payload)
    version_payload = _normalized(version_payload)
    value_payload = _normalized(value_payload)
    key_hash = stable_hash({"key": key_payload, "versions": version_payload})
    family_hash = stable_hash(family_payload)
    entry = _find_entry(db, auth, cache_type, project_id, key_hash)
    if entry is None:
        entry = AICacheEntry(
            workspace_id=auth.workspace_id,
            project_id=project_id,
            scope_key=_scope_key(project_id),
            cache_type=cache_type,
            key_hash=key_hash,
            family_hash=family_hash,
            key_payload=key_payload,
            version_payload=version_payload,
            value_payload=value_payload,
            status="active",
        )
        db.add(entry)
        db.flush()
    else:
        entry.key_payload = key_payload
        entry.scope_key = _scope_key(project_id)
        entry.family_hash = family_hash
        entry.version_payload = version_payload
        entry.value_payload = value_payload
        entry.status = "active"
        entry.updated_at = datetime.now(UTC)
    _record_event(
        db,
        auth,
        cache_type=cache_type,
        event_type="write",
        project_id=project_id,
        entry=entry,
        key_hash=key_hash,
        family_hash=family_hash,
        metadata={"cache_schema_version": CACHE_SCHEMA_VERSION},
    )
    db.commit()
    db.refresh(entry)
    return entry


def cache_event_diagnostics(event: AICacheEvent | None) -> dict[str, Any] | None:
    """Serialize one cache event into diagnostics-safe fields."""

    if event is None:
        return None
    return {
        "cache_type": event.cache_type,
        "status": event.event_type,
        "reason": event.reason,
        "key_hash": event.key_hash,
        "family_hash": event.family_hash,
        "hits": 1 if event.event_type == "hit" else 0,
        "misses": 1 if event.event_type == "miss" else 0,
        "stale_denials": 1 if event.event_type == "stale_denial" else 0,
        "saved_tokens": event.saved_tokens,
        "saved_cost": str(event.saved_cost),
        "latency_saved_ms": event.latency_saved_ms,
    }


def cache_summary(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Aggregate cache events for reports and OpenTelemetry-compatible metrics."""

    stmt = select(AICacheEvent).where(AICacheEvent.workspace_id == auth.workspace_id)
    if project_id is not None:
        stmt = stmt.where(AICacheEvent.project_id == project_id)
    events = list(db.scalars(stmt))
    return {
        "hits": _count(events, "hit"),
        "misses": _count(events, "miss"),
        "stale_denials": _count(events, "stale_denial"),
        "writes": _count(events, "write"),
        "disabled": _count(events, "disabled"),
        "saved_tokens": sum(event.saved_tokens or 0 for event in events),
        "saved_cost": str(sum((event.saved_cost or Decimal("0")) for event in events)),
        "latency_saved_ms": sum(event.latency_saved_ms or 0 for event in events),
        "by_type": _summary_by_type(events),
    }


def embedding_cache_payloads(
    auth: AuthContext,
    settings: Settings,
    text: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    text_digest = text_hash(text)
    family = {
        "workspace_id": str(auth.workspace_id),
        "cache_type": "embedding",
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "dimension": settings.embedding_dimension,
        "text_hash": text_digest,
    }
    versions = {
        "embedding_version": settings.embedding_version,
        "normalization_version": EMBEDDING_NORMALIZATION_VERSION,
        "chunking_version": CHUNKING_VERSION,
        "cache_schema_version": CACHE_SCHEMA_VERSION,
    }
    key = {**family, **versions}
    return key, family, versions


def retrieval_cache_payloads(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
    *,
    context_profile: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    retrieval_settings = _retrieval_settings(settings)
    project_versions = project_state_versions(db, auth, project_id)
    versions = {
        **project_versions,
        "retrieval_policy_version": f"{RETRIEVAL_POLICY_VERSION}:{stable_hash(retrieval_settings)}",
        "context_profile": context_profile,
        "cache_schema_version": CACHE_SCHEMA_VERSION,
    }
    family = {
        "workspace_id": str(auth.workspace_id),
        "project_id": str(project_id),
        "principal_role": auth.role,
        "cache_type": "retrieval_plan",
        "query_hash": text_hash(payload.query),
        "mode": payload.mode,
        "top_k": payload.top_k,
        "filters": _retrieval_filters(payload),
        "context_profile": context_profile,
    }
    key = {**family, "retrieval_settings": retrieval_settings, "versions": versions}
    return key, family, versions


def rerank_cache_payloads(
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    *,
    query: str,
    candidate_chunk_ids: list[uuid.UUID],
    retrieval_policy_version: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    family = {
        "workspace_id": str(auth.workspace_id),
        "project_id": str(project_id),
        "cache_type": "rerank_result",
        "query_hash": text_hash(query),
        "candidate_chunk_ids": [str(chunk_id) for chunk_id in candidate_chunk_ids],
        "provider": settings.retrieval_reranker_provider,
    }
    versions = {
        "reranking_enabled": settings.retrieval_reranking_enabled,
        "reranker_provider": settings.retrieval_reranker_provider,
        "reranker_model": settings.litellm_model,
        "retrieval_policy_version": retrieval_policy_version,
        "score_normalization_version": RERANK_SCORE_NORMALIZATION_VERSION,
        "cache_schema_version": CACHE_SCHEMA_VERSION,
    }
    key = {**family, "versions": versions}
    return key, family, versions


def guide_answer_cache_payloads(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    *,
    message: str,
    recent_turns: list[dict[str, str]],
    prompt_version: str,
    expected_schema: str,
    context_pack: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    project_versions = project_state_versions(db, auth, project_id)
    family = {
        "workspace_id": str(auth.workspace_id),
        "project_id": str(project_id),
        "cache_type": "guide_answer",
        "message_hash": text_hash(message),
        "recent_turns_hash": stable_hash(recent_turns),
    }
    versions = {
        **project_versions,
        "prompt_version": prompt_version,
        "expected_schema": expected_schema,
        "provider": "stub" if settings.should_use_llm_stub else "litellm",
        "model": settings.litellm_model,
        "context_pack_hash": stable_hash(context_pack),
        "guide_answer_cache_version": GUIDE_ANSWER_CACHE_VERSION,
        "cache_schema_version": CACHE_SCHEMA_VERSION,
    }
    key = {**family, "versions": versions}
    return key, family, versions


def project_state_versions(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> dict[str, str]:
    """Return compact version strings for cache invalidation boundaries."""

    evidence_version = _collection_version(
        db,
        EvidenceSource,
        auth,
        project_id,
        timestamp_columns=("updated_at", "ingested_at", "created_at"),
    )
    chunk_version = _collection_version(
        db,
        EvidenceChunk,
        auth,
        project_id,
        timestamp_columns=("created_at", "embedded_at"),
    )
    memory_version = _collection_version(
        db,
        ProjectMemoryItem,
        auth,
        project_id,
        timestamp_columns=("updated_at", "created_at"),
    )
    thesis_count, thesis_max = _count_and_max(db, ProjectThesis, auth, project_id, "created_at")
    assumption_version = _collection_version(
        db,
        Assumption,
        auth,
        project_id,
        timestamp_columns=("updated_at", "created_at"),
    )
    risk_version = _collection_version(
        db,
        Risk,
        auth,
        project_id,
        timestamp_columns=("updated_at", "created_at"),
    )
    decision_count, decision_max = _count_and_max(db, Decision, auth, project_id, "created_at")
    return {
        "evidence_corpus_version": f"{evidence_version}:chunks:{chunk_version}",
        "memory_version": memory_version,
        "memory_policy_version": "memory-manager:v2",
        "thesis_version": f"count:{thesis_count}:max:{thesis_max}",
        "assumption_version": f"{assumption_version}:risks:{risk_version}",
        "decision_version": f"count:{decision_count}:max:{decision_max}",
        "source_quality_policy_version": SOURCE_QUALITY_POLICY_VERSION,
    }


def stable_hash(payload: Any) -> str:
    body = json.dumps(_normalized(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def text_hash(text: str) -> str:
    normalized = " ".join(text.split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _cache_enabled(settings: Settings, cache_type: CacheType) -> tuple[bool, str | None]:
    if cache_type == "embedding":
        return settings.ai_embedding_cache_enabled, "embedding cache disabled by configuration"
    if cache_type == "retrieval_plan":
        return settings.ai_retrieval_cache_enabled, "retrieval cache disabled by configuration"
    if cache_type == "rerank_result":
        return settings.ai_rerank_cache_enabled, "rerank cache disabled by configuration"
    if cache_type == "guide_answer":
        if not settings.ai_semantic_answer_cache_enabled:
            return False, "semantic answer cache disabled by default"
        if not settings.should_use_llm_stub and not settings.ai_semantic_answer_cache_live_enabled:
            return False, "semantic answer cache disabled for live providers"
        return True, None
    return False, f"unsupported cache type: {cache_type}"


def _find_entry(
    db: Session,
    auth: AuthContext,
    cache_type: CacheType,
    project_id: uuid.UUID | None,
    key_hash: str,
) -> AICacheEntry | None:
    stmt = select(AICacheEntry).where(
        AICacheEntry.workspace_id == auth.workspace_id,
        AICacheEntry.scope_key == _scope_key(project_id),
        AICacheEntry.cache_type == cache_type,
        AICacheEntry.key_hash == key_hash,
    )
    stmt = stmt.where(
        AICacheEntry.project_id == project_id
        if project_id is not None
        else AICacheEntry.project_id.is_(None)
    )
    return db.scalar(stmt.order_by(AICacheEntry.updated_at.desc()))


def _find_family_entry(
    db: Session,
    auth: AuthContext,
    cache_type: CacheType,
    project_id: uuid.UUID | None,
    family_hash: str,
) -> AICacheEntry | None:
    stmt = select(AICacheEntry).where(
        AICacheEntry.workspace_id == auth.workspace_id,
        AICacheEntry.scope_key == _scope_key(project_id),
        AICacheEntry.cache_type == cache_type,
        AICacheEntry.family_hash == family_hash,
        AICacheEntry.status == "active",
    )
    stmt = stmt.where(
        AICacheEntry.project_id == project_id
        if project_id is not None
        else AICacheEntry.project_id.is_(None)
    )
    return db.scalar(stmt.order_by(AICacheEntry.updated_at.desc()))


def _record_event(
    db: Session,
    auth: AuthContext,
    *,
    cache_type: CacheType,
    event_type: str,
    project_id: uuid.UUID | None,
    entry: AICacheEntry | None = None,
    key_hash: str | None = None,
    family_hash: str | None = None,
    reason: str | None = None,
    saved_tokens: int = 0,
    saved_cost: Decimal | str | float = Decimal("0"),
    latency_saved_ms: int = 0,
    metadata: dict[str, Any] | None = None,
) -> AICacheEvent:
    event = AICacheEvent(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        cache_entry_id=entry.id if entry is not None else None,
        cache_type=cache_type,
        event_type=event_type,
        reason=reason,
        key_hash=key_hash,
        family_hash=family_hash,
        saved_tokens=max(saved_tokens, 0),
        saved_cost=Decimal(str(saved_cost)),
        latency_saved_ms=max(latency_saved_ms, 0),
        event_metadata=_normalized(metadata or {}),
    )
    db.add(event)
    return event


def _scope_key(project_id: uuid.UUID | None) -> str:
    return str(project_id) if project_id is not None else "__workspace__"


def _versions_match(cached: dict[str, Any], current: dict[str, Any]) -> bool:
    return _normalized(cached) == _normalized(current)


def _stale_reason(cached: dict[str, Any], current: dict[str, Any]) -> str:
    cached_norm = _normalized(cached)
    current_norm = _normalized(current)
    changed = [
        key
        for key in sorted(set(cached_norm) | set(current_norm))
        if cached_norm.get(key) != current_norm.get(key)
    ]
    if not changed:
        return "cache key changed"
    return "version changed: " + ", ".join(changed[:8])


def _not_expired(entry: AICacheEntry) -> bool:
    if entry.expires_at is None:
        return True
    expires_at = entry.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at > datetime.now(UTC)


def _retrieval_settings(settings: Settings) -> dict[str, Any]:
    return {
        "security_policy_version": RETRIEVAL_SECURITY_POLICY_VERSION,
        "vector_path": settings.retrieval_vector_path,
        "python_fallback_enabled": settings.retrieval_python_fallback_enabled,
        "text_search_enabled": settings.retrieval_text_search_enabled,
        "text_search_weight": settings.retrieval_text_search_weight,
        "mmr_enabled": settings.retrieval_mmr_enabled,
        "mmr_lambda": settings.retrieval_mmr_lambda,
        "context_token_budget": settings.retrieval_context_token_budget,
        "max_chunks_per_source": settings.retrieval_max_chunks_per_source,
        "max_chunks_per_domain": settings.retrieval_max_chunks_per_domain,
        "max_chunks_per_source_type": settings.retrieval_max_chunks_per_source_type,
        "max_chunks_per_competitor": settings.retrieval_max_chunks_per_competitor,
        "min_context_score": settings.retrieval_min_context_score,
        "min_source_trust_score": settings.retrieval_min_source_trust_score,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": settings.embedding_dimension,
        "embedding_version": settings.embedding_version,
        "reranking_enabled": settings.retrieval_reranking_enabled,
        "reranker_provider": settings.retrieval_reranker_provider,
    }


def _retrieval_filters(payload: EvidenceRetrieveCreate) -> dict[str, Any]:
    return {
        "source_types": sorted(payload.source_types),
        "competitor_id": str(payload.competitor_id) if payload.competitor_id else None,
        "assumption_id": str(payload.assumption_id) if payload.assumption_id else None,
        "research_sprint_id": str(payload.research_sprint_id)
        if payload.research_sprint_id
        else None,
        "created_after": payload.created_after.isoformat() if payload.created_after else None,
        "created_before": payload.created_before.isoformat() if payload.created_before else None,
        "freshness_days": payload.freshness_days,
    }


def _collection_version(
    db: Session,
    model: Any,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    timestamp_columns: tuple[str, ...],
) -> str:
    count = db.scalar(
        select(func.count()).select_from(model).where(
            model.workspace_id == auth.workspace_id,
            model.project_id == project_id,
        )
    )
    maxima = []
    for column_name in timestamp_columns:
        column = getattr(model, column_name, None)
        if column is None:
            continue
        maxima.append(
            db.scalar(
                select(func.max(column)).where(
                    model.workspace_id == auth.workspace_id,
                    model.project_id == project_id,
                )
            )
        )
    max_value = max((str(value) for value in maxima if value is not None), default="none")
    return f"count:{int(count or 0)}:max:{max_value}"


def _count_and_max(
    db: Session,
    model: Any,
    auth: AuthContext,
    project_id: uuid.UUID,
    timestamp_column: str,
) -> tuple[int, str]:
    count = db.scalar(
        select(func.count()).select_from(model).where(
            model.workspace_id == auth.workspace_id,
            model.project_id == project_id,
        )
    )
    column = getattr(model, timestamp_column)
    max_value = db.scalar(
        select(func.max(column)).where(
            model.workspace_id == auth.workspace_id,
            model.project_id == project_id,
        )
    )
    return int(count or 0), str(max_value) if max_value is not None else "none"


def _count(events: list[AICacheEvent], event_type: str) -> int:
    return sum(1 for event in events if event.event_type == event_type)


def _summary_by_type(events: list[AICacheEvent]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for event in events:
        item = summary.setdefault(
            event.cache_type,
            {"hits": 0, "misses": 0, "stale_denials": 0, "writes": 0, "disabled": 0},
        )
        if event.event_type == "hit":
            item["hits"] += 1
        elif event.event_type == "miss":
            item["misses"] += 1
        elif event.event_type == "stale_denial":
            item["stale_denials"] += 1
        elif event.event_type == "write":
            item["writes"] += 1
        elif event.event_type == "disabled":
            item["disabled"] += 1
    return summary


def _normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalized(val) for key, val in sorted(value.items())}
    if isinstance(value, list | tuple):
        return [_normalized(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value
