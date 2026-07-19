"""Cryptographic verification for credentials sent to reviewed remote MCP servers."""

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

    expected_issuer = issuer.rstrip("/")
    discovery = _fetch_json(
        _issuer_metadata_url(expected_issuer),
        settings.mcp_remote_review_timeout_seconds,
    )
    if discovery.get("issuer") != expected_issuer:
        raise RemoteMcpTokenValidationError("token_issuer_metadata_mismatch")
    jwks_url = _trusted_jwks_url(discovery.get("jwks_uri"), expected_issuer)
    jwks = _fetch_json(jwks_url, settings.mcp_remote_review_timeout_seconds)
    signing_key = _signing_key(jwks, key_id)
    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience=audience,
            issuer=expected_issuer,
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


def _trusted_jwks_url(value: Any, issuer: str) -> str:
    if not isinstance(value, str):
        raise RemoteMcpTokenValidationError("token_jwks_url_invalid")
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
        raise RemoteMcpTokenValidationError("token_jwks_url_invalid")
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
