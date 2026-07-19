import base64
import hashlib
import hmac
import json
import time
import uuid
from binascii import Error as Base64DecodeError
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.oidc import OIDCValidationError, verify_oidc_token
from app.db.models import User, Workspace
from app.db.session import get_db
from app.db.tenant import bind_tenant_context
from app.security.secrets import SecretName, SecretProviderError, resolve_secret
from app.services import auth_audit_service, session_revocation_service
from app.services.identity_service import (
    ensure_dev_identity,
    ensure_external_identity,
    resolve_oidc_identity,
)

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
class Principal:
    user_id: uuid.UUID
    external_subject: str
    workspace_id: uuid.UUID
    role: Literal["owner", "admin", "editor", "viewer"]
    authentication_method: str
    session_id: str | None = None
    token_id: str | None = None


@dataclass(frozen=True)
class AuthContext:
    user: User
    workspace: Workspace
    principal: Principal

    @classmethod
    def from_identity(
        cls,
        *,
        user: User,
        workspace: Workspace,
        role: str,
        authentication_method: str,
        external_subject: str | None = None,
        session_id: str | None = None,
        token_id: str | None = None,
    ) -> "AuthContext":
        normalized = normalized_role(role)
        if normalized not in ROLE_PERMISSIONS:
            raise ValueError("Identity has an unsupported workspace role.")
        principal = Principal(
            user_id=user.id,
            external_subject=external_subject or user.external_auth_id,
            workspace_id=workspace.id,
            role=normalized,
            authentication_method=authentication_method,
            session_id=session_id,
            token_id=token_id,
        )
        return cls(user=user, workspace=workspace, principal=principal)

    @property
    def user_id(self) -> uuid.UUID:
        return self.principal.user_id

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.principal.workspace_id

    @property
    def role(self) -> str:
        return self.principal.role


DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
DevUserEmailHeader = Annotated[str | None, Header()]
DevUserNameHeader = Annotated[str | None, Header()]
DevUserRoleHeader = Annotated[str | None, Header()]
AuthorizationHeader = Annotated[str | None, Header()]
ApiKeyHeader = Annotated[str | None, Header(alias="X-API-Key")]


def get_current_auth_context(
    db: DbDep,
    settings: SettingsDep,
    request: Request,
    x_dev_user_email: DevUserEmailHeader = None,
    x_dev_user_name: DevUserNameHeader = None,
    x_dev_user_role: DevUserRoleHeader = None,
    authorization: AuthorizationHeader = None,
    x_api_key: ApiKeyHeader = None,
) -> AuthContext:
    auth_mode = settings.auth_mode.strip().lower()
    try:
        if auth_mode == "dev":
            auth = ensure_dev_identity(
                db,
                email=x_dev_user_email or settings.dev_auth_default_email,
                display_name=x_dev_user_name or settings.dev_auth_default_name,
                role=x_dev_user_role,
            )
        else:
            if x_dev_user_email or x_dev_user_name or x_dev_user_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Development auth headers are disabled outside AUTH_MODE=dev.",
                )
            if auth_mode == "jwt":
                auth = _auth_from_jwt(db, settings, authorization)
            elif auth_mode == "api_key":
                auth = _auth_from_api_key(db, settings, x_api_key)
            elif auth_mode == "oidc":
                auth = _auth_from_oidc(db, settings, authorization)
            else:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="Unsupported AUTH_MODE. Use dev, jwt, api_key, or oidc.",
                )
    except HTTPException as exc:
        _record_authentication_failure(
            db,
            auth_mode=auth_mode,
            status_code=exc.status_code,
            has_bearer_token=bool(authorization and authorization.lower().startswith("bearer ")),
        )
        from app.services import security_policy_service

        security_policy_service.enforce_failed_authentication_rate_limit(
            settings,
            client_ip=request.client.host if request.client is not None else "unknown",
        )
        raise

    bind_tenant_context(db, auth.principal)
    if session_revocation_service.is_current_session_revoked(db, auth):
        _persist_authentication_event(
            db,
            event_type="login_failure",
            authentication_method=auth.principal.authentication_method,
            reason_code="session_revoked",
            workspace_id=auth.workspace_id,
            user_id=auth.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is revoked.",
        )
    from app.services import security_policy_service

    security_policy_service.enforce_authenticated_request_rate_limit(
        db,
        auth,
        settings,
        client_ip=request.client.host if request.client is not None else "unknown",
    )
    _persist_authentication_event(
        db,
        event_type="login_success",
        authentication_method=auth.principal.authentication_method,
        reason_code="identity_verified",
        workspace_id=auth.workspace_id,
        user_id=auth.user_id,
    )
    return auth


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


def require_workspace_owner(auth: AuthContext) -> None:
    if normalized_role(auth.role) == "owner":
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only workspace owners can manage workspace membership.",
    )


def require_workspace_security_admin(auth: AuthContext) -> None:
    if normalized_role(auth.role) in {"owner", "admin"}:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only workspace owners and admins can view security controls.",
    )


def record_cross_tenant_access_attempt(
    db: Session,
    auth: AuthContext,
    *,
    reason_code: str,
    project_id: uuid.UUID | None = None,
) -> None:
    """Persist an attributed, credential-free scope-denial event."""

    _persist_authentication_event(
        db,
        event_type="cross_tenant_access_attempt",
        authentication_method=auth.principal.authentication_method,
        reason_code=reason_code,
        workspace_id=auth.workspace_id,
        user_id=auth.user_id,
        project_id=project_id,
    )


def _record_authentication_failure(
    db: Session,
    *,
    auth_mode: str,
    status_code: int,
    has_bearer_token: bool,
) -> None:
    if auth_mode in {"jwt", "oidc"} and status_code == status.HTTP_401_UNAUTHORIZED:
        event_type = "token_validation_failure" if has_bearer_token else "login_failure"
        reason_code = "token_rejected" if has_bearer_token else "credentials_missing"
    elif auth_mode == "oidc" and status_code == status.HTTP_403_FORBIDDEN:
        event_type = "workspace_access_denied"
        reason_code = "identity_or_membership_denied"
    else:
        event_type = "login_failure"
        reason_code = "identity_rejected"
    _persist_authentication_event(
        db,
        event_type=event_type,
        authentication_method=auth_mode,
        reason_code=reason_code,
    )


def _persist_authentication_event(
    db: Session,
    *,
    event_type: auth_audit_service.AuthenticationEventType,
    authentication_method: auth_audit_service.AuthenticationMethod,
    reason_code: str,
    workspace_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> None:
    try:
        auth_audit_service.record_authentication_event(
            db,
            event_type=event_type,
            authentication_method=authentication_method,
            reason_code=reason_code,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        scope_denial_security_events: dict[str, tuple[str, Literal["medium", "high"], str]] = {
            "project_scope_denied": (
                "cross_project_access_denied",
                "medium",
                "Project access was denied outside the active workspace scope.",
            ),
            "evidence_source_scope_denied": (
                "cross_tenant_source_id_access",
                "high",
                "Evidence source access was denied outside the active workspace scope.",
            ),
        }
        scope_denial_security_event = scope_denial_security_events.get(reason_code)
        if event_type == "cross_tenant_access_attempt" and scope_denial_security_event:
            from app.services import security_event_service

            security_event_type, severity, summary = scope_denial_security_event
            security_event_service.record_security_event(
                db,
                workspace_id=workspace_id,
                project_id=project_id,
                user_id=user_id,
                event_type=security_event_type,
                severity=severity,
                source="auth",
                summary=summary,
                attributes={"reason_code": reason_code},
            )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication audit is unavailable.",
        ) from None


def _auth_from_jwt(
    db: Session,
    settings: Settings,
    authorization: str | None,
) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
        )
    try:
        jwt_secret = resolve_secret(settings, SecretName.AUTH_JWT_SECRET)
    except SecretProviderError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_JWT_SECRET must be configured for AUTH_MODE=jwt.",
        ) from None

    claims = _verify_hs256_jwt(authorization.split(" ", 1)[1], settings, jwt_secret)
    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT sub is required.")

    email = str(claims.get("email") or f"{subject}@jwt.thesys.local")
    role = str(claims.get("role") or "viewer")
    workspace_name = str(claims.get("workspace_name") or "Thesys JWT Workspace")
    display_name = str(claims.get("name") or claims.get("display_name") or email)
    return ensure_external_identity(
        db,
        external_auth_id=f"jwt:{subject}",
        email=email,
        display_name=display_name,
        workspace_name=workspace_name,
        role=role,
        authentication_method="jwt",
        external_subject=subject,
        token_id=str(claims.get("jti") or "") or None,
    )


def _auth_from_api_key(
    db: Session,
    settings: Settings,
    api_key: str | None,
) -> AuthContext:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required.")
    if not settings.auth_api_key_hashes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_API_KEY_HASHES must be configured for AUTH_MODE=api_key.",
        )
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    configured_hashes = {item.casefold() for item in settings.auth_api_key_hashes}
    revoked_hashes = {item.casefold() for item in settings.auth_revoked_api_key_hashes}
    if key_hash.casefold() not in configured_hashes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    if key_hash.casefold() in revoked_hashes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key revoked.")

    return ensure_external_identity(
        db,
        external_auth_id=f"api-key:{key_hash[:16]}",
        email=settings.auth_service_account_email,
        display_name="Thesys Service Account",
        workspace_name=settings.auth_service_account_workspace,
        role=settings.auth_service_account_role,
        authentication_method="api_key",
    )


def _auth_from_oidc(
    db: Session,
    settings: Settings,
    authorization: str | None,
) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
        )
    try:
        claims = verify_oidc_token(authorization.split(" ", 1)[1], settings)
    except OIDCValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC token.",
        ) from exc

    return resolve_oidc_identity(
        db,
        issuer=settings.oidc_issuer or "",
        external_subject=claims.external_subject,
        workspace_id=claims.workspace_id,
        token_role=claims.role,
        session_id=claims.session_id,
        token_id=claims.token_id,
    )


def _verify_hs256_jwt(token: str, settings: Settings, jwt_secret: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT.")

    header = _decode_jwt_json(parts[0])
    claims = _decode_jwt_json(parts[1])
    if header.get("alg") != "HS256":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only HS256 JWTs are supported by the local verifier.",
        )
    allowed_key_ids = {item.strip() for item in settings.auth_jwt_allowed_key_ids}
    if allowed_key_ids and str(header.get("kid") or "") not in allowed_key_ids:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT key not active.")
    revoked_ids = {item.strip() for item in settings.auth_jwt_revoked_ids}
    if str(claims.get("jti") or "") in revoked_ids:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT revoked.")

    signing_input = f"{parts[0]}.{parts[1]}".encode()
    expected = hmac.new(jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        supplied = _decode_base64url(parts[2])
    except Base64DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT.",
        ) from exc
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT.")

    now = int(time.time())
    if "exp" in claims and int(claims["exp"]) < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT expired.")
    if settings.auth_jwt_issuer and claims.get("iss") != settings.auth_jwt_issuer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT issuer.")
    if settings.auth_jwt_audience:
        audience = claims.get("aud")
        valid_audience = (
            settings.auth_jwt_audience in audience
            if isinstance(audience, list)
            else audience == settings.auth_jwt_audience
        )
        if not valid_audience:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid JWT audience.",
            )
    return claims


def _decode_jwt_json(value: str) -> dict:
    try:
        decoded = _decode_base64url(value)
        parsed = json.loads(decoded)
    except (Base64DecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT.",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT.")
    return parsed


def _decode_base64url(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
