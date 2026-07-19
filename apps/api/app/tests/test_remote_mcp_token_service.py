import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr

from app.core.config import Settings
from app.services import remote_mcp_token_service


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _Client:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses = responses
        self.requests: list[tuple[str, dict[str, object]]] = []

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def get(self, url: str, **kwargs: object) -> _Response:
        self.requests.append((url, kwargs))
        return self._responses.pop(0)


def test_validates_signed_remote_access_token_against_issuer_audience_and_scopes(
    monkeypatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    issuer = "https://issuer.example.test"
    token = _token(
        private_key,
        issuer=issuer,
        audience="https://mcp.example.test",
        scope="mcp.tools.read",
        issued_at=now,
    )
    client = _Client(
        [
            _Response(
                {
                    "issuer": issuer,
                    "jwks_uri": f"{issuer}/.well-known/jwks.json",
                }
            ),
            _Response({"keys": [_public_jwk(private_key)]}),
        ]
    )
    monkeypatch.setattr(remote_mcp_token_service.httpx, "Client", lambda **_kwargs: client)

    remote_mcp_token_service.validate_access_token(
        Settings(),
        access_token=SecretStr(token),
        issuer=issuer,
        audience="https://mcp.example.test",
        required_scopes=("mcp.tools.read",),
    )

    assert [request[0] for request in client.requests] == [
        f"{issuer}/.well-known/openid-configuration",
        f"{issuer}/.well-known/jwks.json",
    ]


@pytest.mark.parametrize(
    ("audience", "scope", "expected_reason"),
    [
        ("https://other.example.test", "mcp.tools.read", "token_claim_validation_failed"),
        ("https://mcp.example.test", "mcp.tools.write", "token_scope_mismatch"),
    ],
)
def test_rejects_remote_access_token_with_wrong_claims(
    monkeypatch,
    audience: str,
    scope: str,
    expected_reason: str,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer = "https://issuer.example.test"
    token = _token(
        private_key,
        issuer=issuer,
        audience=audience,
        scope=scope,
        issued_at=datetime.now(UTC),
    )
    client = _Client(
        [
            _Response(
                {
                    "issuer": issuer,
                    "jwks_uri": f"{issuer}/.well-known/jwks.json",
                }
            ),
            _Response({"keys": [_public_jwk(private_key)]}),
        ]
    )
    monkeypatch.setattr(remote_mcp_token_service.httpx, "Client", lambda **_kwargs: client)

    with pytest.raises(remote_mcp_token_service.RemoteMcpTokenValidationError) as exc_info:
        remote_mcp_token_service.validate_access_token(
            Settings(),
            access_token=SecretStr(token),
            issuer=issuer,
            audience="https://mcp.example.test",
            required_scopes=("mcp.tools.read",),
        )

    assert exc_info.value.reason_code == expected_reason


def test_rejects_symmetric_or_untrusted_jwks_remote_access_tokens(monkeypatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer = "https://issuer.example.test"
    token = jwt.encode(
        {"sub": "user", "iss": issuer, "aud": "https://mcp.example.test"},
        "not-allowed-not-allowed-not-allowed-not-allowed",
        algorithm="HS256",
        headers={"kid": "key-1"},
    )

    with pytest.raises(remote_mcp_token_service.RemoteMcpTokenValidationError) as exc_info:
        remote_mcp_token_service.validate_access_token(
            Settings(),
            access_token=SecretStr(token),
            issuer=issuer,
            audience="https://mcp.example.test",
            required_scopes=("mcp.tools.read",),
        )

    assert exc_info.value.reason_code == "token_algorithm_or_key_rejected"
    discovery_client = _Client(
        [
            _Response(
                {"issuer": issuer, "jwks_uri": "https://untrusted.example.test/jwks.json"}
            )
        ]
    )
    monkeypatch.setattr(
        remote_mcp_token_service.httpx,
        "Client",
        lambda **_kwargs: discovery_client,
    )
    signed_token = _token(
        private_key,
        issuer=issuer,
        audience="https://mcp.example.test",
        scope="mcp.tools.read",
        issued_at=datetime.now(UTC),
    )

    with pytest.raises(remote_mcp_token_service.RemoteMcpTokenValidationError) as jwks_exc:
        remote_mcp_token_service.validate_access_token(
            Settings(),
            access_token=SecretStr(signed_token),
            issuer=issuer,
            audience="https://mcp.example.test",
            required_scopes=("mcp.tools.read",),
        )

    assert jwks_exc.value.reason_code == "token_jwks_url_invalid"


@pytest.mark.parametrize(
    ("token_issuer", "lifetime", "expected_reason"),
    [
        (
            "https://other-issuer.example.test",
            timedelta(minutes=30),
            "token_claim_validation_failed",
        ),
        ("https://issuer.example.test", timedelta(hours=2), "token_lifetime_invalid"),
    ],
)
def test_rejects_remote_access_tokens_with_wrong_issuer_or_excessive_lifetime(
    monkeypatch,
    token_issuer: str,
    lifetime: timedelta,
    expected_reason: str,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer = "https://issuer.example.test"
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "delegated-user",
            "iss": token_issuer,
            "aud": "https://mcp.example.test",
            "scope": "mcp.tools.read",
            "iat": int(now.timestamp()),
            "exp": int((now + lifetime).timestamp()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )
    client = _Client(
        [
            _Response(
                {
                    "issuer": issuer,
                    "jwks_uri": f"{issuer}/.well-known/jwks.json",
                }
            ),
            _Response({"keys": [_public_jwk(private_key)]}),
        ]
    )
    monkeypatch.setattr(remote_mcp_token_service.httpx, "Client", lambda **_kwargs: client)

    with pytest.raises(remote_mcp_token_service.RemoteMcpTokenValidationError) as exc_info:
        remote_mcp_token_service.validate_access_token(
            Settings(),
            access_token=SecretStr(token),
            issuer=issuer,
            audience="https://mcp.example.test",
            required_scopes=("mcp.tools.read",),
        )

    assert exc_info.value.reason_code == expected_reason


def _token(
    private_key,
    *,
    issuer: str,
    audience: str,
    scope: str,
    issued_at: datetime,
) -> str:
    return jwt.encode(
        {
            "sub": "delegated-user",
            "iss": issuer,
            "aud": audience,
            "scope": scope,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + timedelta(minutes=30)).timestamp()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )


def _public_jwk(private_key) -> dict[str, object]:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = "key-1"
    jwk["use"] = "sig"
    return jwk
