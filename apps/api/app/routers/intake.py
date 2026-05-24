import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.prompts import (
    STRUCTURED_INTAKE_FINALIZE_PROMPT_VERSION,
    STRUCTURED_INTAKE_PROMPT_VERSION,
)
from app.core.auth import AuthContextDep, SettingsDep
from app.core.errors import public_error_detail
from app.db.models import Project
from app.db.session import get_db
from app.schemas.intake import (
    ProjectIntakeRead,
    StructuredIntakeAnalyzeCreate,
    StructuredIntakeAnswerCreate,
    StructuredIntakeFinalizeCreate,
    StructuredIntakeFinalizeRead,
    StructuredIntakeRunRead,
)
from app.schemas.projects import ProjectRead
from app.services import intake_service, project_service

router = APIRouter(prefix="/api/projects/{project_id}/intake", tags=["intake"])
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


@router.post("/analyze", response_model=StructuredIntakeRunRead)
def analyze_intake(
    project_id: uuid.UUID,
    payload: StructuredIntakeAnalyzeCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> StructuredIntakeRunRead:
    try:
        result = intake_service.analyze_intake(db, auth, settings, project_id, payload)
    except intake_service.IntakeWorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=public_error_detail("Structured intake analysis failed.", exc),
        ) from exc

    return StructuredIntakeRunRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=STRUCTURED_INTAKE_PROMPT_VERSION,
        model_provider=result.model_provider,
        model_name=result.model_name,
        used_stub=result.used_stub,
        total_tokens=result.total_tokens,
        total_cost=result.total_cost,
        intake=result.intake,
    )


@router.post("/answer", response_model=StructuredIntakeRunRead)
def answer_intake(
    project_id: uuid.UUID,
    payload: StructuredIntakeAnswerCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> StructuredIntakeRunRead:
    try:
        result = intake_service.answer_intake(db, auth, settings, project_id, payload)
    except intake_service.IntakeWorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=public_error_detail("Structured intake answer processing failed.", exc),
        ) from exc

    return StructuredIntakeRunRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=STRUCTURED_INTAKE_PROMPT_VERSION,
        model_provider=result.model_provider,
        model_name=result.model_name,
        used_stub=result.used_stub,
        total_tokens=result.total_tokens,
        total_cost=result.total_cost,
        intake=result.intake,
    )


@router.post("/finalize", response_model=StructuredIntakeFinalizeRead)
def finalize_intake(
    project_id: uuid.UUID,
    payload: StructuredIntakeFinalizeCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> StructuredIntakeFinalizeRead:
    try:
        result = intake_service.finalize_intake(db, auth, project_id, payload)
    except intake_service.IntakeWorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=public_error_detail("Structured intake finalization failed.", exc),
        ) from exc

    return StructuredIntakeFinalizeRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=STRUCTURED_INTAKE_FINALIZE_PROMPT_VERSION,
        project=serialize_project(result.project),
        intake_record=ProjectIntakeRead.model_validate(result.intake_record),
        customer_segments=result.customer_segments,
        problems=result.problems,
    )
