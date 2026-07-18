import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.oidc import oidc_external_auth_id
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
    elif user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity is not active.",
        )

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
        return AuthContext.from_identity(
            user=user,
            workspace=workspace,
            role=membership.role,
            authentication_method="dev",
            external_subject=normalized_email,
        )

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

    return AuthContext.from_identity(
        user=user,
        workspace=workspace,
        role=membership.role,
        authentication_method="dev",
        external_subject=normalized_email,
    )


def ensure_external_identity(
    db: Session,
    *,
    external_auth_id: str,
    email: str,
    display_name: str,
    workspace_name: str,
    role: str,
    authentication_method: str = "external",
    external_subject: str | None = None,
    token_id: str | None = None,
) -> "AuthContext":
    """Create or load a production-auth identity with a workspace membership."""
    from app.core.auth import AuthContext

    normalized_role = _normalize_role(role) or "viewer"
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.external_auth_id == external_auth_id))
    if user is None:
        user = User(
            external_auth_id=external_auth_id,
            email=normalized_email,
            display_name=display_name.strip() or normalized_email,
        )
        db.add(user)
        db.flush()
    elif user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity is not active.",
        )

    membership = db.scalar(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    if membership is None:
        workspace = Workspace(name=workspace_name.strip() or "Thesys Workspace", created_by=user.id)
        db.add(workspace)
        db.flush()
        membership = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=normalized_role,
        )
        db.add(membership)
        db.commit()
        db.refresh(user)
        db.refresh(workspace)
        return AuthContext.from_identity(
            user=user,
            workspace=workspace,
            role=membership.role,
            authentication_method=authentication_method,
            external_subject=external_subject,
            token_id=token_id,
        )

    workspace = db.get(Workspace, membership.workspace_id)
    if workspace is None:
        raise RuntimeError("Workspace membership points to a missing workspace.")
    membership.role = normalized_role
    db.commit()
    db.refresh(membership)
    return AuthContext.from_identity(
        user=user,
        workspace=workspace,
        role=membership.role,
        authentication_method=authentication_method,
        external_subject=external_subject,
        token_id=token_id,
    )


def resolve_oidc_identity(
    db: Session,
    *,
    issuer: str,
    external_subject: str,
    workspace_id: uuid.UUID,
    token_role: str,
    session_id: str | None,
    token_id: str | None,
) -> "AuthContext":
    """Resolve a pre-provisioned active OIDC user and exact workspace membership."""
    from app.core.auth import AuthContext

    user = db.scalar(
        select(User).where(
            User.external_auth_id == oidc_external_auth_id(issuer, external_subject)
        )
    )
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OIDC identity is not provisioned or active.",
        )

    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OIDC identity is not a member of the requested workspace.",
        )
    if membership.role != token_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OIDC role does not match the current workspace membership.",
        )

    workspace = db.get(Workspace, membership.workspace_id)
    if workspace is None:
        raise RuntimeError("Workspace membership points to a missing workspace.")
    return AuthContext.from_identity(
        user=user,
        workspace=workspace,
        role=membership.role,
        authentication_method="oidc",
        external_subject=external_subject,
        session_id=session_id,
        token_id=token_id,
    )


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
