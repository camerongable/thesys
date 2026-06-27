import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_permission
from app.db.models import Assumption, ProjectMemoryItem, Risk
from app.schemas.memory import MemoryType, ProjectMemoryItemRead, MemoryWritePolicy
from app.services import project_service

ACTIVE_MEMORY_STATUSES = {"active", "proposed"}
WORKFLOW_MEMORY_TYPES: dict[str, set[str]] = {
    "guide_chat": {"working", "semantic", "project", "preference"},
    "agentic_research": {"episodic", "semantic", "project", "procedural"},
    "validation_planning": {"semantic", "project", "procedural", "preference"},
    "decision_recommendation": {"episodic", "semantic", "project", "preference"},
}


def list_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    memory_type: MemoryType | None = None,
    include_stale: bool = False,
    limit: int = 50,
) -> list[ProjectMemoryItem]:
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
        db.scalars(
            stmt.order_by(ProjectMemoryItem.updated_at.desc()).limit(min(limit, 100))
        )
    )


def select_memory_for_workflow(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    limit: int = 20,
) -> list[ProjectMemoryItem]:
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


def explain_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> dict[str, Any]:
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


def upsert_from_assumption(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    assumption: Assumption,
    *,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
) -> ProjectMemoryItem:
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
        provenance_metadata={
            "source": source_entity_type,
            "source_entity_id": str(source_entity_id),
            "approval_required": True,
        },
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
) -> ProjectMemoryItem:
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
        provenance_metadata={
            "source": source_entity_type,
            "source_entity_id": str(source_entity_id),
            "approval_required": True,
        },
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


def serialize_memory_item(item: ProjectMemoryItem) -> dict[str, Any]:
    return ProjectMemoryItemRead.model_validate(item).model_dump(mode="json")
