import uuid
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import User, Workspace
from app.db.session import get_db
from app.services.identity_service import ensure_dev_identity

ProjectPermission = Literal[
    "view_project",
    "run_research",
    "approve_memory_updates",
    "approve_high_risk_tools",
    "record_decision",
    "delete_project",
    "write_project",
]

ROLE_PERMISSIONS: dict[str, set[ProjectPermission]] = {
    "owner": {
        "view_project",
        "run_research",
        "approve_memory_updates",
        "approve_high_risk_tools",
        "record_decision",
        "delete_project",
        "write_project",
    },
    "admin": {
        "view_project",
        "run_research",
        "approve_memory_updates",
        "approve_high_risk_tools",
        "record_decision",
        "write_project",
    },
    "editor": {
        "view_project",
        "run_research",
        "approve_memory_updates",
        "record_decision",
        "write_project",
    },
    "viewer": {"view_project"},
}


@dataclass(frozen=True)
class AuthContext:
    user: User
    workspace: Workspace
    role: str

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id


DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
DevUserEmailHeader = Annotated[str | None, Header()]
DevUserNameHeader = Annotated[str | None, Header()]
DevUserRoleHeader = Annotated[str | None, Header()]


def get_current_auth_context(
    db: DbDep,
    settings: SettingsDep,
    x_dev_user_email: DevUserEmailHeader = None,
    x_dev_user_name: DevUserNameHeader = None,
    x_dev_user_role: DevUserRoleHeader = None,
) -> AuthContext:
    if settings.auth_mode == "dev":
        return ensure_dev_identity(
            db,
            email=x_dev_user_email or settings.dev_auth_default_email,
            display_name=x_dev_user_name or settings.dev_auth_default_name,
            role=x_dev_user_role,
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Only AUTH_MODE=dev is implemented in this Sprint 1 scaffold.",
    )


AuthContextDep = Annotated[AuthContext, Depends(get_current_auth_context)]


def normalized_role(role: str) -> str:
    return "editor" if role == "member" else role


def has_permission(auth: AuthContext, permission: ProjectPermission) -> bool:
    return permission in ROLE_PERMISSIONS.get(normalized_role(auth.role), set())


def require_permission(auth: AuthContext, permission: ProjectPermission) -> None:
    if has_permission(auth, permission):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to perform this governed project action.",
    )
