import uuid

from fastapi import APIRouter, Response, status

from app.core.auth import AuthContextDep, DbDep
from app.schemas.identity import MeRead, WorkspaceMemberRead, WorkspaceMemberRoleUpdate
from app.services import identity_service, session_revocation_service

router = APIRouter(prefix="/api", tags=["identity"])


@router.get("/me", response_model=MeRead)
def read_me(auth: AuthContextDep) -> MeRead:
    return MeRead(user=auth.user, workspace=auth.workspace, role=auth.role)


@router.post("/session/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(auth: AuthContextDep, db: DbDep) -> Response:
    session_revocation_service.revoke_current_session(db, auth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/workspace/members/{user_id}/role", response_model=WorkspaceMemberRead)
def update_workspace_member_role(
    user_id: uuid.UUID,
    payload: WorkspaceMemberRoleUpdate,
    auth: AuthContextDep,
    db: DbDep,
) -> WorkspaceMemberRead:
    membership = identity_service.update_workspace_member_role(
        db,
        auth,
        user_id=user_id,
        role=payload.role,
    )
    return WorkspaceMemberRead(user_id=membership.user_id, role=membership.role)
