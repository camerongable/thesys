import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import User, Workspace
from app.db.session import get_db
from app.services.identity_service import ensure_dev_identity


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


def get_current_auth_context(
    db: DbDep,
    settings: SettingsDep,
    x_dev_user_email: DevUserEmailHeader = None,
    x_dev_user_name: DevUserNameHeader = None,
) -> AuthContext:
    if settings.auth_mode == "dev":
        return ensure_dev_identity(
            db,
            email=x_dev_user_email or settings.dev_auth_default_email,
            display_name=x_dev_user_name or settings.dev_auth_default_name,
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Only AUTH_MODE=dev is implemented in this Sprint 1 scaffold.",
    )


AuthContextDep = Annotated[AuthContext, Depends(get_current_auth_context)]
