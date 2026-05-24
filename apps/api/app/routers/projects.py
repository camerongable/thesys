import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep
from app.db.models import Project
from app.db.session import get_db
from app.schemas.overview import (
    IdeaReadinessRead,
    NextBestActionRead,
    ProjectOverviewRead,
    StrategicUpdateRead,
)
from app.schemas.projects import ProjectCreate, ProjectListRead, ProjectRead, ProjectUpdate
from app.services import project_overview_service, project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])
DbDep = Annotated[Session, Depends(get_db)]


def serialize_project(project: Project) -> ProjectRead:
    return ProjectRead.model_validate(
        {
            **project.__dict__,
            "current_thesis": project_service.current_thesis(project),
            "customer_segments": project.customer_segments,
            "problems": project.problems,
        }
    )


@router.get("", response_model=ProjectListRead)
def list_projects(
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectListRead:
    projects = project_service.list_projects(db, auth)
    return ProjectListRead(projects=[serialize_project(project) for project in projects])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectRead:
    project = project_service.create_project(db, auth, payload)
    return serialize_project(project)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectRead:
    project = project_service.get_project(db, auth, project_id)
    return serialize_project(project)


@router.get("/{project_id}/overview", response_model=ProjectOverviewRead)
def get_project_overview(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectOverviewRead:
    return project_overview_service.get_project_overview(db, auth, project_id)


@router.get("/{project_id}/readiness", response_model=IdeaReadinessRead)
def get_project_readiness(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> IdeaReadinessRead:
    return project_overview_service.get_idea_readiness(db, auth, project_id)


@router.get("/{project_id}/strategic-updates", response_model=list[StrategicUpdateRead])
def get_project_strategic_updates(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> list[StrategicUpdateRead]:
    return project_overview_service.get_strategic_updates(db, auth, project_id)


@router.post("/{project_id}/next-action", response_model=NextBestActionRead)
def execute_project_next_action(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> NextBestActionRead:
    return project_overview_service.execute_next_action(db, auth, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: DbDep,
    auth: AuthContextDep,
) -> ProjectRead:
    project = project_service.update_project(db, auth, project_id, payload)
    return serialize_project(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> Response:
    project_service.delete_project(db, auth, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
