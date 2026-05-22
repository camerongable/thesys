import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.ai.prompts import COMPETITOR_ANALYSIS_PROMPT_VERSION
from app.core.auth import AuthContextDep, SettingsDep
from app.db.models import Artifact, ArtifactVersion, Competitor
from app.db.session import get_db
from app.schemas.artifacts import ArtifactRead
from app.schemas.competitors import (
    CompetitorAnalysisRead,
    CompetitorAnalyzeCreate,
    CompetitorCreate,
    CompetitorListRead,
    CompetitorRead,
    CompetitorUpdate,
)
from app.services import competitor_service

router = APIRouter(prefix="/api/projects/{project_id}/competitors", tags=["competitors"])
DbDep = Annotated[Session, Depends(get_db)]


def serialize_competitor(competitor: Competitor) -> CompetitorRead:
    return CompetitorRead.model_validate(competitor)


def serialize_artifact(artifact: Artifact) -> ArtifactRead:
    versions = list(artifact.versions)
    current = _current_version(artifact)
    return ArtifactRead.model_validate(
        {
            **artifact.__dict__,
            "current_version": current,
            "versions": versions,
        }
    )


def _current_version(artifact: Artifact) -> ArtifactVersion | None:
    if artifact.current_version_id is None:
        return None
    return next(
        (version for version in artifact.versions if version.id == artifact.current_version_id),
        None,
    )


@router.get("", response_model=CompetitorListRead)
def list_competitors(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> CompetitorListRead:
    competitors = competitor_service.list_competitors(db, auth, project_id)
    return CompetitorListRead(
        competitors=[serialize_competitor(competitor) for competitor in competitors]
    )


@router.post("", response_model=CompetitorRead, status_code=status.HTTP_201_CREATED)
def create_competitor(
    project_id: uuid.UUID,
    payload: CompetitorCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> CompetitorRead:
    competitor = competitor_service.create_competitor(db, auth, project_id, payload)
    return serialize_competitor(competitor)


@router.post("/analyze", response_model=CompetitorAnalysisRead)
def analyze_competitors(
    project_id: uuid.UUID,
    payload: CompetitorAnalyzeCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> CompetitorAnalysisRead:
    result = competitor_service.analyze_competitors(db, auth, settings, project_id, payload)
    return CompetitorAnalysisRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=COMPETITOR_ANALYSIS_PROMPT_VERSION,
        model_provider=result.model_provider,
        model_name=result.model_name,
        used_stub=result.used_stub,
        total_tokens=result.total_tokens,
        total_cost=result.total_cost,
        retrieval_result_count=result.retrieval_result_count,
        ingested_source_count=result.ingested_source_count,
        artifact=serialize_artifact(result.artifact),
        competitors=[serialize_competitor(competitor) for competitor in result.competitors],
        claims=result.claims,
        citations=result.citations,
        unsupported_claims=result.unsupported_claims,
    )


@router.get("/{competitor_id}", response_model=CompetitorRead)
def get_competitor(
    project_id: uuid.UUID,
    competitor_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> CompetitorRead:
    competitor = competitor_service.get_competitor(db, auth, project_id, competitor_id)
    return serialize_competitor(competitor)


@router.patch("/{competitor_id}", response_model=CompetitorRead)
def update_competitor(
    project_id: uuid.UUID,
    competitor_id: uuid.UUID,
    payload: CompetitorUpdate,
    db: DbDep,
    auth: AuthContextDep,
) -> CompetitorRead:
    competitor = competitor_service.update_competitor(
        db,
        auth,
        project_id,
        competitor_id,
        payload,
    )
    return serialize_competitor(competitor)
