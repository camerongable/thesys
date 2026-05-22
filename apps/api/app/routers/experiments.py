import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.prompts import VALIDATION_PLAN_PROMPT_VERSION
from app.core.auth import AuthContextDep, SettingsDep
from app.db.models import Artifact
from app.db.session import get_db
from app.schemas.artifacts import ArtifactRead
from app.schemas.validation import (
    ExperimentListRead,
    ExperimentRead,
    ExperimentResultCreate,
    ExperimentResultCreateRead,
    ValidationPlanGenerateCreate,
    ValidationPlanGenerateRead,
)
from app.services import validation_service

router = APIRouter(prefix="/api/projects/{project_id}/experiments", tags=["experiments"])
DbDep = Annotated[Session, Depends(get_db)]


def serialize_artifact(artifact: Artifact) -> ArtifactRead:
    current = validation_service.current_version(artifact)
    return ArtifactRead.model_validate(
        {**artifact.__dict__, "current_version": current, "versions": list(artifact.versions)}
    )


@router.get("", response_model=ExperimentListRead)
def list_experiments(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ExperimentListRead:
    experiments = validation_service.list_experiments(db, auth, project_id)
    return ExperimentListRead(
        experiments=[ExperimentRead.model_validate(experiment) for experiment in experiments]
    )


@router.post("/validation-plan", response_model=ValidationPlanGenerateRead)
def generate_validation_plan(
    project_id: uuid.UUID,
    payload: ValidationPlanGenerateCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> ValidationPlanGenerateRead:
    result = validation_service.generate_validation_plan(db, auth, settings, project_id, payload)
    return ValidationPlanGenerateRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=VALIDATION_PLAN_PROMPT_VERSION,
        model_provider=result.model_provider,
        model_name=result.model_name,
        used_stub=result.used_stub,
        total_tokens=result.total_tokens,
        total_cost=result.total_cost,
        artifact=serialize_artifact(result.artifact),
        experiments=[
            ExperimentRead.model_validate(experiment) for experiment in result.experiments
        ],
    )


@router.post("/{experiment_id}/results", response_model=ExperimentResultCreateRead)
def log_experiment_result(
    project_id: uuid.UUID,
    experiment_id: uuid.UUID,
    payload: ExperimentResultCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> ExperimentResultCreateRead:
    result = validation_service.log_experiment_result(db, auth, project_id, experiment_id, payload)
    return ExperimentResultCreateRead(
        result=result.result,
        experiment=result.experiment,
        assumption=result.assumption,
        project_confidence_score=result.project_confidence_score,
    )
