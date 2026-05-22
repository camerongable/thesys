import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.evidence import (
    EvidenceNoteCreate,
    EvidenceRetrieveCreate,
    EvidenceRetrieveRead,
    EvidenceSourceListRead,
    EvidenceSourceRead,
    EvidenceUrlCreate,
)
from app.services import evidence_service, retrieval_service

router = APIRouter(prefix="/api/projects/{project_id}/evidence", tags=["evidence"])
DbDep = Annotated[Session, Depends(get_db)]
EvidenceUploadFile = Annotated[UploadFile, File()]


def serialize_source(source) -> EvidenceSourceRead:
    return EvidenceSourceRead.model_validate(evidence_service.serialize_source(source))


@router.get("", response_model=EvidenceSourceListRead)
def list_evidence_sources(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> EvidenceSourceListRead:
    sources = evidence_service.list_sources(db, auth, project_id)
    return EvidenceSourceListRead(sources=[serialize_source(source) for source in sources])


@router.post("/url", response_model=EvidenceSourceRead, status_code=status.HTTP_201_CREATED)
def add_url_evidence(
    project_id: uuid.UUID,
    payload: EvidenceUrlCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> EvidenceSourceRead:
    try:
        source = evidence_service.add_url_source(db, auth, settings, project_id, payload)
    except evidence_service.EvidenceIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="URL evidence ingestion failed.",
        ) from exc
    return serialize_source(source)


@router.post("/note", response_model=EvidenceSourceRead, status_code=status.HTTP_201_CREATED)
def add_note_evidence(
    project_id: uuid.UUID,
    payload: EvidenceNoteCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> EvidenceSourceRead:
    try:
        source = evidence_service.add_note_source(db, auth, settings, project_id, payload)
    except evidence_service.EvidenceIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Note evidence ingestion failed.",
        ) from exc
    return serialize_source(source)


@router.post("/file", response_model=EvidenceSourceRead, status_code=status.HTTP_201_CREATED)
def add_file_evidence(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
    file: EvidenceUploadFile,
) -> EvidenceSourceRead:
    try:
        source = evidence_service.add_file_source(db, auth, settings, project_id, file)
    except evidence_service.EvidenceIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File evidence ingestion failed.",
        ) from exc
    return serialize_source(source)


@router.post("/retrieve", response_model=EvidenceRetrieveRead)
def retrieve_evidence(
    project_id: uuid.UUID,
    payload: EvidenceRetrieveCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> EvidenceRetrieveRead:
    result = retrieval_service.retrieve_evidence(db, auth, settings, project_id, payload)
    return EvidenceRetrieveRead(
        ai_run_id=result.run.id,
        ai_step_id=result.step.id,
        mode=result.mode,
        query=result.query,
        results=result.results,
    )


@router.get("/{source_id}", response_model=EvidenceSourceRead)
def get_evidence_source(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> EvidenceSourceRead:
    source = evidence_service.get_source(db, auth, project_id, source_id)
    return serialize_source(source)


@router.post("/{source_id}/reprocess", response_model=EvidenceSourceRead)
def reprocess_evidence_source(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> EvidenceSourceRead:
    try:
        source = evidence_service.reprocess_source(db, auth, settings, project_id, source_id)
    except evidence_service.EvidenceIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Evidence source reprocessing failed.",
        ) from exc
    return serialize_source(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence_source(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> Response:
    evidence_service.delete_source(db, auth, project_id, source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
