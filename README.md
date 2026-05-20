# Thesys

This repository contains the local development foundation for Thesys: an
AI-native workspace for turning rough business ideas into
structured, evidence-backed strategic projects.

The implementation follows `IMPLEMENTATION_BRIEF.md`. Sprint 0 focuses on the
monorepo, local infrastructure, API/web skeletons, database migration plumbing,
and healthchecks.

## Repository Layout

```text
apps/
  api/        FastAPI backend, SQLAlchemy, Alembic
  web/        Next.js App Router frontend
infra/
  litellm/    LiteLLM local proxy config
  postgres/   Postgres initialization scripts
docs/         Architecture, API, data model, eval, and security notes
```

## Prerequisites

- Docker Desktop with Docker Compose v2
- Node.js 20+
- pnpm 10+
- Python 3.11+

## Local Setup

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Start the local stack:

   ```bash
   docker compose up --build
   ```

   If Docker build can reach Docker Hub but resets connections to
   `registry.npmjs.org`, override the package registry for the web image:

   ```bash
   NPM_REGISTRY=https://registry.npmmirror.com/ docker compose up --build
   ```

3. Open the services:

   - Web: http://localhost:3000
   - API healthcheck: http://localhost:8000/health
   - MinIO console: http://localhost:9001
   - LiteLLM proxy: http://localhost:4000

The API container runs Alembic migrations on startup. The initial migration
enables the `pgvector` extension, and Sprint 1 adds local dev auth,
workspaces, projects, and thesis tables.

## Local Auth

Sprint 1 uses `AUTH_MODE=dev`. The backend auto-provisions a local user and
workspace from these headers:

```text
X-Dev-User-Email
X-Dev-User-Name
```

If those headers are omitted, the defaults from `.env.example` are used.

## Local Development Without Docker

API:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Web:

```bash
cd apps/web
pnpm install
pnpm run dev
```

## Sprint 0 Acceptance Checks

```bash
docker compose config
cd apps/api && pytest
cd apps/web && pnpm install && pnpm run typecheck
```

## Sprint 1 Manual Checks

```bash
curl http://localhost:8000/api/me
curl http://localhost:8000/api/projects
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo project","short_description":"Initial project state"}'
```

Then open http://localhost:3000/projects and create a project through the UI.
