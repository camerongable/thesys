"""Workspace-scoped project CRUD helpers shared by feature services."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
from app.db.models import EvidenceSource, Project, ProjectThesis
from app.schemas.projects import ProjectCreate, ProjectUpdate
from app.services import object_storage_service


def list_projects(db: Session, auth: AuthContext) -> list[Project]:
    """List projects visible to the current workspace."""

    return list(
        db.scalars(
            select(Project)
            .where(Project.workspace_id == auth.workspace_id)
            .options(
                selectinload(Project.theses),
                selectinload(Project.customer_segments),
                selectinload(Project.problems),
            )
            .order_by(Project.updated_at.desc())
        )
    )


def get_project(db: Session, auth: AuthContext, project_id: uuid.UUID) -> Project:
    """Load a project and key relationships within the current workspace."""

    project = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.workspace_id == auth.workspace_id)
        .options(
            selectinload(Project.theses),
            selectinload(Project.customer_segments),
            selectinload(Project.problems),
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def create_project(db: Session, auth: AuthContext, payload: ProjectCreate) -> Project:
    """Create a project and optional initial thesis version."""

    require_permission(auth, "write_project")
    project = Project(
        workspace_id=auth.workspace_id,
        name=payload.name.strip(),
        short_description=payload.short_description,
        created_by=auth.user_id,
    )
    db.add(project)
    db.flush()

    thesis_text = payload.initial_thesis or payload.short_description
    if thesis_text:
        thesis = ProjectThesis(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            version=1,
            thesis_text=thesis_text.strip(),
            created_by=auth.user_id,
        )
        db.add(thesis)
        db.flush()
        project.current_thesis_id = thesis.id

    db.commit()
    return get_project(db, auth, project.id)


def update_project(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: ProjectUpdate,
) -> Project:
    """Update basic project metadata and status."""

    require_permission(auth, "write_project")
    project = get_project(db, auth, project_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        project.name = update_data["name"].strip()
    if "short_description" in update_data:
        project.short_description = update_data["short_description"]
    if "status" in update_data and update_data["status"] is not None:
        project.status = update_data["status"]

    db.commit()
    return get_project(db, auth, project.id)


def delete_project(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
) -> None:
    """Delete a project and its private evidence objects."""

    require_permission(auth, "delete_project")
    project = get_project(db, auth, project_id)
    stored_sources = list(
        db.scalars(
            select(EvidenceSource).where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
                EvidenceSource.object_storage_key.is_not(None),
            )
        )
    )
    # Imported here because governance event reads depend on project_service.
    from app.services import governance_service

    for source in stored_sources:
        object_storage_service.delete_evidence_object(
            settings,
            workspace_id=auth.workspace_id,
            project_id=project_id,
            source_id=source.id,
            key=source.object_storage_key or "",
        )
        governance_service.record_audit_event(
            db,
            auth,
            event_type="object_deleted",
            actor_type="user",
            entity_type="evidence_source",
            entity_id=source.id,
            risk_level="medium",
            summary="Deleted a private evidence object with its project.",
            metadata={
                "storage_mode": settings.object_storage_mode,
                "deleted_project_id": str(project_id),
            },
        )
    db.delete(project)
    db.commit()


def current_thesis(project: Project) -> ProjectThesis | None:
    """Return the loaded thesis currently marked active on a project."""

    if project.current_thesis_id is None:
        return None
    return next(
        (thesis for thesis in project.theses if thesis.id == project.current_thesis_id),
        None,
    )
