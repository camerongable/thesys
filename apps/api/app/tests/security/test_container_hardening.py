from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_api_container_uses_an_immutable_base_and_locked_dependencies() -> None:
    dockerfile = (REPO_ROOT / "apps" / "api" / "Dockerfile").read_text()

    assert dockerfile.count("FROM python:3.12.13-slim-trixie@sha256:") == 2
    assert "COPY apps/api/pyproject.toml apps/api/uv.lock ./" in dockerfile
    assert "uv sync --locked --no-dev --no-install-project" in dockerfile
    assert "uv sync --locked --no-dev" in dockerfile
    assert "USER thesys" in dockerfile
    assert "pip install --no-cache-dir -e ." not in dockerfile


def test_web_container_has_separate_development_and_non_root_runtime_stages() -> None:
    dockerfile = (REPO_ROOT / "apps" / "web" / "Dockerfile").read_text()

    assert dockerfile.count("FROM node:24.17.0-alpine3.23@sha256:") == 2
    assert "RUN corepack enable" in dockerfile
    assert "pnpm install" in dockerfile
    assert "--frozen-lockfile" in dockerfile
    assert "RUN pnpm --filter thesys-web build" in dockerfile
    assert "FROM build AS development" in dockerfile
    assert "FROM node:24.17.0-alpine3.23@sha256:" in dockerfile
    assert "USER thesys" in dockerfile
    assert 'CMD ["pnpm", "run", "start", "--hostname", "0.0.0.0"]' in dockerfile


def test_compose_explicitly_selects_development_targets() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text()

    assert compose.count("target: development") == 3
