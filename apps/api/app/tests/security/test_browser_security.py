from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_api_responses_have_strict_browser_security_headers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == (
        "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    )
    assert response.headers["x-frame-options"] == "DENY"
    assert "strict-transport-security" not in response.headers


def test_cors_does_not_enable_browser_credentials(client: TestClient) -> None:
    response = client.options(
        "/api/projects",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in response.headers


def test_production_api_responses_include_hsts(monkeypatch) -> None:
    settings = Settings(
        environment="production",
        auth_mode="api_key",
        secret_provider="cloud",
        database_url="postgresql+psycopg://thesys_api:secret@db.example/thesys",
        object_storage_mode="s3",
        s3_endpoint_url="https://s3.example.com",
        s3_verify_bucket_security=True,
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert response.headers["content-security-policy"].endswith("frame-ancestors 'none'")
