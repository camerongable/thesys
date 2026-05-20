from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User, Workspace, WorkspaceMember

if TYPE_CHECKING:
    from app.core.auth import AuthContext


def ensure_dev_identity(db: Session, *, email: str, display_name: str) -> "AuthContext":
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
    if membership is not None:
        workspace = db.get(Workspace, membership.workspace_id)
        if workspace is None:
            raise RuntimeError("Workspace membership points to a missing workspace.")
        return AuthContext(user=user, workspace=workspace, role=membership.role)

    workspace = Workspace(name=f"{display_name}'s Workspace", created_by=user.id)
    db.add(workspace)
    db.flush()

    membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(membership)
    db.commit()
    db.refresh(user)
    db.refresh(workspace)

    return AuthContext(user=user, workspace=workspace, role=membership.role)
