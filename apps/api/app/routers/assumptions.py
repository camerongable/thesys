import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.prompts import ASSUMPTION_EXTRACTION_PROMPT_VERSION
from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.artifacts import AssumptionRead, RiskRead
from app.schemas.validation import (
    AssumptionExtractionRead,
    AssumptionListRead,
    AssumptionUpdate,
    RiskListRead,
)
from app.services import validation_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["assumptions"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/assumptions", response_model=AssumptionListRead)
def list_assumptions(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> AssumptionListRead:
    assumptions = validation_service.list_assumptions(db, auth, project_id)
    return AssumptionListRead(
        assumptions=[AssumptionRead.model_validate(assumption) for assumption in assumptions]
    )


@router.post("/assumptions/extract", response_model=AssumptionExtractionRead)
def extract_assumptions(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> AssumptionExtractionRead:
    result = validation_service.extract_assumptions_and_risks(db, auth, settings, project_id)
    return AssumptionExtractionRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=ASSUMPTION_EXTRACTION_PROMPT_VERSION,
        model_provider=result.model_provider,
        model_name=result.model_name,
        used_stub=result.used_stub,
        total_tokens=result.total_tokens,
        total_cost=result.total_cost,
        assumptions=result.assumptions,
        risks=result.risks,
    )


@router.patch("/assumptions/{assumption_id}", response_model=AssumptionRead)
def update_assumption(
    project_id: uuid.UUID,
    assumption_id: uuid.UUID,
    payload: AssumptionUpdate,
    db: DbDep,
    auth: AuthContextDep,
) -> AssumptionRead:
    assumption = validation_service.update_assumption(
        db,
        auth,
        project_id,
        assumption_id,
        payload,
    )
    return AssumptionRead.model_validate(assumption)


@router.get("/risks", response_model=RiskListRead)
def list_risks(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> RiskListRead:
    risks = validation_service.list_risks(db, auth, project_id)
    return RiskListRead(risks=[RiskRead.model_validate(risk) for risk in risks])


@router.post("/risks/extract", response_model=AssumptionExtractionRead)
def extract_risks(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> AssumptionExtractionRead:
    result = validation_service.extract_assumptions_and_risks(db, auth, settings, project_id)
    return AssumptionExtractionRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=ASSUMPTION_EXTRACTION_PROMPT_VERSION,
        model_provider=result.model_provider,
        model_name=result.model_name,
        used_stub=result.used_stub,
        total_tokens=result.total_tokens,
        total_cost=result.total_cost,
        assumptions=result.assumptions,
        risks=result.risks,
    )
