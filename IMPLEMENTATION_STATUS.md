# Implementation Status

## Current Phase

V1 Sprints 2 and 3 complete. Approved research sprints can now generate ranked
source candidates and competitor candidates from the research plan. Users can
review source candidates before they are ingested into evidence, and can
review/edit/approve competitor candidates before they become first-class
project competitors. Watchlists, monitoring, collaboration, portfolio
dashboards, integrations, and multi-segment workflow packs remain V2 scope.

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

Original Sprint 9 plan:

- Add AI status endpoint.
- Add visible web AI mode indicator.
- Document live-demo configuration.
- Verify structured-output smoke test can run with `used_stub=false`.
- Improve live-mode error handling.
- Show token and cost metadata in workflow traces.
- Decide whether to add real embeddings.
- Add tests for AI status and live/stub mode behavior.

## Sprint 9 Scope

- [x] Add `GET /api/ai/status` with configured stub mode, resolved mode,
  LiteLLM model/base URL, LiteLLM reachability, provider-key presence booleans,
  embedding configuration, and optional structured-output healthcheck.
- [x] Add global API error handling for LiteLLM and structured-output failures
  so provider issues return actionable 502 responses.
- [x] Add strict structured-output repair attempts and configurable fallback
  policy: `disabled`, `emergency`, or `always`.
- [x] Add web AI mode indicator showing `Stub mode` or `Live LLM`, model name,
  and LiteLLM reachability.
- [x] Add provider/model, token, and cost visibility to workflow traces.
- [x] Render AI-generated markdown output as readable headings, paragraphs,
  lists, links, inline code, and emphasis across project tabs.
- [x] Update `.env.example`, `README.md`, and API docs with the live-demo path.
- [x] Keep deterministic hash embeddings for Sprint 9 and expose the embedding
  model/dimension through AI status.
- [x] Add tests for AI status and live/stub structured-output behavior.

## Sprint 9 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] Browser-verified Brief, Competitors, Assumptions, Experiments, and
  Decisions tabs show no raw markdown heading/list syntax.

Original Sprint 10 plan:

- Add or compute project lifecycle stage.
- Replace developer-facing MVP readiness with founder-facing Idea Readiness.
- Replace Recent Workflows with Recent Strategic Updates.
- Add Current Recommendation, Next Best Action, Strategic Snapshot, and
  Evidence Health overview sections.
- Add guided empty states and outcome-oriented button labels.
- Add overview, readiness, strategic updates, and next-action API endpoints.
- Avoid V1 monitoring, collaboration, portfolio, or agentic research work.

## Sprint 10 Scope

- [x] Add computed overview schemas for project stage, recommendation, next
  action, readiness, strategic snapshot, evidence health, and strategic
  updates.
- [x] Add `ProjectOverviewService` using existing structured project,
  evidence, artifact, claim, assumption, risk, experiment, decision, and
  workflow data.
- [x] Add API endpoints:
  - `GET /api/projects/{project_id}/overview`
  - `GET /api/projects/{project_id}/readiness`
  - `GET /api/projects/{project_id}/strategic-updates`
  - `POST /api/projects/{project_id}/next-action`
- [x] Redesign the Overview tab around Current Recommendation, Next Best
  Action, Idea Readiness, Strategic Snapshot, Evidence Health, Recent
  Strategic Updates, and Key Assumptions/Risks.
- [x] Keep the AI mode badge visible but secondary to project guidance.
- [x] Replace implementation-oriented labels such as “Analyze Idea,”
  “Finalize Intake,” “MVP Readiness,” and “Recent Workflows.”
- [x] Add guided empty states with clear CTAs for briefs, evidence,
  competitors, assumptions, experiments, and decisions.
- [x] Add tests for new-project and seeded-demo overview behavior.

## Sprint 10 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_project_overview.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose up -d`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`

Original V1 Sprint 1 plan:

- Add `Run Research Sprint` CTA to the Overview page.
- Generate a research plan from the current idea/thesis.
- Let the user approve, edit, or reject the research plan.
- Store approved research plans.
- Show research workflow progress.
- Do not perform autonomous browsing/research before user approval.

## V1 Sprint 1 Scope

- [x] Add `research_plans` and `research_sprints` tables.
- [x] Add Alembic migration for research sprint planning records.
- [x] Add `ResearchPlanDraft` structured output schema.
- [x] Add research sprint planning prompt version.
- [x] Add LangGraph-backed planning workflow with project-context loading,
  structured plan generation, persistence, and AI run/step logging.
- [x] Put generated planning runs into `waiting_for_human` status.
- [x] Add research sprint endpoints:
  - `GET /api/projects/{project_id}/research-sprints`
  - `POST /api/projects/{project_id}/research-sprints/plan`
  - `PATCH /api/projects/{project_id}/research-plans/{plan_id}`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/approve`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/reject`
- [x] Add Overview page Research Sprint card with objective input, plan editing,
  save draft, approve, reject, recent plans, and workflow trace.
- [x] Keep autonomous source discovery, competitor discovery, and ingestion out
  of V1 Sprint 1.

## V1 Sprint 1 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_sprints.py`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_sprints.py app/tests/test_project_overview.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `docker compose config`

Original V1 Sprint 2 plan:

- Generate source discovery queries from approved research plans.
- Discover useful public source candidates.
- Rank and dedupe source candidates.
- Let users approve/reject sources before ingestion.
- Link discovered sources to research sprints.

## V1 Sprint 2 Scope

- [x] Add `discovered_sources` table with candidate, approved, rejected,
  ingested, and failed statuses.
- [x] Add `SourceDiscoveryService` that uses LiteLLM structured output in live
  mode and deterministic fallback in stub mode to create ranked public source
  candidates from research plan queries.
- [x] Add source discovery workflow tracing through `ai_runs` and `ai_steps`.
- [x] Add source candidate review endpoints:
  - `GET /api/projects/{project_id}/research-sprints/{sprint_id}/sources`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/approve`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/reject`
- [x] Approving a source candidate ingests a reviewed URL snapshot through the
  existing evidence chunking and embedding pipeline.
- [x] Add Overview page source candidate review UI.

Original V1 Sprint 3 plan:

- Discover direct competitors, indirect competitors, substitutes, and
  incumbents.
- Classify competitors.
- Let users approve, reject, or edit competitor candidates.
- Approved competitors become project competitor records.
- Each candidate explains why it matters.

## V1 Sprint 3 Scope

- [x] Add `competitor_candidates` table with candidate, approved, rejected, and
  merged statuses.
- [x] Add `CompetitorDiscoveryService` that uses LiteLLM structured output in
  live mode and deterministic fallback in stub mode to produce classified
  competitor and substitute candidates from the approved research plan.
- [x] Add competitor discovery workflow tracing through `ai_runs` and
  `ai_steps`.
- [x] Add competitor candidate review endpoints:
  - `GET /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/discover`
  - `PATCH /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/approve`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/reject`
- [x] Approving a competitor candidate creates or updates a first-class
  project competitor and links approved discovered evidence when available.
- [x] Add Overview page competitor candidate review and edit UI.

## V1 Sprints 2-3 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_discovery.py app/tests/test_research_sprints.py`
- [x] Discovery tests assert that live mode calls the structured-output layer
  instead of bypassing LiteLLM.
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`

## Next Sprint

V1 Sprint 4: Auto-Ingestion and Evidence Graph Update.
