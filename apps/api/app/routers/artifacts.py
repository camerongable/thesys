import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.ai.prompts import OPPORTUNITY_BRIEF_PROMPT_VERSION
from app.core.auth import AuthContextDep, SettingsDep
from app.db.models import Artifact, ArtifactVersion
from app.db.session import get_db
from app.schemas.artifacts import (
    ArtifactListRead,
    ArtifactRead,
    ArtifactType,
    ArtifactVersionListRead,
    ArtifactVersionRead,
    OpportunityBriefGenerateRead,
)
from app.services import opportunity_brief_service

router = APIRouter(prefix="/api/projects/{project_id}/artifacts", tags=["artifacts"])
DbDep = Annotated[Session, Depends(get_db)]
ArtifactTypeQuery = Annotated[ArtifactType | None, Query()]


def serialize_artifact(artifact: Artifact) -> ArtifactRead:
    versions = list(artifact.versions)
    current = opportunity_brief_service.current_version(artifact)
    return ArtifactRead.model_validate(
        {
            **artifact.__dict__,
            "current_version": current,
            "versions": versions,
        }
    )


def serialize_version(version: ArtifactVersion) -> ArtifactVersionRead:
    return ArtifactVersionRead.model_validate(version)


@router.get("", response_model=ArtifactListRead)
def list_artifacts(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    artifact_type: ArtifactTypeQuery = None,
) -> ArtifactListRead:
    artifacts = opportunity_brief_service.list_artifacts(db, auth, project_id, artifact_type)
    return ArtifactListRead(artifacts=[serialize_artifact(artifact) for artifact in artifacts])


@router.post("/opportunity-brief/generate", response_model=OpportunityBriefGenerateRead)
def generate_opportunity_brief(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> OpportunityBriefGenerateRead:
    result = opportunity_brief_service.generate_opportunity_brief(
        db,
        auth,
        settings,
        project_id,
    )
    return OpportunityBriefGenerateRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        prompt_version=OPPORTUNITY_BRIEF_PROMPT_VERSION,
        model_provider=result.model_provider,
        model_name=result.model_name,
        used_stub=result.used_stub,
        total_tokens=result.total_tokens,
        total_cost=result.total_cost,
        retrieval_result_count=result.retrieval_result_count,
        artifact=serialize_artifact(result.artifact),
        version=serialize_version(result.version),
        claims=result.claims,
        assumptions=result.assumptions,
        risks=result.risks,
        citations=result.citations,
        unsupported_claims=result.unsupported_claims,
    )


@router.get("/{artifact_id}", response_model=ArtifactRead)
def get_artifact(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ArtifactRead:
    artifact = opportunity_brief_service.get_artifact(db, auth, project_id, artifact_id)
    return serialize_artifact(artifact)


@router.get("/{artifact_id}/versions", response_model=ArtifactVersionListRead)
def list_artifact_versions(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ArtifactVersionListRead:
    artifact = opportunity_brief_service.get_artifact(db, auth, project_id, artifact_id)
    return ArtifactVersionListRead(
        versions=[serialize_version(version) for version in artifact.versions]
    )
