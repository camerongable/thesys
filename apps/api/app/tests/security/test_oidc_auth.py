import time
import uuid
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core import oidc
from app.core.auth import get_current_auth_context
from app.core.config import Settings, get_settings
from app.core.oidc import OIDCValidationError, oidc_external_auth_id, verify_oidc_token
from app.db.models import AuthenticationEvent, SessionRevocation, User, Workspace, WorkspaceMember
from app.db.tenant import get_bound_tenant_context
from app.main import create_app

ISSUER = "https://identity.example.com"
AUDIENCE = "thesys-api"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"


@pytest.fixture
def rsa_private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def install_static_jwks(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[rsa.RSAPrivateKey], None]:
    def install(private_key: rsa.RSAPrivateKey) -> None:
        class StaticSigningKey:
            key = private_key.public_key()

        class StaticJWKClient:
            def get_signing_key_from_jwt(self, token: str) -> StaticSigningKey:
                assert token
                return StaticSigningKey()

        monkeypatch.setattr(oidc, "get_jwks_client", lambda *_args: StaticJWKClient())

    return install


def test_identity_configuration_rejects_dev_auth_outside_local() -> None:
    with pytest.raises(ValidationError, match="AUTH_MODE=dev"):
        Settings(environment="production", auth_mode="dev")

    with pytest.raises(ValidationError, match="OIDC_ISSUER"):
        Settings(
            environment="production",
            auth_mode="oidc",
            secret_provider="cloud",
            database_url=(
                "postgresql+psycopg://thesys_api:secret@db.example/thesys?sslmode=verify-full"
            ),
            redis_url="rediss://redis.example:6380/0",
            object_storage_mode="s3",
            s3_endpoint_url="https://s3.example.com",
            s3_verify_bucket_security=True,
            malware_scanner_mode="clamav",
        )

    with pytest.raises(ValidationError, match="approved asymmetric algorithms"):
        Settings(
            environment="production",
            auth_mode="oidc",
            secret_provider="cloud",
            database_url=(
                "postgresql+psycopg://thesys_api:secret@db.example/thesys?sslmode=verify-full"
            ),
            redis_url="rediss://redis.example:6380/0",
            object_storage_mode="s3",
            s3_endpoint_url="https://s3.example.com",
            s3_verify_bucket_security=True,
            malware_scanner_mode="clamav",
            oidc_issuer=ISSUER,
            oidc_audience=AUDIENCE,
            oidc_jwks_url=JWKS_URL,
            oidc_required_algorithms=["HS256"],
        )


def test_application_creation_fails_with_production_dev_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()

    with pytest.raises(ValidationError, match="AUTH_MODE=dev"):
        create_app()


def test_oidc_verifier_accepts_signed_claims_and_preserves_session_identity(
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    workspace_id = uuid.uuid4()
    token = _sign_token(
        rsa_private_key,
        _claims(workspace_id, sid="session-123", jti="token-456"),
    )

    claims = verify_oidc_token(token, _oidc_settings())

    assert claims.external_subject == "user-123"
    assert claims.workspace_id == workspace_id
    assert claims.role == "editor"
    assert claims.session_id == "session-123"
    assert claims.token_id == "token-456"


@pytest.mark.parametrize(
    "claim_overrides",
    [
        {"iss": "https://attacker.example.com"},
        {"aud": "other-api"},
        {"exp": int(time.time()) - 1},
        {"nbf": int(time.time()) + 3600},
    ],
)
def test_oidc_verifier_rejects_invalid_standard_claims(
    claim_overrides: dict[str, Any],
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    claims = _claims(uuid.uuid4())
    claims.update(claim_overrides)
    token = _sign_token(rsa_private_key, claims)

    with pytest.raises(OIDCValidationError, match="validation failed"):
        verify_oidc_token(token, _oidc_settings())


def test_oidc_verifier_does_not_trust_header_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_called = False

    def fail_if_called(*_args: object) -> object:
        nonlocal client_called
        client_called = True
        raise AssertionError("JWKS lookup must not run for a disallowed algorithm.")

    monkeypatch.setattr(oidc, "get_jwks_client", fail_if_called)
    token = jwt.encode(
        _claims(uuid.uuid4()),
        "attacker-secret-at-least-32-bytes",
        algorithm="HS256",
    )

    with pytest.raises(OIDCValidationError, match="algorithm is not allowed"):
        verify_oidc_token(token, _oidc_settings())
    assert client_called is False


def test_oidc_verifier_rejects_invalid_signature(
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _sign_token(attacker_key, _claims(uuid.uuid4()))

    with pytest.raises(OIDCValidationError, match="validation failed"):
        verify_oidc_token(token, _oidc_settings())


@pytest.mark.parametrize(
    "claim_overrides",
    [
        {"workspace_id": "not-a-uuid"},
        {"role": "superadmin"},
        {"sid": ""},
        {"jti": 123},
    ],
)
def test_oidc_verifier_rejects_invalid_identity_claims(
    claim_overrides: dict[str, Any],
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    claims = _claims(uuid.uuid4())
    claims.update(claim_overrides)
    token = _sign_token(rsa_private_key, claims)

    with pytest.raises(OIDCValidationError):
        verify_oidc_token(token, _oidc_settings())


def test_oidc_verifier_requires_valid_authorized_party_for_multiple_audiences(
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    token = _sign_token(
        rsa_private_key,
        _claims(uuid.uuid4(), aud=[AUDIENCE, "profile-api"], azp="thesys-web"),
    )

    with pytest.raises(OIDCValidationError, match="OIDC_AUTHORIZED_PARTY"):
        verify_oidc_token(token, _oidc_settings())

    with pytest.raises(OIDCValidationError, match="authorized party is invalid"):
        verify_oidc_token(token, _oidc_settings(oidc_authorized_party="other-client"))

    settings = _oidc_settings(oidc_authorized_party="thesys-web")
    assert verify_oidc_token(token, settings).external_subject == "user-123"


def test_oidc_auth_resolves_preprovisioned_membership_into_principal(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    user, workspace = _provision_identity(db_session)
    _configure_oidc(monkeypatch)
    token = _sign_token(
        rsa_private_key,
        _claims(workspace.id, sid="session-123", jti="token-456"),
    )

    auth = get_current_auth_context(
        db_session,
        get_settings(),
        Request({"type": "http", "client": ("127.0.0.1", 1234)}),
        authorization=f"Bearer {token}",
    )
    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert auth.user_id == user.id
    assert auth.workspace_id == workspace.id
    assert auth.principal.external_subject == "user-123"
    assert auth.principal.authentication_method == "oidc"
    assert auth.principal.session_id == "session-123"
    assert auth.principal.token_id == "token-456"
    tenant_context = get_bound_tenant_context(db_session)
    assert tenant_context is not None
    assert tenant_context.user_id == user.id
    assert tenant_context.workspace_id == workspace.id


def test_oidc_session_revocation_blocks_reuse_and_records_safe_audit(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    user, workspace = _provision_identity(db_session)
    _configure_oidc(monkeypatch)
    token = _sign_token(
        rsa_private_key,
        _claims(workspace.id, sid="session-to-revoke", jti="token-to-revoke"),
    )
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.get("/api/projects", headers=headers)
    revoked = client.post("/api/session/revoke", headers=headers)
    reused = client.get("/api/projects", headers=headers)

    assert initial.status_code == 200
    assert revoked.status_code == 204
    assert reused.status_code == 401
    revocation = db_session.scalar(select(SessionRevocation))
    assert revocation is not None
    assert revocation.workspace_id == workspace.id
    assert revocation.user_id == user.id
    assert len(revocation.session_identifier_hash) == 64
    assert "session-to-revoke" not in str(revocation.__dict__)
    events = list(db_session.scalars(select(AuthenticationEvent)))
    assert any(
        event.event_type == "session_revoked" and event.reason_code == "self_revocation"
        for event in events
    )
    assert any(
        event.event_type == "login_failure" and event.reason_code == "session_revoked"
        for event in events
    )


def test_oidc_auth_never_provisions_from_token_claims(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    _configure_oidc(monkeypatch)
    token = _sign_token(rsa_private_key, _claims(uuid.uuid4()))

    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert db_session.scalar(select(func.count()).select_from(User)) == 0
    assert db_session.scalar(select(func.count()).select_from(Workspace)) == 0


@pytest.mark.parametrize("account_status,token_role", [("disabled", "editor"), ("active", "owner")])
def test_oidc_auth_rejects_disabled_users_and_stale_roles(
    account_status: str,
    token_role: str,
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    user, workspace = _provision_identity(db_session, status=account_status)
    _configure_oidc(monkeypatch)
    token = _sign_token(rsa_private_key, _claims(workspace.id, role=token_role))

    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    db_session.refresh(user)
    assert user.status == account_status


def test_oidc_auth_rejects_membership_in_a_different_workspace(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: rsa.RSAPrivateKey,
    install_static_jwks: Callable[[rsa.RSAPrivateKey], None],
) -> None:
    install_static_jwks(rsa_private_key)
    _provision_identity(db_session)
    other_workspace = Workspace(name="Workspace B")
    db_session.add(other_workspace)
    db_session.commit()
    _configure_oidc(monkeypatch)
    token = _sign_token(rsa_private_key, _claims(other_workspace.id))

    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_oidc_token_failure_returns_generic_detail_without_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_oidc(monkeypatch)
    token = "not-a-token"

    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid OIDC token."}
    assert token not in response.text


def _oidc_settings(**overrides: object) -> Settings:
    return Settings(
        environment="local",
        auth_mode="oidc",
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_jwks_url=JWKS_URL,
        oidc_required_algorithms=["RS256"],
        **overrides,
    )


def _configure_oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OIDC_JWKS_URL", JWKS_URL)
    monkeypatch.setenv("OIDC_REQUIRED_ALGORITHMS", "RS256")
    get_settings.cache_clear()


def _claims(workspace_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "workspace_id": str(workspace_id),
        "role": "editor",
        "exp": int(time.time()) + 3600,
        "nbf": int(time.time()) - 1,
    }
    claims.update(overrides)
    return claims


def _sign_token(private_key: rsa.RSAPrivateKey, claims: dict[str, Any]) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "active-key"})


def _provision_identity(
    db: Session,
    *,
    status: str = "active",
) -> tuple[User, Workspace]:
    user = User(
        external_auth_id=oidc_external_auth_id(ISSUER, "user-123"),
        email="user@example.com",
        display_name="OIDC User",
        status=status,
    )
    db.add(user)
    db.flush()
    workspace = Workspace(name="Workspace A", created_by=user.id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="editor"))
    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    return user, workspace
