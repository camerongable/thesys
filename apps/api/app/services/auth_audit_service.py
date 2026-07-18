"""Credential-free persistence for authentication and authorization outcomes."""

import uuid
from typing import Literal

from sqlalchemy.orm import Session

from app.db.models import AuthenticationEvent

AuthenticationEventType = Literal[
    "login_success",
    "login_failure",
    "token_validation_failure",
    "workspace_access_denied",
    "role_change",
    "session_revoked",
    "cross_tenant_access_attempt",
]
AuthenticationMethod = Literal["dev", "jwt", "api_key", "oidc"]


def record_authentication_event(
    db: Session,
    *,
    event_type: AuthenticationEventType,
    authentication_method: AuthenticationMethod,
    reason_code: str | None = None,
    workspace_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> AuthenticationEvent:
    """Store fixed audit attributes only; credentials are deliberately not accepted."""

    event = AuthenticationEvent(
        workspace_id=workspace_id,
        user_id=user_id,
        event_type=event_type,
        authentication_method=authentication_method,
        reason_code=reason_code,
    )
    db.add(event)
    db.flush()
    return event
