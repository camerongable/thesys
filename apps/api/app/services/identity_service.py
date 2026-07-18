import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.oidc import oidc_external_auth_id
from app.db.models import User, Workspace, WorkspaceMember
from app.services import auth_audit_service

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


def update_workspace_member_role(
    db: Session,
    auth: "AuthContext",
    *,
    user_id: uuid.UUID,
    role: str,
) -> WorkspaceMember:
    """Change a member role within the caller's workspace and audit the outcome."""

    from app.core.auth import require_workspace_owner
    from app.services import governance_service

    require_workspace_owner(auth)
    normalized_role = _normalize_role(role)
    if normalized_role is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A workspace role is required.",
        )

    # Serialize membership role updates so the final workspace owner cannot be demoted.
    db.scalar(select(Workspace).where(Workspace.id == auth.workspace_id).with_for_update())
    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == auth.workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if membership is None:
        _record_cross_tenant_member_attempt(db, auth, user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found.",
        )

    previous_role = membership.role
    if previous_role == normalized_role:
        return membership
    if previous_role == "owner" and normalized_role != "owner":
        owner_count = db.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == auth.workspace_id,
                WorkspaceMember.role == "owner",
            )
        )
        if owner_count == 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A workspace must retain at least one owner.",
            )

    membership.role = normalized_role
    auth_audit_service.record_authentication_event(
        db,
        event_type="role_change",
        authentication_method=auth.principal.authentication_method,
        reason_code="workspace_member_role_updated",
        workspace_id=auth.workspace_id,
        user_id=auth.user_id,
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="workspace_member_role_changed",
        actor_type="user",
        entity_type="workspace_member",
        entity_id=membership.id,
        risk_level="high",
        summary="Changed a workspace member role.",
        metadata={"previous_role": previous_role, "new_role": normalized_role},
    )
    db.commit()
    db.refresh(membership)
    return membership


def _record_cross_tenant_member_attempt(
    db: Session,
    auth: "AuthContext",
    user_id: uuid.UUID,
) -> None:
    exists_outside_workspace = db.scalar(
        select(WorkspaceMember.id).where(WorkspaceMember.user_id == user_id).limit(1)
    )
    if exists_outside_workspace is None:
        return
    auth_audit_service.record_authentication_event(
        db,
        event_type="cross_tenant_access_attempt",
        authentication_method=auth.principal.authentication_method,
        reason_code="workspace_member_outside_scope",
        workspace_id=auth.workspace_id,
        user_id=auth.user_id,
    )
    db.commit()


def _normalize_role(role: str | None) -> str | None:
    if role is None or role.strip() == "":
        return None
    normalized = "editor" if role.strip().lower() == "member" else role.strip().lower()
    if normalized not in VALID_DEV_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace role. Use owner, admin, editor, or viewer.",
        )
    return normalized
