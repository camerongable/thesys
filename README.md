# Thesys

This repository contains the local development foundation for Thesys: an
AI-native workspace for turning rough business ideas into
structured, evidence-backed strategic projects.

The implementation follows `IMPLEMENTATION_BRIEF.md`. Sprints 0-10 establish the
monorepo, local infrastructure, project workspace foundation, AI gateway
infrastructure, structured intake, evidence/RAG, cited briefs, competitors,
assumptions, validation plans, decisions, demo seeding, MVP eval checks, and
workflow trace UI, live LLM demo readiness, and a guided strategic overview
that makes the next validation step explicit.

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

## Sprint 9 Local Open-Weight Demo

Sprint 9 keeps deterministic hash embeddings for retrieval, but allows the MVP
generation workflows to run against a live local model through LiteLLM and
Ollama. This avoids per-token OpenAI API billing during development.

1. Install Ollama and pull the recommended dev model:

   ```bash
   ollama pull qwen2.5:3b
   ```

   Larger variants such as `qwen2.5:7b` and `qwen2.5:14b` are more capable, but
   `qwen2.5:3b` is the better default for responsive local development.

2. Set local open-weight values in `.env`:

   ```bash
   LLM_STUB_MODE=never
   LITELLM_MODEL=dev-local-qwen
   LITELLM_TIMEOUT_SECONDS=180
   LITELLM_API_KEY=sk-local-dev
   LITELLM_MASTER_KEY=sk-local-dev
   LLM_STRUCTURED_OUTPUT_REPAIR_ATTEMPTS=1
   LLM_FALLBACK_POLICY=emergency
   OLLAMA_API_BASE=http://host.docker.internal:11434
   ```

   Structured-output validation remains strict. `LLM_STRUCTURED_OUTPUT_REPAIR_ATTEMPTS`
   controls how many times the configured model can repair invalid JSON before
   the workflow fails or falls back. `LLM_FALLBACK_POLICY` accepts `disabled`,
   `emergency`, or `always`; use `emergency` for live demos so LiteLLM is tried
   first and deterministic fallback is only used after model/validation failure.

3. Restart LiteLLM and the API:

   ```bash
   docker compose restart litellm api
   ```

4. Check the configured AI mode:

   ```bash
   curl http://localhost:8000/api/ai/status
   ```

   The web UI also shows an AI mode badge on project pages. It reports
   `Stub mode` or `Live LLM`, the configured model, and LiteLLM reachability.

5. Run the structured-output smoke test:

   ```bash
   curl -X POST http://localhost:8000/api/ai/test-structured-output \
     -H "Content-Type: application/json" \
     -d '{"idea":"AI workspace for independent fitness coaches"}'
   ```

   In live mode, confirm:

   ```json
   {
     "used_stub": false,
     "model_provider": "litellm"
   }
   ```

6. In the web UI, create or open a project and run the MVP AI actions:

   - Analyze Idea
   - Generate Brief
   - Analyze Competitors
   - Extract Assumptions
   - Generate Plans

Workflow traces show provider/model metadata, step status, token counts, and
cost when LiteLLM returns it. If the provider fails, the API returns an
actionable error and the failed workflow step stores the provider error.

To test against OpenAI later, set `LITELLM_MODEL=dev-gpt-4o-mini` and provide
`OPENAI_API_KEY` in `.env`. To test against Gemini through Google AI Studio,
set `LITELLM_MODEL=dev-gemini-3.5-flash` and provide `GEMINI_API_KEY`.

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

## Sprint 10 Guided Overview

Project pages now open on a founder-facing command center. The Overview tab
shows:

- current lifecycle stage
- current recommendation and rationale
- one primary next best action
- idea readiness instead of developer-facing MVP checks
- strategic snapshot
- evidence health
- recent strategic updates
- key assumptions and risks

The supporting API endpoints are:

```bash
curl http://localhost:8000/api/projects/<project_id>/overview
curl http://localhost:8000/api/projects/<project_id>/readiness
curl http://localhost:8000/api/projects/<project_id>/strategic-updates
curl -X POST http://localhost:8000/api/projects/<project_id>/next-action
```

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
