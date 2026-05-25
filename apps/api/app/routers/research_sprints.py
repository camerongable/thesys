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
    CompetitorCandidateActionRead,
    CompetitorCandidateListRead,
    CompetitorCandidateRead,
    CompetitorCandidateUpdate,
    CompetitorDiscoveryRunRead,
    DiscoveredSourceActionRead,
    DiscoveredSourceListRead,
    DiscoveredSourceRead,
    ResearchPlanRead,
    ResearchPlanUpdate,
    ResearchSprintApprovalRead,
    ResearchSprintListRead,
    ResearchSprintPlanCreate,
    ResearchSprintPlanRunRead,
    ResearchSprintRead,
    SourceDiscoveryRunRead,
)
from app.services import (
    competitor_discovery_service,
    research_sprint_service,
    source_discovery_service,
)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["research-sprints"])
DbDep = Annotated[Session, Depends(get_db)]


def serialize_plan(plan: ResearchPlan) -> ResearchPlanRead:
    return ResearchPlanRead.model_validate(plan)


def serialize_sprint(sprint: ResearchSprint) -> ResearchSprintRead:
    return ResearchSprintRead.model_validate({**sprint.__dict__, "plan": sprint.plan})


def serialize_source(source) -> DiscoveredSourceRead:
    return DiscoveredSourceRead.model_validate(source)


def serialize_candidate(candidate) -> CompetitorCandidateRead:
    return CompetitorCandidateRead.model_validate(candidate)


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


@router.get(
    "/research-sprints/{sprint_id}/sources",
    response_model=DiscoveredSourceListRead,
)
def list_discovered_sources(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> DiscoveredSourceListRead:
    sources = source_discovery_service.list_discovered_sources(db, auth, project_id, sprint_id)
    return DiscoveredSourceListRead(sources=[serialize_source(source) for source in sources])


@router.post(
    "/research-sprints/{sprint_id}/sources/discover",
    response_model=SourceDiscoveryRunRead,
)
def discover_sources(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> SourceDiscoveryRunRead:
    result = source_discovery_service.discover_sources(db, auth, settings, project_id, sprint_id)
    return SourceDiscoveryRunRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        generated_count=result.generated_count,
        candidate_count=result.candidate_count,
        sources=[serialize_source(source) for source in result.sources],
    )


@router.post(
    "/research-sprints/{sprint_id}/sources/{source_id}/approve",
    response_model=DiscoveredSourceActionRead,
)
def approve_discovered_source(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    source_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> DiscoveredSourceActionRead:
    source = source_discovery_service.approve_source_candidate(
        db,
        auth,
        settings,
        project_id,
        sprint_id,
        source_id,
    )
    return DiscoveredSourceActionRead(source=serialize_source(source))


@router.post(
    "/research-sprints/{sprint_id}/sources/{source_id}/reject",
    response_model=DiscoveredSourceActionRead,
)
def reject_discovered_source(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    source_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> DiscoveredSourceActionRead:
    source = source_discovery_service.reject_source_candidate(
        db,
        auth,
        project_id,
        sprint_id,
        source_id,
    )
    return DiscoveredSourceActionRead(source=serialize_source(source))


@router.get(
    "/research-sprints/{sprint_id}/competitor-candidates",
    response_model=CompetitorCandidateListRead,
)
def list_competitor_candidates(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> CompetitorCandidateListRead:
    candidates = competitor_discovery_service.list_competitor_candidates(
        db,
        auth,
        project_id,
        sprint_id,
    )
    return CompetitorCandidateListRead(
        candidates=[serialize_candidate(candidate) for candidate in candidates]
    )


@router.post(
    "/research-sprints/{sprint_id}/competitor-candidates/discover",
    response_model=CompetitorDiscoveryRunRead,
)
def discover_competitors(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> CompetitorDiscoveryRunRead:
    result = competitor_discovery_service.discover_competitors(
        db,
        auth,
        settings,
        project_id,
        sprint_id,
    )
    return CompetitorDiscoveryRunRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        generated_count=result.generated_count,
        candidate_count=result.candidate_count,
        candidates=[serialize_candidate(candidate) for candidate in result.candidates],
    )


@router.patch(
    "/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}",
    response_model=CompetitorCandidateRead,
)
def update_competitor_candidate(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: CompetitorCandidateUpdate,
    db: DbDep,
    auth: AuthContextDep,
) -> CompetitorCandidateRead:
    candidate = competitor_discovery_service.update_competitor_candidate(
        db,
        auth,
        project_id,
        sprint_id,
        candidate_id,
        payload,
    )
    return serialize_candidate(candidate)


@router.post(
    "/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/approve",
    response_model=CompetitorCandidateActionRead,
)
def approve_competitor_candidate(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> CompetitorCandidateActionRead:
    candidate = competitor_discovery_service.approve_competitor_candidate(
        db,
        auth,
        settings,
        project_id,
        sprint_id,
        candidate_id,
    )
    return CompetitorCandidateActionRead(candidate=serialize_candidate(candidate))


@router.post(
    "/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/reject",
    response_model=CompetitorCandidateActionRead,
)
def reject_competitor_candidate(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> CompetitorCandidateActionRead:
    candidate = competitor_discovery_service.reject_competitor_candidate(
        db,
        auth,
        project_id,
        sprint_id,
        candidate_id,
    )
    return CompetitorCandidateActionRead(candidate=serialize_candidate(candidate))
