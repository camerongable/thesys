import base64
import hashlib
import hmac
import json
import time
import uuid
from binascii import Error as Base64DecodeError
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.oidc import OIDCValidationError, verify_oidc_token
from app.db.models import User, Workspace
from app.db.session import get_db
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
    x_dev_user_email: DevUserEmailHeader = None,
    x_dev_user_name: DevUserNameHeader = None,
    x_dev_user_role: DevUserRoleHeader = None,
    authorization: AuthorizationHeader = None,
    x_api_key: ApiKeyHeader = None,
) -> AuthContext:
    auth_mode = settings.auth_mode.strip().lower()
    if auth_mode == "dev":
        return ensure_dev_identity(
            db,
            email=x_dev_user_email or settings.dev_auth_default_email,
            display_name=x_dev_user_name or settings.dev_auth_default_name,
            role=x_dev_user_role,
        )

    if x_dev_user_email or x_dev_user_name or x_dev_user_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Development auth headers are disabled outside AUTH_MODE=dev.",
        )
    if auth_mode == "jwt":
        return _auth_from_jwt(db, settings, authorization)
    if auth_mode == "api_key":
        return _auth_from_api_key(db, settings, x_api_key)
    if auth_mode == "oidc":
        return _auth_from_oidc(db, settings, authorization)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Unsupported AUTH_MODE. Use dev, jwt, api_key, or oidc.",
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
    if not settings.auth_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_JWT_SECRET must be configured for AUTH_MODE=jwt.",
        )

    claims = _verify_hs256_jwt(authorization.split(" ", 1)[1], settings)
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


def _verify_hs256_jwt(token: str, settings: Settings) -> dict:
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
    expected = hmac.new(
        settings.auth_jwt_secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
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
