"""Session revocation without persisting raw bearer-token identifiers."""

import hashlib
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import SessionRevocation
from app.services import auth_audit_service

if TYPE_CHECKING:
    from app.core.auth import AuthContext


def revoke_current_session(db: Session, auth: "AuthContext") -> None:
    identifier_hash = _current_identifier_hash(auth, required=True)
    try:
        existing = db.scalar(
            select(SessionRevocation).where(
                SessionRevocation.workspace_id == auth.workspace_id,
                SessionRevocation.user_id == auth.user_id,
                SessionRevocation.session_identifier_hash == identifier_hash,
            )
        )
        if existing is None:
            db.add(
                SessionRevocation(
                    workspace_id=auth.workspace_id,
                    user_id=auth.user_id,
                    session_identifier_hash=identifier_hash,
                )
            )
            auth_audit_service.record_authentication_event(
                db,
                event_type="session_revoked",
                authentication_method=auth.principal.authentication_method,
                reason_code="self_revocation",
                workspace_id=auth.workspace_id,
                user_id=auth.user_id,
            )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session revocation is unavailable.",
        ) from None


def is_current_session_revoked(db: Session, auth: "AuthContext") -> bool:
    identifier_hash = _current_identifier_hash(auth, required=False)
    if identifier_hash is None:
        return False
    try:
        return (
            db.scalar(
                select(SessionRevocation.id).where(
                    SessionRevocation.workspace_id == auth.workspace_id,
                    SessionRevocation.user_id == auth.user_id,
                    SessionRevocation.session_identifier_hash == identifier_hash,
                )
            )
            is not None
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session validation is unavailable.",
        ) from None


def _current_identifier_hash(auth: "AuthContext", *, required: bool) -> str | None:
    identifier = auth.principal.session_id or auth.principal.token_id
    if not identifier:
        if required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The authenticated session cannot be revoked.",
            )
        return None
    return hashlib.sha256(f"thesys-session-revocation:v1:{identifier}".encode()).hexdigest()
