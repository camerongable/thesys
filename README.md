# Thesys

This repository contains the local development foundation for Thesys: an
AI-native workspace for turning rough business ideas into
structured, evidence-backed strategic projects.

The implementation follows `IMPLEMENTATION_BRIEF.md`. Sprints 0-8 establish the
monorepo, local infrastructure, project workspace foundation, AI gateway
infrastructure, structured intake, evidence/RAG, cited briefs, competitors,
assumptions, validation plans, decisions, demo seeding, MVP eval checks, and
workflow trace UI.

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

The API container runs Alembic migrations on startup. The local stack defaults
to deterministic LLM stubs so the demo remains runnable without paid model
access.

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

## Sprint 2 Manual Check

By default, local Docker AI calls use the deterministic dev stub. This keeps
the app demoable without paid model access and avoids accidentally using
provider keys exported in your shell.

```bash
curl -X POST http://localhost:8000/api/ai/test-structured-output \
  -H "Content-Type: application/json" \
  -d '{"idea":"AI workspace for independent fitness coaches"}'
```

Set `LLM_STUB_MODE=never` and provide a real provider key in `.env` to force
calls through LiteLLM. Docker forwards those keys into both the API and LiteLLM
containers.

## Sprint 4 Manual Checks

Add a note source:

```bash
curl -X POST http://localhost:8000/api/projects/<project_id>/evidence/note \
  -H "Content-Type: application/json" \
  -d '{"title":"Interview notes","text":"Coaches spend hours reviewing weekly check-ins."}'
```

Retrieve evidence:

```bash
curl -X POST http://localhost:8000/api/projects/<project_id>/evidence/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"weekly coach check-ins","mode":"hybrid","top_k":5}'
```

The project page now includes an Evidence tab for URL, note, and file ingestion,
source listing, and hybrid/semantic/keyword retrieval.

## Sprint 8 Demo Script

Start the stack:

```bash
docker compose up --build
```

Seed the demo project:

```bash
curl -X POST http://localhost:8000/api/demo/seed
```

Open http://localhost:3000/projects, or open the `next_url` returned by the
seed response. The demo project includes:

- structured project thesis, segments, and problems
- three evidence notes with chunks and embeddings
- a cited opportunity brief
- competitor profiles and a competitor landscape artifact
- assumptions and risks
- validation plan artifact
- logged experiment result
- linked decision record
- workflow traces and MVP readiness checks

Run the MVP readiness eval:

```bash
curl http://localhost:8000/api/projects/<project_id>/evals/mvp
```

Inspect workflow traces:

```bash
curl http://localhost:8000/api/projects/<project_id>/workflows
curl http://localhost:8000/api/workflows/<run_id>
curl -N http://localhost:8000/api/workflows/<run_id>/events
```
