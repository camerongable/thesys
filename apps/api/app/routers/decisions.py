import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep
from app.db.session import get_db
from app.schemas.validation import (
    DecisionCoachChatCreate,
    DecisionCoachChatRead,
    DecisionCreate,
    DecisionListRead,
    DecisionRead,
    DecisionRecommendationRead,
)
from app.services import validation_service

router = APIRouter(prefix="/api/projects/{project_id}/decisions", tags=["decisions"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=DecisionListRead)
def list_decisions(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> DecisionListRead:
    decisions = validation_service.list_decisions(db, auth, project_id)
    return DecisionListRead(
        decisions=[DecisionRead.model_validate(decision) for decision in decisions]
    )


@router.get("/recommendation", response_model=DecisionRecommendationRead)
def get_decision_recommendation(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> DecisionRecommendationRead:
    return validation_service.get_decision_recommendation(db, auth, project_id)


@router.post("/coach", response_model=DecisionCoachChatRead)
def chat_with_decision_coach(
    project_id: uuid.UUID,
    payload: DecisionCoachChatCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> DecisionCoachChatRead:
    return validation_service.chat_decision_coach(db, auth, project_id, payload.message)


@router.post("", response_model=DecisionRead, status_code=status.HTTP_201_CREATED)
def create_decision(
    project_id: uuid.UUID,
    payload: DecisionCreate,
    db: DbDep,
    auth: AuthContextDep,
) -> DecisionRead:
    decision = validation_service.create_decision(db, auth, project_id, payload)
    return DecisionRead.model_validate(decision)


@router.get("/{decision_id}", response_model=DecisionRead)
def get_decision(
    project_id: uuid.UUID,
    decision_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> DecisionRead:
    decision = validation_service.get_decision(db, auth, project_id, decision_id)
    return DecisionRead.model_validate(decision)
