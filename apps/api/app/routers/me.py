from fastapi import APIRouter

from app.core.auth import AuthContextDep
from app.schemas.identity import MeRead

router = APIRouter(prefix="/api", tags=["identity"])


@router.get("/me", response_model=MeRead)
def read_me(auth: AuthContextDep) -> MeRead:
    return MeRead(user=auth.user, workspace=auth.workspace, role=auth.role)
