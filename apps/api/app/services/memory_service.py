"""Typed project-memory management for AI workflows.

Memory is modeled as inspectable domain data rather than chat transcript text.
Items can be semantic, episodic, procedural, preference, working, or project
memory, and each workflow selects only the memory types it is allowed to use.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_permission
from app.db.models import Assumption, ProjectMemoryItem, Risk
from app.schemas.memory import MemoryType, MemoryWritePolicy, ProjectMemoryItemRead
from app.services import project_service

ACTIVE_MEMORY_STATUSES = {"active", "proposed"}
WORKFLOW_MEMORY_TYPES: dict[str, set[str]] = {
    "assumption_extraction": {"semantic", "project", "preference"},
    "guide_chat": {"working", "semantic", "project", "preference"},
    "agentic_research": {"episodic", "semantic", "project", "procedural"},
    "opportunity_brief": {"semantic", "project", "episodic", "preference"},
    "competitor_analysis": {"semantic", "project", "episodic"},
    "validation_plan": {"semantic", "project", "procedural", "preference"},
    "validation_planning": {"semantic", "project", "procedural", "preference"},
    "validation_result_interpretation": {"episodic", "semantic", "project", "preference"},
    "decision_recommendation": {"episodic", "semantic", "project", "preference"},
}
WORKFLOW_STALE_HISTORY_ALLOWED = {
    "agentic_research",
    "validation_result_interpretation",
    "decision_recommendation",
}


@dataclass(frozen=True)
class MemorySelection:
    """Inspectable memory-selection result for context compilation and UI review."""

    selected: list[ProjectMemoryItem]
    excluded: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    policy: dict[str, Any]


def list_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    memory_type: MemoryType | None = None,
    include_stale: bool = False,
    limit: int = 50,
) -> list[ProjectMemoryItem]:
    """List typed project memory with stale/expired records hidden by default."""
    project_service.get_project(db, auth, project_id)
    stmt = select(ProjectMemoryItem).where(
        ProjectMemoryItem.workspace_id == auth.workspace_id,
        ProjectMemoryItem.project_id == project_id,
    )
    if memory_type is not None:
        stmt = stmt.where(ProjectMemoryItem.memory_type == memory_type)
    if not include_stale:
        stmt = stmt.where(
            ProjectMemoryItem.status.in_(ACTIVE_MEMORY_STATUSES),
            or_(
                ProjectMemoryItem.expires_at.is_(None),
                ProjectMemoryItem.expires_at > datetime.now(UTC),
            ),
        )
    return list(
        db.scalars(stmt.order_by(ProjectMemoryItem.updated_at.desc()).limit(min(limit, 100)))
    )


def select_memory_for_workflow(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    limit: int = 20,
) -> list[ProjectMemoryItem]:
    """Select memory types that are relevant for a specific AI workflow."""
    allowed_types = WORKFLOW_MEMORY_TYPES.get(
        workflow_type,
        {"semantic", "project", "episodic", "preference"},
    )
    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(ProjectMemoryItem)
            .where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.memory_type.in_(allowed_types),
                ProjectMemoryItem.status == "active",
                or_(
                    ProjectMemoryItem.expires_at.is_(None),
                    ProjectMemoryItem.expires_at > datetime.now(UTC),
                ),
            )
            .order_by(ProjectMemoryItem.updated_at.desc())
            .limit(min(limit, 100))
        )
    )


def select_memory_for_context(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    limit: int = 20,
) -> MemorySelection:
    """Select workflow memory and explain exclusions for context inspection."""
    allowed_types = WORKFLOW_MEMORY_TYPES.get(
        workflow_type,
        {"semantic", "project", "episodic", "preference"},
    )
    include_stale_history = workflow_type in WORKFLOW_STALE_HISTORY_ALLOWED
    now = datetime.now(UTC)
    project_service.get_project(db, auth, project_id)
    all_items = list(
        db.scalars(
            select(ProjectMemoryItem)
            .where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
            )
            .order_by(ProjectMemoryItem.updated_at.desc())
            .limit(200)
        )
    )
    conflicts = detect_memory_conflicts(db, auth, project_id, mark=True, commit=False)
    selected: list[ProjectMemoryItem] = []
    excluded: list[dict[str, Any]] = []
    for item in all_items:
        reason = _memory_exclusion_reason(
            item,
            allowed_types=allowed_types,
            include_stale_history=include_stale_history,
            now=now,
        )
        if reason is not None:
            excluded.append(_excluded(item, reason))
            continue
        selected.append(item)
        if len(selected) >= min(limit, 100):
            break
    return MemorySelection(
        selected=selected,
        excluded=excluded,
        conflicts=conflicts,
        policy={
            "workflow_type": workflow_type,
            "allowed_memory_types": sorted(allowed_types),
            "include_stale_history": include_stale_history,
            "limit": min(limit, 100),
        },
    )


def inspect_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str = "guide_chat",
) -> dict[str, Any]:
    """Return memory selected, excluded, proposed, and conflicted for Inspect."""
    selection = select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type=workflow_type,
        limit=50,
    )
    proposed = [
        item
        for item in list_memory(db, auth, project_id, include_stale=True, limit=100)
        if item.status == "proposed"
    ]
    return {
        "workflow_type": workflow_type,
        "selected_memory": [serialize_memory_item(item) for item in selection.selected],
        "excluded_memory": selection.excluded,
        "proposed_memory": [serialize_memory_item(item) for item in proposed],
        "conflicts": selection.conflicts,
        "policy": selection.policy,
    }


def explain_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> dict[str, Any]:
    """Return an inspectable explanation of why a memory item exists."""
    item = get_memory_item(db, auth, project_id, memory_id)
    provenance = item.provenance_metadata or {}
    source = provenance.get("source") or item.source_entity_type or item.entity_type or "unknown"
    explanation = (
        f"{item.title} is {item.memory_type} memory with {item.write_policy} write policy. "
        f"It came from {source} and is currently {item.status}."
    )
    return {
        "memory_item": serialize_memory_item(item),
        "explanation": explanation,
        "provenance": provenance,
    }


def get_memory_item(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> ProjectMemoryItem:
    item = db.scalar(
        select(ProjectMemoryItem).where(
            ProjectMemoryItem.workspace_id == auth.workspace_id,
            ProjectMemoryItem.project_id == project_id,
            ProjectMemoryItem.id == memory_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found.")
    return item


def upsert_memory_item(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    memory_type: MemoryType,
    write_policy: MemoryWritePolicy,
    title: str,
    summary: str,
    content: dict[str, Any],
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    source_entity_type: str | None = None,
    source_entity_id: uuid.UUID | None = None,
    provenance_metadata: dict[str, Any] | None = None,
    confidence_score: Decimal | None = None,
    status_value: str = "active",
    expires_at: datetime | None = None,
) -> ProjectMemoryItem:
    """Create or update a typed memory item under the project's governance model."""
    project_service.get_project(db, auth, project_id)
    existing = None
    if entity_type and entity_id:
        existing = db.scalar(
            select(ProjectMemoryItem).where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.entity_type == entity_type,
                ProjectMemoryItem.entity_id == entity_id,
                ProjectMemoryItem.memory_type == memory_type,
            )
        )
    if existing is None:
        existing = ProjectMemoryItem(
            workspace_id=auth.workspace_id,
            project_id=project_id,
            memory_type=memory_type,
            write_policy=write_policy,
            entity_type=entity_type,
            entity_id=entity_id,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            title=title[:255],
            summary=summary,
            content=content,
            provenance_metadata=provenance_metadata or {},
            confidence_score=confidence_score,
            status=status_value,
            expires_at=expires_at,
            created_by=auth.user_id,
        )
        db.add(existing)
    else:
        existing.write_policy = write_policy
        existing.source_entity_type = source_entity_type or existing.source_entity_type
        existing.source_entity_id = source_entity_id or existing.source_entity_id
        existing.title = title[:255]
        existing.summary = summary
        existing.content = content
        existing.provenance_metadata = provenance_metadata or existing.provenance_metadata
        existing.confidence_score = confidence_score
        existing.status = status_value
        existing.expires_at = expires_at
    db.flush()
    return existing


def propose_preference_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    title: str,
    summary: str,
    content: dict[str, Any],
    source: str = "user_preference",
) -> ProjectMemoryItem:
    """Create an approval-gated preference memory proposal."""
    require_permission(auth, "run_research")
    item = upsert_memory_item(
        db,
        auth,
        project_id,
        memory_type="preference",
        write_policy="approval_required",
        title=title,
        summary=summary,
        content=content or {"preference": summary},
        source_entity_type=source,
        provenance_metadata={
            "source": source,
            "proposal_kind": "preference_capture",
            "requires_human_approval": True,
        },
        status_value="proposed",
    )
    db.commit()
    db.refresh(item)
    return item


def propose_compacted_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    memory_type: MemoryType = "semantic",
    source_memory_ids: list[uuid.UUID] | None = None,
    title: str | None = None,
) -> ProjectMemoryItem:
    """Create an approval-gated compacted-memory candidate with provenance."""
    require_permission(auth, "run_research")
    source_items = _compaction_source_items(
        db,
        auth,
        project_id,
        workflow_type=workflow_type,
        source_memory_ids=source_memory_ids or [],
    )
    if not source_items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No source memory items are eligible for compaction.",
        )
    summary_parts = [item.summary.strip() for item in source_items if item.summary.strip()]
    summary = " ".join(summary_parts)[:1800]
    item = upsert_memory_item(
        db,
        auth,
        project_id,
        memory_type=memory_type,
        write_policy="approval_required",
        title=title or f"Compacted {workflow_type} memory",
        summary=summary,
        content={
            "summary": summary,
            "source_memory_ids": [str(item.id) for item in source_items],
            "source_memory_titles": [item.title for item in source_items],
            "workflow_type": workflow_type,
        },
        source_entity_type="memory_compaction",
        provenance_metadata={
            "source": "memory_compaction",
            "workflow_type": workflow_type,
            "source_memory_ids": [str(item.id) for item in source_items],
            "source_entity_refs": [
                {
                    "memory_id": str(item.id),
                    "source_entity_type": item.source_entity_type,
                    "source_entity_id": str(item.source_entity_id) if item.source_entity_id else None,
                    "superseded_by_id": str(item.superseded_by_id) if item.superseded_by_id else None,
                }
                for item in source_items
            ],
            "requires_human_approval": True,
        },
        status_value="proposed",
    )
    db.commit()
    db.refresh(item)
    return item


def approve_memory_proposal(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> ProjectMemoryItem:
    """Promote proposed memory to active memory after human review."""
    require_permission(auth, "approve_memory_updates")
    item = get_memory_item(db, auth, project_id, memory_id)
    if item.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only proposed memory can be approved.",
        )
    item.status = "active"
    metadata = dict(item.provenance_metadata or {})
    metadata["approved_by_user_id"] = str(auth.user_id)
    metadata["approved_at"] = datetime.now(UTC).isoformat()
    item.provenance_metadata = metadata
    db.commit()
    db.refresh(item)
    return item


def reject_memory_proposal(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> ProjectMemoryItem:
    """Archive proposed memory after human rejection while preserving auditability."""
    require_permission(auth, "approve_memory_updates")
    item = get_memory_item(db, auth, project_id, memory_id)
    if item.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only proposed memory can be rejected.",
        )
    item.status = "archived"
    metadata = dict(item.provenance_metadata or {})
    metadata["rejected_by_user_id"] = str(auth.user_id)
    metadata["rejected_at"] = datetime.now(UTC).isoformat()
    item.provenance_metadata = metadata
    db.commit()
    db.refresh(item)
    return item


def upsert_from_assumption(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    assumption: Assumption,
    *,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    source_metadata: dict[str, Any] | None = None,
) -> ProjectMemoryItem:
    """Mirror an assumption into semantic memory with approval provenance."""

    provenance_metadata = {
        "source": source_entity_type,
        "source_entity_id": str(source_entity_id),
        "approval_required": True,
    }
    provenance_metadata.update(source_metadata or {})
    return upsert_memory_item(
        db,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        entity_type="assumption",
        entity_id=assumption.id,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        title="Assumption memory",
        summary=assumption.text,
        content={
            "text": assumption.text,
            "category": assumption.category,
            "importance": assumption.importance,
            "uncertainty": assumption.uncertainty,
            "kill_risk": assumption.kill_risk,
            "status": assumption.status,
        },
        provenance_metadata=provenance_metadata,
        confidence_score=assumption.confidence_score,
    )


def upsert_from_risk(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    risk: Risk,
    *,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    source_metadata: dict[str, Any] | None = None,
) -> ProjectMemoryItem:
    """Mirror a risk into semantic memory with approval provenance."""

    provenance_metadata = {
        "source": source_entity_type,
        "source_entity_id": str(source_entity_id),
        "approval_required": True,
    }
    provenance_metadata.update(source_metadata or {})
    return upsert_memory_item(
        db,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        entity_type="risk",
        entity_id=risk.id,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        title="Risk memory",
        summary=risk.text,
        content={
            "text": risk.text,
            "category": risk.category,
            "severity": risk.severity,
            "likelihood": risk.likelihood,
            "mitigation": risk.mitigation,
            "status": risk.status,
        },
        provenance_metadata=provenance_metadata,
    )


def mark_stale(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> ProjectMemoryItem:
    require_permission(auth, "approve_memory_updates")
    item = get_memory_item(db, auth, project_id, memory_id)
    item.status = "stale"
    db.commit()
    db.refresh(item)
    return item


def archive_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> ProjectMemoryItem:
    require_permission(auth, "approve_memory_updates")
    item = get_memory_item(db, auth, project_id, memory_id)
    item.status = "archived"
    db.commit()
    db.refresh(item)
    return item


def merge_duplicates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    keeper_id: uuid.UUID,
    duplicate_ids: list[uuid.UUID],
) -> ProjectMemoryItem:
    require_permission(auth, "approve_memory_updates")
    keeper = get_memory_item(db, auth, project_id, keeper_id)
    for duplicate_id in duplicate_ids:
        if duplicate_id == keeper_id:
            continue
        duplicate = get_memory_item(db, auth, project_id, duplicate_id)
        duplicate.status = "superseded"
        duplicate.superseded_by_id = keeper.id
    db.commit()
    db.refresh(keeper)
    return keeper


def detect_memory_conflicts(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    mark: bool = True,
    commit: bool = False,
) -> list[dict[str, Any]]:
    """Detect active memory records that conflict on the same durable subject."""
    project_service.get_project(db, auth, project_id)
    items = list(
        db.scalars(
            select(ProjectMemoryItem).where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.status == "active",
                ProjectMemoryItem.memory_type.in_(("semantic", "project", "preference")),
            )
        )
    )
    groups: dict[str, list[ProjectMemoryItem]] = {}
    for item in items:
        groups.setdefault(_conflict_key(item), []).append(item)
    conflicts: list[dict[str, Any]] = []
    for key, candidates in groups.items():
        summaries = {_normalize_text(item.summary) for item in candidates}
        if len(candidates) < 2 or len(summaries) < 2:
            continue
        conflict_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"thesys:memory-conflict:{project_id}:{key}"))
        if mark:
            for item in candidates:
                metadata = dict(item.provenance_metadata or {})
                metadata["conflict_group_id"] = conflict_id
                metadata["conflict_detected_at"] = metadata.get(
                    "conflict_detected_at",
                    datetime.now(UTC).isoformat(),
                )
                item.provenance_metadata = metadata
        conflicts.append(
            {
                "conflict_group_id": conflict_id,
                "reason": "Active memory records make different claims about the same subject.",
                "memory_item_ids": [item.id for item in candidates],
                "titles": [item.title for item in candidates],
            }
        )
    if mark:
        db.flush()
        if commit:
            db.commit()
    return conflicts


def resolve_memory_conflict(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    conflict_group_id: str,
    keeper_id: uuid.UUID,
    supersede_ids: list[uuid.UUID],
    archive_ids: list[uuid.UUID],
    reason: str,
) -> ProjectMemoryItem:
    """Resolve a memory conflict through explicit human-approved state changes."""
    require_permission(auth, "approve_memory_updates")
    detect_memory_conflicts(db, auth, project_id, mark=True, commit=False)
    keeper = get_memory_item(db, auth, project_id, keeper_id)
    _ensure_conflict_member(keeper, conflict_group_id)
    resolution_metadata = {
        "conflict_group_id": conflict_group_id,
        "resolved_by_user_id": str(auth.user_id),
        "resolved_at": datetime.now(UTC).isoformat(),
        "resolution_reason": reason,
    }
    keeper.status = "active"
    keeper.provenance_metadata = {**(keeper.provenance_metadata or {}), **resolution_metadata}
    for item_id in supersede_ids:
        item = get_memory_item(db, auth, project_id, item_id)
        _ensure_conflict_member(item, conflict_group_id)
        item.status = "superseded"
        item.superseded_by_id = keeper.id
        item.provenance_metadata = {**(item.provenance_metadata or {}), **resolution_metadata}
    for item_id in archive_ids:
        item = get_memory_item(db, auth, project_id, item_id)
        _ensure_conflict_member(item, conflict_group_id)
        item.status = "archived"
        item.provenance_metadata = {**(item.provenance_metadata or {}), **resolution_metadata}
    db.commit()
    db.refresh(keeper)
    return keeper


def serialize_memory_item(item: ProjectMemoryItem) -> dict[str, Any]:
    return ProjectMemoryItemRead.model_validate(item).model_dump(mode="json")


def _memory_exclusion_reason(
    item: ProjectMemoryItem,
    *,
    allowed_types: set[str],
    include_stale_history: bool,
    now: datetime,
) -> str | None:
    if item.memory_type not in allowed_types:
        return "memory_type_not_allowed_for_workflow"
    if item.expires_at is not None and item.expires_at <= now:
        return "expired"
    if item.status == "active":
        return None
    if item.status == "stale" and include_stale_history:
        return None
    if item.status == "proposed":
        return "pending_human_review"
    return f"status_{item.status}"


def _excluded(item: ProjectMemoryItem, reason: str) -> dict[str, Any]:
    return {
        "id": item.id,
        "memory_type": item.memory_type,
        "status": item.status,
        "title": item.title,
        "reason": reason,
    }


def _compaction_source_items(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    source_memory_ids: list[uuid.UUID],
) -> list[ProjectMemoryItem]:
    if source_memory_ids:
        return [get_memory_item(db, auth, project_id, memory_id) for memory_id in source_memory_ids]
    selection = select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type=workflow_type,
        limit=12,
    )
    return [
        item
        for item in selection.selected
        if item.status in {"active", "stale"}
        and (item.source_entity_type or item.provenance_metadata.get("source"))
    ][:8]


def _conflict_key(item: ProjectMemoryItem) -> str:
    entity = str(item.entity_id) if item.entity_id else _normalize_text(item.title)
    return f"{item.memory_type}:{item.entity_type or 'title'}:{entity}"


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _ensure_conflict_member(item: ProjectMemoryItem, conflict_group_id: str) -> None:
    metadata = item.provenance_metadata or {}
    if metadata.get("conflict_group_id") != conflict_group_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Memory item is not part of the requested conflict group.",
        )
