from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.demo import DemoSeedRead
from app.services import demo_service

router = APIRouter(prefix="/api/demo", tags=["demo"])
DbDep = Annotated[Session, Depends(get_db)]


@router.post("/seed", response_model=DemoSeedRead)
def seed_demo_project(
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> DemoSeedRead:
    if settings.environment == "production" or settings.auth_mode != "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo seeding is only available in local dev mode.",
        )
    return demo_service.seed_demo_project(db, auth, settings)
