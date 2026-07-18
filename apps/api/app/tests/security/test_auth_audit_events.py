from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import auth
from app.core.config import get_settings
from app.db.models import AuthenticationEvent


def test_successful_authentication_records_attributable_login(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.get("/api/me")

    assert response.status_code == 200
    event = db_session.scalar(select(AuthenticationEvent))
    assert event is not None
    assert event.event_type == "login_success"
    assert event.authentication_method == "dev"
    assert event.reason_code == "identity_verified"
    assert event.user_id is not None
    assert event.workspace_id is not None
    assert {column.name for column in AuthenticationEvent.__table__.columns} == {
        "id",
        "workspace_id",
        "user_id",
        "event_type",
        "authentication_method",
        "reason_code",
        "created_at",
    }


def test_invalid_oidc_token_records_credential_free_validation_failure(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_oidc(monkeypatch)
    token = "not-a-token"

    response = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    event = db_session.scalar(select(AuthenticationEvent))
    assert event is not None
    assert event.event_type == "token_validation_failure"
    assert event.authentication_method == "oidc"
    assert event.reason_code == "token_rejected"
    assert event.workspace_id is None
    assert event.user_id is None
    assert token not in str(event.__dict__)


def test_missing_oidc_credentials_records_login_failure(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_oidc(monkeypatch)

    response = client.get("/api/projects")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    event = db_session.scalar(select(AuthenticationEvent))
    assert event is not None
    assert event.event_type == "login_failure"
    assert event.authentication_method == "oidc"
    assert event.reason_code == "credentials_missing"
    assert event.workspace_id is None
    assert event.user_id is None


def test_session_revocation_requires_a_session_identifier(client: TestClient) -> None:
    response = client.post("/api/session/revoke")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"detail": "The authenticated session cannot be revoked."}


def test_oidc_identity_denial_records_workspace_access_denied(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_oidc(monkeypatch)
    monkeypatch.setattr(
        auth,
        "verify_oidc_token",
        lambda *_args: SimpleNamespace(
            external_subject="user-123",
            workspace_id=None,
            role="viewer",
            session_id=None,
            token_id=None,
        ),
    )

    def reject_identity(_db, **_kwargs):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OIDC identity is not a member of the requested workspace.",
        )

    monkeypatch.setattr(auth, "resolve_oidc_identity", reject_identity)
    response = client.get("/api/projects", headers={"Authorization": "Bearer signed-token"})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    event = db_session.scalar(select(AuthenticationEvent))
    assert event is not None
    assert event.event_type == "workspace_access_denied"
    assert event.authentication_method == "oidc"
    assert event.reason_code == "identity_or_membership_denied"
    assert event.workspace_id is None
    assert event.user_id is None


def _configure_oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.com")
    monkeypatch.setenv("OIDC_AUDIENCE", "thesys-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://identity.example.com/.well-known/jwks.json")
    monkeypatch.setenv("OIDC_REQUIRED_ALGORITHMS", "RS256")
    get_settings.cache_clear()
