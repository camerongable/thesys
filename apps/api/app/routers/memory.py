import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep
from app.db.session import get_db
from app.schemas.memory import (
    ProjectMemoryCompactionCreate,
    ProjectMemoryConflictResolveCreate,
    MemoryType,
    ProjectMemoryExplainRead,
    ProjectMemoryInspectRead,
    ProjectMemoryItemRead,
    ProjectMemoryListRead,
    ProjectMemoryPreferenceCreate,
)
from app.services import memory_service

router = APIRouter(prefix="/api/projects/{project_id}/memory", tags=["memory"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=ProjectMemoryListRead)
def list_project_memory(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    memory_type: MemoryType | None = None,
    include_stale: bool = False,
) -> ProjectMemoryListRead:
    items = memory_service.list_memory(
        db,
        auth,
        project_id,
        memory_type=memory_type,
        include_stale=include_stale,
    )
    return ProjectMemoryListRead(
        memory_items=[
            ProjectMemoryItemRead.model_validate(item)
            for item in items
        ]
    )


@router.get("/inspect", response_model=ProjectMemoryInspectRead)
def inspect_project_memory(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    workflow_type: str = "guide_chat",
) -> ProjectMemoryInspectRead:
    return ProjectMemoryInspectRead.model_validate(
        memory_service.inspect_memory(db, auth, project_id, workflow_type=workflow_type)
    )


@router.post("/preferences", response_model=ProjectMemoryItemRead)
def propose_project_preference_memory(
    project_id: uuid.UUID,
    payload: ProjectMemoryPreferenceCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectMemoryItemRead:
    return ProjectMemoryItemRead.model_validate(
        memory_service.propose_preference_memory(
            db,
            auth,
            project_id,
            title=payload.title,
            summary=payload.summary,
            content=payload.content,
            source=payload.source,
        )
    )


@router.post("/compact", response_model=ProjectMemoryItemRead)
def propose_project_compacted_memory(
    project_id: uuid.UUID,
    payload: ProjectMemoryCompactionCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectMemoryItemRead:
    return ProjectMemoryItemRead.model_validate(
        memory_service.propose_compacted_memory(
            db,
            auth,
            project_id,
            workflow_type=payload.workflow_type,
            memory_type=payload.memory_type,
            source_memory_ids=payload.source_memory_ids,
            title=payload.title,
        )
    )


@router.get("/{memory_id}/explain", response_model=ProjectMemoryExplainRead)
def explain_project_memory(
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectMemoryExplainRead:
    return ProjectMemoryExplainRead.model_validate(
        memory_service.explain_memory(db, auth, project_id, memory_id)
    )


@router.post("/{memory_id}/stale", response_model=ProjectMemoryItemRead)
def mark_project_memory_stale(
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectMemoryItemRead:
    return ProjectMemoryItemRead.model_validate(
        memory_service.mark_stale(db, auth, project_id, memory_id)
    )


@router.post("/{memory_id}/approve", response_model=ProjectMemoryItemRead)
def approve_project_memory_proposal(
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectMemoryItemRead:
    return ProjectMemoryItemRead.model_validate(
        memory_service.approve_memory_proposal(db, auth, project_id, memory_id)
    )


@router.post("/{memory_id}/reject", response_model=ProjectMemoryItemRead)
def reject_project_memory_proposal(
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectMemoryItemRead:
    return ProjectMemoryItemRead.model_validate(
        memory_service.reject_memory_proposal(db, auth, project_id, memory_id)
    )


@router.post("/conflicts/{conflict_group_id}/resolve", response_model=ProjectMemoryItemRead)
def resolve_project_memory_conflict(
    project_id: uuid.UUID,
    conflict_group_id: str,
    payload: ProjectMemoryConflictResolveCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectMemoryItemRead:
    return ProjectMemoryItemRead.model_validate(
        memory_service.resolve_memory_conflict(
            db,
            auth,
            project_id,
            conflict_group_id=conflict_group_id,
            keeper_id=payload.keeper_id,
            supersede_ids=payload.supersede_ids,
            archive_ids=payload.archive_ids,
            reason=payload.reason,
        )
    )


@router.post("/{memory_id}/archive", response_model=ProjectMemoryItemRead)
def archive_project_memory(
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectMemoryItemRead:
    return ProjectMemoryItemRead.model_validate(
        memory_service.archive_memory(db, auth, project_id, memory_id)
    )
