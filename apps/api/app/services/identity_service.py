from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User, Workspace, WorkspaceMember

if TYPE_CHECKING:
    from app.core.auth import AuthContext


VALID_DEV_ROLES = {"owner", "admin", "editor", "viewer"}


def ensure_dev_identity(
    db: Session,
    *,
    email: str,
    display_name: str,
    role: str | None = None,
) -> "AuthContext":
    from app.core.auth import AuthContext

    normalized_email = email.strip().lower()
    external_auth_id = f"dev:{normalized_email}"

    user = db.scalar(select(User).where(User.external_auth_id == external_auth_id))
    if user is None:
        user = User(
            external_auth_id=external_auth_id,
            email=normalized_email,
            display_name=display_name,
        )
        db.add(user)
        db.flush()

    membership = db.scalar(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    requested_role = _normalize_role(role)

    if membership is not None:
        workspace = db.get(Workspace, membership.workspace_id)
        if workspace is None:
            raise RuntimeError("Workspace membership points to a missing workspace.")
        if membership.role == "member":
            membership.role = "editor"
        if requested_role is not None:
            membership.role = requested_role
        db.commit()
        db.refresh(membership)
        return AuthContext(user=user, workspace=workspace, role=membership.role)

    workspace = Workspace(name=f"{display_name}'s Workspace", created_by=user.id)
    db.add(workspace)
    db.flush()

    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=requested_role or "owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(user)
    db.refresh(workspace)

    return AuthContext(user=user, workspace=workspace, role=membership.role)


def _normalize_role(role: str | None) -> str | None:
    if role is None or role.strip() == "":
        return None
    normalized = "editor" if role.strip().lower() == "member" else role.strip().lower()
    if normalized not in VALID_DEV_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid dev auth role. Use owner, admin, editor, or viewer.",
        )
    return normalized
