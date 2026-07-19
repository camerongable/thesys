"""OAuth acquisition and cryptographic verification for remote MCP credentials."""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
from jwt.exceptions import PyJWTError
from pydantic import SecretStr

from app.core.config import Settings

ALLOWED_TOKEN_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}
MAX_ACCESS_TOKEN_LIFETIME = timedelta(hours=1)


@dataclass(frozen=True)
class RemoteMcpOAuthMetadata:
    issuer: str
    jwks_url: str
    token_endpoint: str | None


class RemoteMcpTokenValidationError(ValueError):
    """A credential could not be safely presented to a reviewed MCP server."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def validate_access_token(
    settings: Settings,
    *,
    access_token: SecretStr,
    issuer: str,
    audience: str,
    required_scopes: tuple[str, ...],
    require_subject: bool = True,
) -> None:
    """Verify the exact issuer, audience, and least-privilege scope before egress."""
    token = access_token.get_secret_value()
    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as exc:
        raise RemoteMcpTokenValidationError("token_malformed") from exc
    algorithm = header.get("alg")
    key_id = header.get("kid")
    if algorithm not in ALLOWED_TOKEN_ALGORITHMS or not isinstance(key_id, str) or not key_id:
        raise RemoteMcpTokenValidationError("token_algorithm_or_key_rejected")

    metadata = discover_oauth_metadata(settings, issuer=issuer)
    jwks = _fetch_json(metadata.jwks_url, settings.mcp_remote_review_timeout_seconds)
    signing_key = _signing_key(jwks, key_id)
    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience=audience,
            issuer=metadata.issuer,
            options={
                "require": ["exp", "iat", "iss", "aud"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
    except PyJWTError as exc:
        raise RemoteMcpTokenValidationError("token_claim_validation_failed") from exc
    if require_subject and not isinstance(claims.get("sub"), str):
        raise RemoteMcpTokenValidationError("token_subject_invalid")
    _validate_short_lived(claims)
    _validate_scopes(claims, required_scopes)


def request_client_credentials_access_token(
    settings: Settings,
    *,
    issuer: str,
    audience: str,
    scopes: tuple[str, ...],
    client_id: str,
    client_secret: SecretStr,
) -> SecretStr:
    """Exchange a single server-scoped client credential for a validated JWT."""
    metadata = discover_oauth_metadata(settings, issuer=issuer, require_token_endpoint=True)
    if metadata.token_endpoint is None:
        raise RemoteMcpTokenValidationError("token_endpoint_unavailable")
    basic_value = base64.b64encode(
        f"{client_id}:{client_secret.get_secret_value()}".encode()
    ).decode("ascii")
    try:
        with httpx.Client(
            timeout=settings.mcp_remote_review_timeout_seconds,
            follow_redirects=False,
            verify=True,
        ) as client:
            response = client.post(
                metadata.token_endpoint,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Basic {basic_value}",
                },
                data={
                    "grant_type": "client_credentials",
                    "audience": audience,
                    "scope": " ".join(scopes),
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RemoteMcpTokenValidationError("client_credentials_exchange_unavailable") from exc
    access_token = _validated_token_response(payload)
    validate_access_token(
        settings,
        access_token=access_token,
        issuer=metadata.issuer,
        audience=audience,
        required_scopes=scopes,
        require_subject=False,
    )
    return access_token


def discover_oauth_metadata(
    settings: Settings,
    *,
    issuer: str,
    require_token_endpoint: bool = False,
) -> RemoteMcpOAuthMetadata:
    """Discover metadata without allowing an issuer to redirect credential egress."""
    expected_issuer = issuer.rstrip("/")
    discovery = _fetch_json(
        _issuer_metadata_url(expected_issuer),
        settings.mcp_remote_review_timeout_seconds,
    )
    if discovery.get("issuer") != expected_issuer:
        raise RemoteMcpTokenValidationError("token_issuer_metadata_mismatch")
    token_endpoint = discovery.get("token_endpoint")
    if token_endpoint is not None:
        token_endpoint = _trusted_issuer_endpoint(
            token_endpoint,
            expected_issuer,
            "token_endpoint",
        )
    elif require_token_endpoint:
        raise RemoteMcpTokenValidationError("token_endpoint_unavailable")
    return RemoteMcpOAuthMetadata(
        issuer=expected_issuer,
        jwks_url=_trusted_issuer_endpoint(discovery.get("jwks_uri"), expected_issuer, "jwks"),
        token_endpoint=token_endpoint,
    )


def _issuer_metadata_url(issuer: str) -> str:
    parsed = urlparse(issuer)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
    ):
        raise RemoteMcpTokenValidationError("token_issuer_invalid")
    return f"{issuer}/.well-known/openid-configuration"


def _trusted_issuer_endpoint(value: Any, issuer: str, endpoint_type: str) -> str:
    if not isinstance(value, str):
        raise RemoteMcpTokenValidationError(f"token_{endpoint_type}_url_invalid")
    issuer_url = urlparse(issuer)
    jwks_url = urlparse(value)
    if (
        jwks_url.scheme != "https"
        or not jwks_url.hostname
        or jwks_url.username is not None
        or jwks_url.password is not None
        or jwks_url.port not in {None, 443}
        or jwks_url.hostname.casefold() != issuer_url.hostname.casefold()
    ):
        raise RemoteMcpTokenValidationError(f"token_{endpoint_type}_url_invalid")
    return value


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False, verify=True) as client:
            response = client.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RemoteMcpTokenValidationError("token_discovery_unavailable") from exc
    if not isinstance(payload, dict):
        raise RemoteMcpTokenValidationError("token_discovery_invalid")
    return payload


def _signing_key(jwks: dict[str, Any], key_id: str) -> jwt.PyJWK:
    try:
        matching_keys = [key for key in jwt.PyJWKSet.from_dict(jwks).keys if key.key_id == key_id]
    except (PyJWTError, ValueError, TypeError) as exc:
        raise RemoteMcpTokenValidationError("token_jwks_invalid") from exc
    if len(matching_keys) != 1:
        raise RemoteMcpTokenValidationError("token_key_not_found")
    return matching_keys[0]


def _validated_token_response(payload: Any) -> SecretStr:
    if not isinstance(payload, dict):
        raise RemoteMcpTokenValidationError("client_credentials_response_invalid")
    access_token = payload.get("access_token")
    token_type = payload.get("token_type")
    expires_in = payload.get("expires_in")
    if (
        not isinstance(access_token, str)
        or not access_token
        or len(access_token) > 8192
        or not isinstance(token_type, str)
        or token_type.casefold() != "bearer"
        or not isinstance(expires_in, int)
        or isinstance(expires_in, bool)
        or expires_in <= 0
        or expires_in > int(MAX_ACCESS_TOKEN_LIFETIME.total_seconds())
    ):
        raise RemoteMcpTokenValidationError("client_credentials_response_invalid")
    return SecretStr(access_token)


def _validate_short_lived(claims: dict[str, Any]) -> None:
    issued_at = claims.get("iat")
    expires_at = claims.get("exp")
    if (
        not isinstance(issued_at, int | float)
        or isinstance(issued_at, bool)
        or not isinstance(expires_at, int | float)
        or isinstance(expires_at, bool)
    ):
        raise RemoteMcpTokenValidationError("token_lifetime_invalid")
    lifetime = timedelta(seconds=expires_at - issued_at)
    if lifetime <= timedelta() or lifetime > MAX_ACCESS_TOKEN_LIFETIME:
        raise RemoteMcpTokenValidationError("token_lifetime_invalid")
    if datetime.fromtimestamp(expires_at, UTC) <= datetime.now(UTC):
        raise RemoteMcpTokenValidationError("token_expired")


def _validate_scopes(claims: dict[str, Any], required_scopes: tuple[str, ...]) -> None:
    raw_scopes = claims.get("scope", claims.get("scp"))
    if isinstance(raw_scopes, str):
        token_scopes = tuple(scope for scope in raw_scopes.split(" ") if scope)
    elif isinstance(raw_scopes, list) and all(
        isinstance(scope, str) and scope for scope in raw_scopes
    ):
        token_scopes = tuple(raw_scopes)
    else:
        raise RemoteMcpTokenValidationError("token_scope_invalid")
    if set(token_scopes) != set(required_scopes) or len(token_scopes) != len(set(token_scopes)):
        raise RemoteMcpTokenValidationError("token_scope_mismatch")
