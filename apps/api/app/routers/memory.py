import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep
from app.db.session import get_db
from app.schemas.memory import (
    MemoryType,
    ProjectMemoryExplainRead,
    ProjectMemoryItemRead,
    ProjectMemoryListRead,
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
