import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthContext
from app.db.models import AIRun
from app.services import project_service


def get_run(db: Session, auth: AuthContext, run_id: uuid.UUID) -> AIRun:
    run = db.scalar(
        select(AIRun)
        .where(AIRun.id == run_id, AIRun.workspace_id == auth.workspace_id)
        .options(selectinload(AIRun.steps))
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    return run


def list_project_runs(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    limit: int,
) -> list[AIRun]:
    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(AIRun)
            .where(AIRun.workspace_id == auth.workspace_id, AIRun.project_id == project_id)
            .options(selectinload(AIRun.steps))
            .order_by(AIRun.created_at.desc())
            .limit(limit)
        )
    )
