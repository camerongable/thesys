import hashlib
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, cast

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.core.config import Settings

WorkspaceRole = Literal["owner", "admin", "editor", "viewer"]
VALID_WORKSPACE_ROLES: set[str] = {"owner", "admin", "editor", "viewer"}


class OIDCValidationError(ValueError):
    """A token validation failure safe to translate into a generic auth denial."""


@dataclass(frozen=True)
class OIDCClaims:
    external_subject: str
    workspace_id: uuid.UUID
    role: WorkspaceRole
    session_id: str | None
    token_id: str | None


def oidc_external_auth_id(issuer: str, subject: str) -> str:
    identity_hash = hashlib.sha256(f"{issuer}\0{subject}".encode()).hexdigest()
    return f"oidc:{identity_hash}"


def verify_oidc_token(token: str, settings: Settings) -> OIDCClaims:
    algorithms = tuple(settings.oidc_required_algorithms)
    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as exc:
        raise OIDCValidationError("Malformed OIDC token header.") from exc

    algorithm = header.get("alg")
    if not isinstance(algorithm, str) or algorithm not in algorithms:
        raise OIDCValidationError("OIDC token algorithm is not allowed.")

    issuer = _required_setting(settings.oidc_issuer, "OIDC_ISSUER")
    audience = _required_setting(settings.oidc_audience, "OIDC_AUDIENCE")
    jwks_url = _required_setting(settings.oidc_jwks_url, "OIDC_JWKS_URL")
    try:
        signing_key = get_jwks_client(
            jwks_url,
            settings.oidc_jwks_cache_seconds,
            settings.oidc_jwks_timeout_seconds,
        ).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=list(algorithms),
            audience=audience,
            issuer=issuer,
            options={
                "require": ["exp", "iss", "aud", "sub", "workspace_id", "role"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
    except PyJWTError as exc:
        raise OIDCValidationError("OIDC token validation failed.") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise OIDCValidationError("OIDC token subject is invalid.")

    _validate_authorized_party(claims, settings)
    workspace_id = _parse_workspace_id(claims.get("workspace_id"))
    role = claims.get("role")
    if not isinstance(role, str) or role not in VALID_WORKSPACE_ROLES:
        raise OIDCValidationError("OIDC token role is invalid.")

    return OIDCClaims(
        external_subject=subject,
        workspace_id=workspace_id,
        role=cast(WorkspaceRole, role),
        session_id=_optional_identifier(claims, "sid"),
        token_id=_optional_identifier(claims, "jti"),
    )


@lru_cache(maxsize=16)
def get_jwks_client(url: str, cache_seconds: int, timeout_seconds: float) -> PyJWKClient:
    return PyJWKClient(
        url,
        cache_keys=True,
        lifespan=cache_seconds,
        timeout=timeout_seconds,
    )


def _validate_authorized_party(claims: dict, settings: Settings) -> None:
    audience = claims.get("aud")
    multiple_audiences = isinstance(audience, list) and len(audience) > 1
    authorized_party = claims.get("azp")
    expected_party = settings.oidc_authorized_party

    if (multiple_audiences or authorized_party is not None) and not expected_party:
        raise OIDCValidationError(
            "OIDC_AUTHORIZED_PARTY is required when a token identifies an authorized party."
        )
    if expected_party and authorized_party != expected_party:
        raise OIDCValidationError("OIDC token authorized party is invalid.")


def _parse_workspace_id(value: object) -> uuid.UUID:
    if not isinstance(value, str):
        raise OIDCValidationError("OIDC token workspace is invalid.")
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise OIDCValidationError("OIDC token workspace is invalid.") from exc


def _optional_identifier(claims: dict, name: str) -> str | None:
    value = claims.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OIDCValidationError(f"OIDC token {name} is invalid.")
    return value


def _required_setting(value: str | None, name: str) -> str:
    if value and value.strip():
        return value
    raise OIDCValidationError(f"{name} is not configured.")
