import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.evals import AIEvalRead, GuideEvalRead, MvpEvalRead, V1ResearchEvalRead
from app.services import eval_service

router = APIRouter(prefix="/api/projects/{project_id}/evals", tags=["evals"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/mvp", response_model=MvpEvalRead)
def run_mvp_eval(project_id: uuid.UUID, db: DbDep, auth: AuthContextDep) -> MvpEvalRead:
    return eval_service.run_mvp_eval(db, auth, project_id)


@router.get("/v1-research", response_model=V1ResearchEvalRead)
def run_v1_research_eval(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> V1ResearchEvalRead:
    return eval_service.run_v1_research_eval(db, auth, project_id)


@router.get("/guide", response_model=GuideEvalRead)
def run_guide_eval(project_id: uuid.UUID, db: DbDep, auth: AuthContextDep) -> GuideEvalRead:
    return eval_service.run_guide_eval(db, auth, project_id)


@router.get("/ai", response_model=AIEvalRead)
def run_ai_eval(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> AIEvalRead:
    return eval_service.run_ai_eval(db, auth, settings, project_id)
