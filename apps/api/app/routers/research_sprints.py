import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.prompts import RESEARCH_SPRINT_PLANNING_PROMPT_VERSION
from app.core.auth import AuthContextDep, SettingsDep
from app.core.errors import public_error_detail
from app.db.models import ResearchPlan, ResearchSprint
from app.db.session import get_db
from app.schemas.research import (
    ResearchPlanRead,
    ResearchPlanUpdate,
    ResearchSprintApprovalRead,
    ResearchSprintListRead,
    ResearchSprintPlanCreate,
    ResearchSprintPlanRunRead,
    ResearchSprintRead,
)
from app.services import research_sprint_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["research-sprints"])
DbDep = Annotated[Session, Depends(get_db)]


def serialize_plan(plan: ResearchPlan) -> ResearchPlanRead:
    return ResearchPlanRead.model_validate(plan)


def serialize_sprint(sprint: ResearchSprint) -> ResearchSprintRead:
    return ResearchSprintRead.model_validate({**sprint.__dict__, "plan": sprint.plan})


@router.get("/research-sprints", response_model=ResearchSprintListRead)
def list_research_sprints(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ResearchSprintListRead:
    sprints = research_sprint_service.list_research_sprints(db, auth, project_id)
    return ResearchSprintListRead(sprints=[serialize_sprint(sprint) for sprint in sprints])


@router.post("/research-sprints/plan", response_model=ResearchSprintPlanRunRead)
def start_research_sprint_plan(
    project_id: uuid.UUID,
    payload: ResearchSprintPlanCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> ResearchSprintPlanRunRead:
    try:
        result = research_sprint_service.start_research_sprint_plan(
            db,
            auth,
            settings,
            project_id,
            payload,
        )
    except research_sprint_service.ResearchSprintWorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=public_error_detail("Research sprint planning failed.", exc),
        ) from exc

    return ResearchSprintPlanRunRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=RESEARCH_SPRINT_PLANNING_PROMPT_VERSION,
        model_provider=result.model_provider,
        model_name=result.model_name,
        used_stub=result.used_stub,
        total_tokens=result.total_tokens,
        total_cost=result.total_cost,
        sprint=serialize_sprint(result.sprint),
    )


@router.patch("/research-plans/{plan_id}", response_model=ResearchPlanRead)
def update_research_plan(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: ResearchPlanUpdate,
    db: DbDep,
    auth: AuthContextDep,
) -> ResearchPlanRead:
    plan = research_sprint_service.update_research_plan(db, auth, project_id, plan_id, payload)
    return serialize_plan(plan)


@router.post("/research-sprints/{sprint_id}/approve", response_model=ResearchSprintApprovalRead)
def approve_research_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    payload: ResearchPlanUpdate,
    db: DbDep,
    auth: AuthContextDep,
) -> ResearchSprintApprovalRead:
    sprint = research_sprint_service.approve_research_sprint(
        db,
        auth,
        project_id,
        sprint_id,
        payload,
    )
    return ResearchSprintApprovalRead(ai_run_id=sprint.ai_run_id, sprint=serialize_sprint(sprint))


@router.post("/research-sprints/{sprint_id}/reject", response_model=ResearchSprintApprovalRead)
def reject_research_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ResearchSprintApprovalRead:
    sprint = research_sprint_service.reject_research_sprint(db, auth, project_id, sprint_id)
    return ResearchSprintApprovalRead(ai_run_id=sprint.ai_run_id, sprint=serialize_sprint(sprint))
