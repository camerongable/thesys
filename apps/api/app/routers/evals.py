import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.evals import (
    AIEvalRead,
    ContextEvalRead,
    EvalObservabilityMetricsRead,
    EvalReportRead,
    EvalTrendListRead,
    GuideEvalRead,
    MvpEvalRead,
    V1ResearchEvalRead,
)
from app.services import eval_report_service, eval_service, security_policy_service

router = APIRouter(prefix="/api/projects/{project_id}/evals", tags=["evals"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/mvp", response_model=MvpEvalRead)
def run_mvp_eval(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> MvpEvalRead:
    with _guard_eval(db, auth, settings, project_id, "mvp_eval"):
        return eval_service.run_mvp_eval(db, auth, project_id)


@router.get("/v1-research", response_model=V1ResearchEvalRead)
def run_v1_research_eval(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> V1ResearchEvalRead:
    with _guard_eval(db, auth, settings, project_id, "v1_research_eval"):
        return eval_service.run_v1_research_eval(db, auth, project_id)


@router.get("/guide", response_model=GuideEvalRead)
def run_guide_eval(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> GuideEvalRead:
    with _guard_eval(db, auth, settings, project_id, "guide_eval"):
        return eval_service.run_guide_eval(db, auth, project_id)


@router.get("/context", response_model=ContextEvalRead)
def run_context_eval(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> ContextEvalRead:
    with _guard_eval(db, auth, settings, project_id, "context_eval"):
        return eval_service.run_context_eval(db, auth, settings, project_id)


@router.get("/ai", response_model=AIEvalRead)
def run_ai_eval(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> AIEvalRead:
    with _guard_eval(db, auth, settings, project_id, "ai_eval"):
        return eval_service.run_ai_eval(db, auth, settings, project_id)


@router.get("/reports/latest", response_model=EvalReportRead)
def get_latest_eval_report(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> EvalReportRead:
    with _guard_eval(db, auth, settings, project_id, "eval_report_read"):
        return EvalReportRead(report=eval_report_service.read_latest_report())


@router.get("/reports/trends", response_model=EvalTrendListRead)
def get_eval_trends(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
    limit: int = 20,
) -> EvalTrendListRead:
    with _guard_eval(db, auth, settings, project_id, "eval_trend_read"):
        return EvalTrendListRead(trends=eval_report_service.read_eval_trends(limit=limit))


@router.get("/observability-metrics", response_model=EvalObservabilityMetricsRead)
def get_eval_observability_metrics(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> EvalObservabilityMetricsRead:
    with _guard_eval(db, auth, settings, project_id, "eval_observability_metrics"):
        return EvalObservabilityMetricsRead.model_validate(
            eval_report_service.project_observability_metrics(db, auth, settings, project_id)
        )


def _guard_eval(
    db: Session,
    auth,
    settings,
    project_id: uuid.UUID,
    workflow_type: str,
):
    return security_policy_service.guarded_workflow(
        db,
        auth,
        settings,
        project_id=project_id,
        workflow_type=workflow_type,
        estimate=security_policy_service.merge_estimate(settings, multiplier=0.25),
    )
