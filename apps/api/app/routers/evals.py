import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep
from app.db.session import get_db
from app.schemas.evals import MvpEvalRead
from app.services import eval_service

router = APIRouter(prefix="/api/projects/{project_id}/evals", tags=["evals"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/mvp", response_model=MvpEvalRead)
def run_mvp_eval(project_id: uuid.UUID, db: DbDep, auth: AuthContextDep) -> MvpEvalRead:
    return eval_service.run_mvp_eval(db, auth, project_id)
