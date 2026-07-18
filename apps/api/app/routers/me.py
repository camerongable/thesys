from fastapi import APIRouter, Response, status

from app.core.auth import AuthContextDep, DbDep
from app.schemas.identity import MeRead
from app.services import session_revocation_service

router = APIRouter(prefix="/api", tags=["identity"])


@router.get("/me", response_model=MeRead)
def read_me(auth: AuthContextDep) -> MeRead:
    return MeRead(user=auth.user, workspace=auth.workspace, role=auth.role)


@router.post("/session/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(auth: AuthContextDep, db: DbDep) -> Response:
    session_revocation_service.revoke_current_session(db, auth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
