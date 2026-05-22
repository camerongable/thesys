# Implementation Status

## Current Phase

Sprint 8 complete. MVP demo flow is ready for local validation.

## Sprint 0 Scope

- [x] Create monorepo structure.
- [x] Add Docker Compose services for web, API, Postgres + pgvector, Redis,
  MinIO, and LiteLLM.
- [x] Add `.env.example`.
- [x] Scaffold FastAPI app.
- [x] Scaffold Next.js app.
- [x] Add Alembic.
- [x] Add base SQLAlchemy model infrastructure.
- [x] Add healthcheck endpoints.
- [x] Add README local setup instructions.

## Sprint 0 Verification

Checks run:

- [x] `docker compose config`
- [x] `cd apps/api && pytest`
- [x] `cd apps/api && alembic upgrade head --sql`
- [x] `cd apps/api && ruff check apps/api`
- [x] `cd apps/web && node -e "JSON.parse(...)"`
- [x] `pnpm install && pnpm --filter thesys-web typecheck`

## Sprint 1 Scope

- [x] Add dev auth boundary and identity context.
- [x] Add users, workspaces, workspace members, projects, and project theses.
- [x] Add Alembic migrations for Sprint 1 tables.
- [x] Implement workspace-scoped project CRUD API.
- [x] Build project list UI.
- [x] Build project creation UI.
- [x] Build project overview page with empty states.

## Sprint 1 Verification

Checks run:

- [x] `cd apps/api && ruff check apps/api`
- [x] `cd apps/api && pytest`
- [x] `cd apps/api && alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`

## Sprint 2 Scope

- [x] Add LiteLLM client for the OpenAI-compatible proxy endpoint.
- [x] Add deterministic local LLM stub mode.
- [x] Add AI run and step SQLAlchemy models.
- [x] Add Alembic migration for `ai_runs` and `ai_steps`.
- [x] Add structured-output helper using Pydantic schemas.
- [x] Add prompt versioning convention.
- [x] Add token/cost logging fields.
- [x] Add structured-output smoke-test API endpoint.

## Sprint 2 Verification

Checks run:

- [x] `apps/api/.venv/bin/ruff check apps/api`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/api && uv lock`
- [x] `docker compose config`
- [x] `pnpm --filter thesys-web typecheck`

## Sprint 3 Scope

- [x] Implement structured intake Pydantic schema.
- [x] Add LangGraph-backed structured intake generation workflow.
- [x] Add `/intake/analyze`, `/intake/answer`, and `/intake/finalize`.
- [x] Store structured intake records, first thesis version, customer segments, and problems.
- [x] Build frontend intake wizard on the project overview page.
- [x] Keep intake workflow executions visible in `ai_runs` and `ai_steps`.

## Sprint 3 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

## Sprint 4 Scope

- [x] Implement evidence source and chunk tables.
- [x] Add URL ingestion.
- [x] Add manual note ingestion.
- [x] Add PDF/text/Markdown upload.
- [x] Add object storage integration with MinIO/S3 mode and local fallback.
- [x] Add parser/chunker and deterministic dev-safe embedding generation.
- [x] Store embeddings in pgvector-backed `evidence_chunks`.
- [x] Implement project-scoped semantic, keyword, and hybrid retrieval.
- [x] Add metadata filters for source type, freshness, competitor ID, and assumption ID.
- [x] Return retrieval results with source IDs, chunk IDs, scores, and metadata.
- [x] Trace ingestion and retrieval through `ai_runs` and `ai_steps`.
- [x] Build the Evidence tab with URL, note, upload, source list, and retrieval UI.

## Sprint 4 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

Original Sprint 5 plan:

- Implement opportunity brief workflow.
- Retrieve relevant evidence before generation.
- Generate structured opportunity brief and markdown artifact.
- Run citation audit.
- Store claims, unsupported assumptions, artifact, and artifact version.
- Display brief with citations.
- Extract assumptions and risks from brief.

## Sprint 5 Scope

- [x] Add artifact and artifact version persistence.
- [x] Add cited claims and claim-to-evidence links.
- [x] Add assumptions and risks produced by the opportunity brief.
- [x] Implement project-scoped opportunity brief generation.
- [x] Retrieve project evidence before generation.
- [x] Generate structured opportunity brief output and markdown artifact content.
- [x] Run citation audit before saving supported claims.
- [x] Save unsupported claims separately in structured artifact content.
- [x] Add artifact API routes and opportunity brief generation endpoint.
- [x] Build the Brief tab with generation, cited claims, unsupported claims, and versions.

## Sprint 5 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

Original Sprint 6 plan:

- Add competitor tables.
- Add manual competitor URL input.
- Implement competitor source ingestion.
- Implement competitor profile extraction.
- Implement competitor clustering.
- Generate competitor landscape artifact.
- Build Competitors tab.

## Sprint 6 Scope

- [x] Add `competitors` and `competitor_evidence_links` tables.
- [x] Add Alembic migration for competitor analysis records.
- [x] Add competitor CRUD API endpoints.
- [x] Add competitor analysis endpoint.
- [x] Ingest user-seeded competitor URLs through the evidence pipeline.
- [x] Attach `competitor_id` metadata to linked evidence chunks.
- [x] Generate structured competitor profiles, clusters, positioning gaps, and wedge notes.
- [x] Save the competitor landscape as a versioned artifact.
- [x] Preserve cited claims and unsupported claims.
- [x] Build the Competitors tab with URL entry, profile list, analysis action, and artifact display.

## Sprint 6 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

Original Sprint 7 plan:

- Build Assumptions tab.
- Build Risks display.
- Implement validation plan generation.
- Build Experiments tab.
- Add manual result logging.
- Update assumption confidence based on results.
- Build Decisions tab.
- Allow decision records linked to assumptions, evidence, artifacts, and experiments.

## Sprint 7 Scope

- [x] Add `experiments`, `experiment_results`, `decisions`, and `decision_links` tables.
- [x] Add Alembic migration for validation and decision records.
- [x] Add assumption/risk listing, extraction, and assumption update endpoints.
- [x] Add validation-plan generation endpoint that creates versioned artifacts and experiments.
- [x] Add manual experiment result logging.
- [x] Update assumption status/confidence and project confidence after result logging.
- [x] Add decision ledger endpoints with validated links to assumptions, risks, evidence,
  artifacts, competitors, and experiments.
- [x] Build Assumptions tab with risk display and per-assumption validation-plan action.
- [x] Build Experiments tab with validation plans and result logging.
- [x] Build Decisions tab with rationale, expected outcome, review date, and links.

## Sprint 7 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

Original Sprint 8 plan:

- Add loading/progress states.
- Add SSE workflow updates.
- Add error handling.
- Add empty states.
- Add basic eval checks.
- Add seed/demo project.
- Add README demo script.
- Add screenshots or walkthrough GIF later.

## Sprint 8 Scope

- [x] Add workflow trace APIs:
  - `GET /api/projects/{project_id}/workflows`
  - `GET /api/workflows/{run_id}`
  - `GET /api/workflows/{run_id}/events`
- [x] Add SSE workflow event streaming over persisted `ai_runs` and `ai_steps`.
- [x] Add local-dev demo seeding endpoint:
  - `POST /api/demo/seed`
- [x] Seed the implementation-brief fitness coach scenario with structured project state,
  evidence, cited artifacts, competitors, assumptions, risks, validation experiment result,
  decision links, and workflow observability.
- [x] Add MVP eval endpoint:
  - `GET /api/projects/{project_id}/evals/mvp`
- [x] Add frontend workflow trace panels to intake, brief, competitor analysis,
  assumption extraction, and validation-plan generation.
- [x] Add project overview MVP readiness and recent workflow panels.
- [x] Add project-list demo seeding action.
- [x] Update README demo script and eval docs.
- [ ] Add screenshots or walkthrough GIF later.

## Sprint 8 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_demo_eval_workflows.py`
- [x] `pnpm --filter thesys-web typecheck`

## Next Sprint

Sprint 9: Live ML Demo Readiness.

Detailed Sprint 9 tasks, live-demo instructions, and acceptance criteria now live
in `IMPLEMENTATION_BRIEF.md`.
