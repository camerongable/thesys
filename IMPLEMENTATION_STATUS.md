# Implementation Status

## Current Phase

V1 Sprint 50 implementation is complete on the AI upgrade branch. Thesys now
demonstrates a stronger production-style AI architecture for a portfolio
project:

- provider-backed embeddings with deterministic local fallback and re-embedding
  support
- SQL-level pgvector retrieval with Python fallback
- multi-stage retrieval with query planning, subquery decomposition, reranking,
  context assembly, citation-preserving result metadata, and retrieval-quality
  diagnostics
- LLM-grounded Ask Thesys answers with citations, bounded recent-turn context,
  retrieval diagnostics, action-card routing, and deterministic fallback
- governed external source discovery with deterministic and Tavily providers
- multimodal evidence extraction for image uploads and low-text PDF fallback
- URL/upload security guards, source provenance metadata, canonical
  URL/content-hash dedupe, fetched-page prompt-injection markers, source quality
  signals, and PDF page lineage
- typed context packs, workflow-aware memory selection, and multiple memory
  types
- MCP-shaped adapter over the governed internal tool registry
- AI cost accounting, budget/circuit checks, guide evals, and local AI quality
  gates
- Temporal-backed durable research sprint orchestration
- LangGraph-backed agentic research synthesis
- LangSmith-compatible trace metadata, local AI run/step records, and custom eval
  checks
- shared service utilities for metadata merging and workflow finalization
- developer docs and README navigation for AI architecture review

The simplified project experience is preserved: retrieval, search, extraction,
cost, trace, and quality details stay in Inspect, Evidence, workflow trace,
artifact structured content, and eval/check surfaces rather than new main
dashboard cards. The homepage and main project workflow should remain focused on
current verdict, next action, evidence health, validation, and decision state.

The completed Sprint 41-50 upgrade track is summarized in the "Recently
Completed V1 AI Engineering Upgrade Track" section near the end of this file.

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

Original V1 Sprint 4 plan:

- Approved discovered sources and competitors should be ingested automatically
  into the project evidence graph.
- Fetch approved source content.
- Extract useful text.
- Chunk and embed content.
- Store source metadata and freshness timestamps.
- Link evidence to the project, competitors, assumptions, research questions,
  and artifacts where applicable.
- Make ingestion failures visible and recoverable.

## V1 Sprint 4 Scope

- [x] Add research ingestion metadata fields for discovered source ingestion
  timestamps and competitor candidate evidence ingestion status.
- [x] Upgrade discovered source approval from snapshot-only ingestion to real
  URL fetch, text extraction, chunking, embedding, and evidence-source linking.
- [x] Fall back to ingesting the reviewed discovery snapshot when a public URL
  blocks automated fetch, while preserving the remote fetch error in chunk
  metadata.
- [x] Stamp evidence chunk metadata with research sprint, research plan,
  discovered source, source type, research question, and assumptions-to-test
  provenance.
- [x] Upgrade competitor candidate approval to ingest the candidate URL when
  present, fall back to candidate snapshot ingestion when blocked, and link
  ingested chunks to the merged project competitor.
- [x] Link approved discovered-source evidence referenced by competitor
  candidates to the merged competitor.
- [x] Extend retrieval metadata filtering to support both singular and list
  metadata IDs for competitor-scoped retrieval.
- [x] Show source and competitor evidence ingestion status in the Overview
  research discovery review UI.

## V1 Sprint 4 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_discovery.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`

Original V1 Sprint 5 plan:

- Implement the core agentic RAG workflow.
- Break the research objective into subquestions.
- Choose semantic search, keyword search, source reading, competitor lookup,
  project-memory lookup, artifact lookup, and assumption lookup tools.
- Execute multiple retrieval/tool calls.
- Detect evidence gaps.
- Perform at least one additional retrieval pass when evidence is weak.
- Synthesize cited findings.
- Critique weak claims and unsupported conclusions.
- Produce a final research memo.
- Pause for human approval before major project-memory updates.

## V1 Sprint 5 Scope

- [x] Add `AGENTIC_RESEARCH_PROMPT_VERSION`.
- [x] Add structured schemas for agentic research findings, memo output, and API response.
- [x] Add `AgenticResearchService` with LangGraph nodes:
  - `load_research_context`
  - `research_planner`
  - `retrieval_strategy_selector`
  - `tool_executor`
  - `evidence_selector`
  - `gap_detector`
  - `follow_up_retriever`
  - `synthesizer`
  - `critic`
  - `final_memo_writer`
  - `human_approval_interrupt`
- [x] Implement project-scoped tool interfaces for semantic search, keyword
  search, source reading, competitor lookup, project-memory lookup, artifact
  lookup, and assumption lookup.
- [x] Write cited `research_memo` artifact versions with structured content
  linking back to the research sprint, plan, tool calls, selected evidence,
  evidence gaps, and critic output.
- [x] Store supported claims and claim-to-evidence links from the memo.
- [x] Mark unsupported or weak claims and keep memory updates pending human approval.
- [x] Add endpoint:
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run`
- [x] Add Overview page action to run agentic RAG from the research discovery panel.
- [x] Show the resulting trace and review status in the research sprint UI.
- [x] Add inline research memo review UI with rendered memo content, cited
  claims, unsupported claims, citations, version metadata, and pending human
  review state.
- [x] Add a research memo approval endpoint and UI action that completes the
  human review gate, marks the memo approved, and completes the research sprint.

## V1 Sprint 5 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_research_discovery.py app/tests/test_research_sprints.py -q`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] In-app browser verification for memo review and approval UI.

Original V1 Sprint 6 plan:

- Upgrade research memos so they feel like sharp strategic analysis.
- Add sections for market landscape, pain signals, competitors, substitutes,
  pricing signals, risks, assumptions, evidence summary, unknowns, validation
  actions, and decision recommendation.
- Keep citations and unsupported claims visible.
- Trace memo versions back to research sprints, sources, evidence, and claims.

## V1 Sprint 6 Scope

- [x] Extend `AgenticResearchMemoDraft` with V1 memo sections.
- [x] Render upgraded research memo markdown with the required V1 sections.
- [x] Add research-derived risk and assumption drafts to memo structured content.
- [x] Add memory-update previews to research memo artifact versions.
- [x] Keep cited claims, unsupported claims, selected evidence, tool calls,
  gaps, critic output, and sprint/version links in structured content.
- [x] Show approved memory-update summaries in the memo review UI.

Original V1 Sprint 7 plan:

- Convert research findings into operational validation priorities.
- Create or update assumptions and risks after user approval.
- Rank assumptions by importance, uncertainty, evidence strength, and kill risk.
- Link assumptions to evidence.
- Refresh overview recommendation and next best action after memory changes.

## V1 Sprint 7 Scope

- [x] Add `assumption_evidence_links` table and Alembic migration.
- [x] Add assumption evidence links to API schemas and web types.
- [x] Change research memo approval from metadata-only approval to a memory
  writer that creates or updates assumptions and risks.
- [x] Link research-derived assumptions to cited evidence chunks.
- [x] Update project confidence from research-derived assumption confidence.
- [x] Invalidate overview, assumptions, risks, and experiments after memo
  approval so the UI reflects the new state.
- [x] Add research memo strategic update language to the Overview feed.

Original V1 Sprint 8 plan:

- Help users take action after research.
- Generate validation assets from high-risk assumptions.
- Include interview scripts, screeners, survey questions, landing page copy,
  outreach messages, success criteria, note templates, and result rubrics.
- Keep external execution manual and user-controlled.

## V1 Sprint 8 Scope

- [x] Extend validation plan schemas with screener questions, landing page copy,
  outreach copy, note-taking templates, and result interpretation rubrics.
- [x] Update validation-plan prompting and deterministic stubs to generate the
  richer validation asset set.
- [x] Render validation assets into artifact markdown and experiment plans.
- [x] Show evidence-link counts on research-derived assumptions.
- [x] Preserve the existing manual experiment execution and result logging flow.

## V1 Sprints 6-8 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check ...`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_validation.py -q`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`

Original V1 Sprint 9 plan:

- Show research sprint history.
- Show what changed after each sprint.
- Show evidence added.
- Show assumptions created/updated.
- Show recommendation changes.
- Show memory updates approved/rejected.
- Show research memo versions.

## V1 Sprint 9 Scope

- [x] Add project research-history API:
  - `GET /api/projects/{project_id}/research-history`
- [x] Compute per-sprint history from research plans, source candidates,
  competitor candidates, research memo artifact versions, workflow review state,
  and memory-update status.
- [x] Add explicit research memo rejection endpoint:
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/reject`
- [x] Preserve rejected memory updates in artifact structured content without
  writing assumptions or risks into project memory.
- [x] Surface research history on the Overview page with evidence counts,
  competitor counts, memo/version links, recommendation changes, and event
  timelines.
- [x] Add research-specific strategic updates for memo generation, approved
  memory updates, rejected memory updates, and sprint completion/failure.

Original V1 Sprint 10 plan:

- Add eval cases for autonomous research quality.
- Add retrieval quality checks.
- Add groundedness checks.
- Add latency/cost tracking.
- Add trace inspection.
- Create polished demo projects.

## V1 Sprint 10 Scope

- [x] Add 10-case local research sprint eval dataset:
  - `apps/api/app/evals/research_sprint_cases.json`
- [x] Add V1 research eval endpoint:
  - `GET /api/projects/{project_id}/evals/v1-research`
- [x] Evaluate source discovery, competitor discovery, citation coverage,
  unsupported claims, high-risk assumptions, validation actions, agentic trace
  persistence, evidence gap detection, and cost/latency visibility.
- [x] Show Research Quality checks on the Overview page.
- [x] Document V1 research history and eval commands in README and docs.

## V1 Sprints 9-10 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_history_eval.py -q`
- [x] `cd apps/api && .venv/bin/ruff check ...`
- [x] `pnpm --filter thesys-web typecheck`

## Sprint 11 Scope

- [x] Add Sprint 11 UI/UX refactor requirements to the implementation brief.
- [x] Refactor project navigation to Overview, Research, Evidence, Competitors,
  Assumptions, Validation, and Decisions.
- [x] Move research sprint planning, discovery review, research memo review,
  research history, and quality checks into the Research tab.
- [x] Keep Overview focused on recommendation, next action, lifecycle progress,
  strategic snapshot, top risks, evidence health, and recent strategic updates.
- [x] Add progressive disclosure for manual evidence entry, research traces,
  generated memos, validation plans, and source details.
- [x] Group competitors by category and make competitor profiles easier to scan.
- [x] Refactor assumptions around the riskiest assumption, filters, and a ranked
  operational table.
- [x] Rename Experiments to Validation and make validation assets copyable.
- [x] Add current decision recommendation to the Decisions page.

## Sprint 11 Verification

Checks run:

- [x] `pnpm --filter thesys-web typecheck`

## Sprint 12 Scope

- [x] Audit current V1 project pages against best-in-class workflow patterns
  from Linear, Jira Product Discovery, Dovetail, NotebookLM, and Clay.
- [x] Refine Overview as a Linear-inspired command center with one primary
  action, strong hierarchy, lifecycle progress, and secondary technical status.
- [x] Refine Assumptions and idea-readiness surfaces using prioritization,
  risk, confidence, evidence-strength, and status patterns from Jira Product
  Discovery.
- [x] Refine Evidence and Research surfaces so findings and source-linked
  insights lead, while raw chunks/details stay behind drawers or progressive
  disclosure.
- [x] Refine briefs and research memos around source-grounded reading patterns:
  executive verdict first, citations near claims, sources used, unsupported
  claims, and "what we still do not know."
- [x] Refine research sprint, source discovery, competitor discovery, and
  approval flows around inspectable plain-English workflow steps and structured
  candidate rows/cards.
- [x] Validate the full seeded demo journey across Overview, Research,
  Evidence, Competitors, Assumptions, Validation, and Decisions.

## Sprint 12 Verification

Checks run:

- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose restart web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`

## Sprint 13 Scope

- [x] Add Sprint 13 UX/Product Activation Refactor to `IMPLEMENTATION_BRIEF.md`.
- [x] Create Sprint 13 UX audit/TODO list.
- [x] Add persistent project Verdict Bar across project tabs.
- [x] Rename Overview Current State to Strategic Verdict and add explicit Why framing.
- [x] Surface Riskiest Assumption on the Overview page.
- [x] Refactor the home/project list around product promise, verdict, stage, next action,
  and project-scoped evidence state.
- [x] Make the new-project form start from "Investigate a New Idea" and add Quick Scan /
  Deep Research Sprint choice.
- [x] Refactor Research page so conclusions lead and run/process details are secondary.
- [x] Refactor Evidence page around supported findings and open questions.
- [x] Refactor Competitors page around landscape summary and strategic implication.
- [x] Refactor Assumptions labels and CTA hierarchy.
- [x] Refactor Validation into a step-by-step execution guide.
- [x] Refactor Decisions into suggested decision, rationale, and missing evidence.
- [x] Improve seeded demo project presentation if needed.
- [x] Run Sprint 13 usability task tests.
- [x] Add Sprint 13 product-clarity addendum for strategic judgment, state-aware
  CTAs, workflow-progress labeling, and implication-driven evidence.
- [x] Replace procedural overview/verdict language with strategic recommendations
  from the shared overview service.
- [x] Clarify workflow progress vs idea confidence in the project header,
  verdict bar, Overview, and lifecycle details.
- [x] Add Research Result, Top Validation Priorities, state-aware validation
  CTAs, and stronger decision recommendations.

## Sprint 13 Verification

Checks run:

- [x] `pnpm --filter thesys-web typecheck`
- [x] Manual code-path QA against Sprint 13 usability tasks:
  - home/project list promise and strategic project cards
  - project verdict bar and Overview verdict/next action/riskiest assumption
  - Research conclusions before inspectable run details
  - Evidence supported findings and open questions before raw sources
  - Competitors landscape summary, substitutes, and strategic implication
  - Assumptions risk/confidence labels and primary riskiest-assumption CTA
  - Validation step plan, assets, prominent result logging, and interpretation
  - Decisions suggested decision, rationale, and missing evidence
- [x] `git diff --check`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] `docker compose restart web`
- [x] `curl -I -fsS http://localhost:3000/projects` after restart
- [x] Browser smoke check for `/projects` and seeded demo project verdict context
- [x] Re-run Sprint 13 product-clarity checks after the additional addendum:
  - strategic project card/verdict bar wording
  - hash navigation across project tabs
  - assumptions top priorities and no horizontal overflow
  - evidence implication/open-question format and consistent counts
  - validation state-aware CTA and decision handoff

## V1 Sprint 14 Scope

- [x] Add opt-in LangSmith configuration to API settings, Docker Compose, and
  `.env.example`.
- [x] Add LangSmith dependency and a best-effort observability service that
  creates local trace IDs when external tracing is disabled.
- [x] Persist trace IDs/URLs on `ResearchSprint`, `AIRun`, `AIStep`, and
  `ArtifactVersion`.
- [x] Add Alembic migration for trace columns and indexes.
- [x] Trace research sprint planning, source discovery, competitor discovery,
  agentic research planning/retrieval/synthesis/critique/memo-writing,
  assumption extraction, memory-update approval/rejection, and validation-plan
  generation.
- [x] Expose trace fields through workflow, artifact, and research schemas.
- [x] Show trace links in workflow details, research history, memo review, and
  research quality panels.
- [x] Expand the research eval dataset to 10 Sprint 14 cases with competitor,
  risky-assumption, output-section, unsafe-claim, next-action, and demo-ready
  fields.
- [x] Add V1 research eval metrics for memo completeness, trace ID persistence,
  span coverage, and secret redaction.
- [x] Add local `pnpm eval:research` command.
- [x] Document LangSmith observability and local eval usage in README.

## V1 Sprint 14 Verification

Checks run:

- [ ] `cd apps/api && uv lock` was attempted but `uv` is not installed in this
  shell; `apps/api/uv.lock` already contains `langsmith==0.8.5`.
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_langsmith_observability.py app/tests/test_agentic_research.py app/tests/test_research_history_eval.py app/tests/test_validation.py -q`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `PATH=... node_modules/.bin/next typegen` from `apps/web`
- [x] `PATH=... node_modules/.bin/tsc --noEmit` from `apps/web`
- [x] `python3 scripts/eval_research_sprints.py`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose config`
- [x] `git diff --check -- . ':(exclude)IMPLEMENTATION_BRIEF.md'`
- [ ] Full `git diff --check` is blocked by trailing whitespace in the
  user-updated `IMPLEMENTATION_BRIEF.md`.
- [ ] Browser smoke check is blocked because `http://localhost:3000/projects`
  timed out in the in-app browser.
- [ ] Container restart is blocked because `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
  hung with no output and had to be terminated.

## V1 Sprint 15 Scope

- [x] Add MCP-compatible internal tool definitions with names, descriptions,
  input/output schemas, access modes, risk levels, approval policies, and
  allowed project roles.
- [x] Add `tool_invocations` audit persistence with project and research sprint
  scope, requested-by attribution, redacted input/output payloads, status,
  risk, access mode, and approval metadata.
- [x] Add API endpoints for:
  - `GET /api/tools`
  - `GET /api/projects/{project_id}/tool-invocations`
  - `POST /api/projects/{project_id}/tool-invocations/{invocation_id}/approve`
  - `POST /api/projects/{project_id}/tool-invocations/{invocation_id}/reject`
- [x] Register at least 8 read tools:
  - `get_project_summary`
  - `search_project_evidence`
  - `list_project_sources`
  - `list_competitors`
  - `list_assumptions`
  - `list_validation_plans`
  - `list_decisions`
  - `get_research_memo`
- [x] Register proposal tools:
  - `propose_research_plan`
  - `propose_memory_update`
  - `propose_validation_plan`
  - `propose_decision`
- [x] Route agentic research project context reads, evidence searches, lookup
  calls, and memory/validation/decision proposals through the tool layer.
- [x] Gate research-plan and research-memo proposal approvals before final
  project state mutation.
- [x] Add a secondary Tool Activity panel to the project evidence review UI.
- [x] Document the internal MCP-style tool boundary in README.

## V1 Sprint 15 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app/tests/test_tool_boundary.py app/services/tool_service.py app/routers/tools.py app/services/agentic_research_service.py app/services/research_sprint_service.py`
- [x] `cd apps/api && .venv/bin/python -m pytest app/tests/test_tool_boundary.py app/tests/test_agentic_research.py -q`
- [x] `cd apps/api && .venv/bin/python -m pytest -q`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/apps/web/node_modules/.bin:$PATH tsc --noEmit` from `apps/web`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Post-restart browser smoke check against
  `/projects/386742ee-948b-49d4-9beb-e646d09b8e41#research-sprint`: Tool Activity
  panel rendered one approved `propose_research_plan` invocation and browser
  console reported no errors.

## V1 Sprint 16 Scope

- [x] Replace the legacy member role with owner/admin/editor/viewer permission
  checks for project viewing, research execution, memory approval, high-risk
  tool approval, decision recording, project writes, and owner-only deletion.
- [x] Add `audit_events` and `approval_requests` persistence with Alembic
  migration, Pydantic schemas, governance service helpers, and project-scoped
  API routes.
- [x] Enforce tool authorization by role, access mode, risk, and approval
  policy; deny safely and audit tool denials.
- [x] Create approval requests for research plans, memory updates, validation
  plans, tool proposals, and high-risk decisions.
- [x] Record governance events for research sprint start/approval, tool
  requests/executions/denials, memory proposals/approvals/rejections,
  validation-plan creation, decision recording, and high-risk requests.
- [x] Add shared redaction for API keys, bearer/JWT-like tokens, sensitive key
  names, secret values, and emails across audit, tool, workflow, LangSmith, and
  UI-facing error surfaces.
- [x] Add prompt-injection hardening: agent prompts state retrieved content is
  evidence, not instruction, and retrieved evidence/snippets are wrapped in
  `<untrusted_retrieved_content>` blocks.
- [x] Add the project governance approval queue UI with summary, risk, why it
  matters, proposed state changes, approve/reject controls, and recent audit
  events.
- [x] Document Security and Governance in README.

## V1 Sprint 16 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/python -m pytest app/tests/test_security_governance.py app/tests/test_tool_boundary.py -q`
- [x] `cd apps/api && .venv/bin/python -m pytest app/tests/test_langsmith_observability.py app/tests/test_security_governance.py -q`
- [x] `cd apps/api && .venv/bin/python -m pytest app/tests/test_competitors.py app/tests/test_security_governance.py -q`
- [x] `cd apps/api && .venv/bin/python -m pytest -q`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/apps/web/node_modules/.bin:$PATH next typegen` from `apps/web`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/apps/web/node_modules/.bin:$PATH tsc --noEmit` from `apps/web`
- [x] `git diff --check -- . ':(exclude)IMPLEMENTATION_BRIEF.md'`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Browser QA against
  `/projects/103c6571-aee6-46a0-b0f5-af6be2b409de#research-sprint`: the
  governance approval queue rendered one pending research-plan approval, showed
  proposed change JSON and audit events, the Approve button resolved the queue
  to zero pending approvals, and the browser console reported no errors.
- [ ] `pnpm --dir apps/web typecheck` was attempted but `pnpm` is not installed
  in this shell; local `next typegen` and `tsc --noEmit` both passed.

## V1 Sprint 17 Scope

- [x] Add Temporal SDK dependency, settings, local Docker service, and dedicated
  `temporal-worker` process.
- [x] Add Temporal execution metadata to `research_sprints`: workflow ID, run ID,
  current step, failed step, and failure message.
- [x] Add Alembic migration for durable execution metadata and expanded sprint
  statuses.
- [x] Implement `ResearchSprintWorkflow` as the deterministic Temporal business
  workflow.
- [x] Implement side-effecting Temporal activities for source discovery,
  competitor discovery, ingestion, embedding boundary, LangGraph research
  synthesis, eval checks, memory-update proposal handling, persistence, and
  finalization.
- [x] Keep LangGraph-owned reasoning inside `run_langgraph_research_activity`.
- [x] Add durable workflow API routes for status, start, retry, and cancel.
- [x] Signal the Temporal workflow from research-plan and memory-update approval
  endpoints.
- [x] Add project UI durable workflow status panel with current step, action
  required, retry, and cancel controls.
- [x] Add unit tests for Temporal metadata, approval signaling, retry, cancel,
  and disabled-mode status behavior.
- [x] Document Durable Workflow Orchestration in README.

## V1 Sprint 17 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_temporal_research_orchestration.py app/tests/test_research_sprints.py app/tests/test_agentic_research.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/apps/web/node_modules/.bin:$PATH tsc --noEmit` from `apps/web`
- [x] `git diff --check -- . ':(exclude)IMPLEMENTATION_BRIEF.md'`
- [x] `PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH docker compose up -d --build temporal api temporal-worker`
- [x] `PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH docker compose restart web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] `PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH docker compose exec -T api alembic current`
  reported `0018_temporal_research (head)`.
- [x] `PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH docker compose ps`
  confirmed `temporal`, `temporal-worker`, `api`, and `web` were running.
- [x] Browser QA against
  `/projects/244d865c-b270-4df7-83ff-746a90912b39#research-sprint`: generated
  a Temporal-backed sprint, confirmed the durable workflow panel rendered
  `Temporal enabled`, `waiting for approval`, current step
  `wait for research plan approval`, workflow ID, and action required
  `Approve research plan`; then clicked `Cancel workflow` and confirmed the
  panel and API durable status changed to `cancelled` with no browser console
  errors.

Notes:

- [x] A full web image rebuild was attempted with `docker compose up -d --build
  temporal api temporal-worker web`, but the Docker build exhausted npm
  registry retries with `ECONNRESET`. No frontend dependencies changed in this
  sprint, and the web service bind-mounts `apps/web`, so the existing web image
  was restarted and served the updated source successfully.

## V1 Sprint 18 Scope

- [x] Add guide schema contracts for context, action cards, recommendation
  responses, chat requests, chat responses, and related project entities.
- [x] Add `GuideService` that loads project overview state, derives current
  focus, missing context, biggest unknown, confidence/risk, evidence summary,
  and stage-aware next actions.
- [x] Add guide API routes for:
  - `GET /api/projects/{project_id}/guide/context`
  - `POST /api/projects/{project_id}/guide/recommend`
  - `POST /api/projects/{project_id}/guide/actions/{action_id}/execute`
- [x] Map guide actions to existing project tabs/forms through stable deep
  links and action metadata.
- [x] Cover guide output across at least five project stages.

## V1 Sprint 18 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_guide.py`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_guide.py apps/api/app/tests/test_project_overview.py`
- [x] `apps/api/.venv/bin/ruff check apps/api/app/services/guide_service.py apps/api/app/schemas/guide.py apps/api/app/routers/projects.py apps/api/app/tests/test_guide.py`
- [x] `apps/api/.venv/bin/pytest`
- [x] Runtime check:
  `GET /api/projects/53002617-c8bc-4335-bc4d-9ac43a338390/guide/context`
  returned stage-aware context with missing evidence, assumptions, validation,
  and decision context.
- [x] Runtime check:
  `POST /api/projects/53002617-c8bc-4335-bc4d-9ac43a338390/guide/recommend`
  returned the expected current focus, recommended action, secondary actions,
  and suggested questions.
- [x] Runtime check:
  `POST /api/projects/53002617-c8bc-4335-bc4d-9ac43a338390/guide/actions/generate_brief/execute`
  returned the executable action and target route.

## V1 Sprint 19 Scope

- [x] Add a persistent `GuidePanel` to project pages in both mobile and desktop
  layouts.
- [x] Render current focus, why it matters, the primary recommended action,
  secondary actions, suggested questions, and constrained Ask Thesys responses.
- [x] Wire guide panel actions to existing project navigation and workspace
  affordances.
- [x] Add frontend API client types and calls for guide context,
  recommendations, action execution, and guide chat.
- [x] Add backend guide chat that stays constrained to thesis, evidence,
  blockers, validation, and decisions.

## V1 Sprint 19 Verification

Checks run:

- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin node_modules/.bin/next typegen`
  from `apps/web`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin node_modules/.bin/tsc --noEmit`
  from `apps/web`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Runtime check:
  `POST /api/projects/53002617-c8bc-4335-bc4d-9ac43a338390/guide/chat`
  returned a project-scoped answer, action cards, and related thesis/research
  entities.
- [x] Browser QA in the Codex in-app browser against
  `/projects/53002617-c8bc-4335-bc4d-9ac43a338390#intelligence`: the Guide
  rendered current focus, why it matters, primary action, secondary actions,
  suggested questions, and Ask Thesys; the Guide stayed visible across
  Decision, Intelligence/Evidence, Validation, and Record workspaces; the
  Improve thesis action opened the structured project context form; Ask Thesys
  returned a project-scoped answer with action cards and related entities; the
  browser console reported no errors.

## V1 Sprint 20 Scope

- [x] Add a standalone conversational investigation preview API:
  - `POST /api/intake/investigation/preview`
- [x] Add Sprint 20 response contracts for thesis drafts, investigation modes,
  missing context, assumptions made, clarifying questions, and first next
  action.
- [x] Keep the existing project-bound structured intake APIs intact.
- [x] Add backend preview generation that asks only 2-4 clarifying questions,
  supports continuing with assumptions, and returns a first testable thesis.
- [x] Rebuild the new investigation UI around a guided flow:
  - paste rough idea
  - shape idea
  - answer or skip clarifying questions
  - review first testable thesis
  - choose Quick Orientation, Evidence Review, or Validation Sprint
  - create and finalize the structured project
- [x] Route new projects to the recommended investigation path after creation.

## V1 Sprint 20 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_intake.py`
- [x] `apps/api/.venv/bin/pytest`
- [x] `apps/api/.venv/bin/ruff check apps/api/app`
- [x] `/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node node_modules/next/dist/bin/next typegen`
  from `apps/web`
- [x] `/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node node_modules/typescript/bin/tsc --noEmit`
  from `apps/web`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects/new`
- [x] Runtime check:
  `POST /api/intake/investigation/preview` returned a live LLM thesis draft,
  2-4 clarifying questions, investigation modes, and a recommended path.
- [x] Runtime check:
  preview -> create project -> finalize structured intake -> overview returned
  project `b4706caa-f785-4bd3-9f64-11af9e60f3f5` at stage
  `structured_intake` with next action `Run first research pass`.
- [x] Browser QA: opened `/projects/new`, pasted a rough idea, clicked
  `Shape idea`, verified the first testable thesis appeared, used `Continue
  with assumptions`, created the investigation, and confirmed the project
  opened at `/projects/c1c642a5-f52b-4722-a9f4-25d483c13ccf#research`.
  Captured screenshots in `/private/tmp/thesys-sprint20-qa`; the run reported
  no failed HTTP responses and no browser console errors.

## V1 Sprint 21 Scope

- [x] Add `ThesisCanvas` and `ThesisEvolutionEvent` persistence with project and
  workspace scoping.
- [x] Add Alembic migration for the thesis canvas and evolution timeline tables.
- [x] Add project APIs:
  - `GET /api/projects/{project_id}/thesis-canvas`
  - `PATCH /api/projects/{project_id}/thesis-canvas`
  - `GET /api/projects/{project_id}/thesis-evolution`
- [x] Seed thesis canvases from existing project descriptions, current theses,
  structured intake, assumptions, problems, and validation state.
- [x] Record thesis edits as manual evolution events and create a new project
  thesis version when the current thesis changes.
- [x] Add derived evolution events for research artifacts, validation blockers,
  experiment results, and decisions.
- [x] Teach Ask Thesys to answer how an idea changed and expose `Show evolution`
  and thesis editing actions.
- [x] Add the frontend Thesis tab with editable canvas fields and a chronological
  evolution timeline.

## V1 Sprint 21 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_thesis_canvas.py app/tests/test_guide.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/web && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/node_modules/.bin:$PATH ./node_modules/.bin/next typegen && ./node_modules/.bin/tsc --noEmit`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose config`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Runtime check: `POST /api/demo/seed`, then
  `GET /api/projects/244d865c-b270-4df7-83ff-746a90912b39/thesis-canvas`
  returned a seeded thesis canvas with original idea, current thesis, target
  user, problem, workaround, wedge, biggest unknown, proof needed, and evolution
  events derived from assumptions, research, validation, and decisions.
- [x] Runtime check: created a disposable project, loaded its thesis canvas,
  patched the canvas, confirmed one manual evolution event and thesis version 2,
  then deleted the disposable project.
- [x] Browser QA in the Codex in-app browser: opened the demo project at
  `#thesis`, verified the Thesis workspace rendered seeded canvas fields,
  derived evolution events, and the `Show evolution` guide action; opened a
  disposable project, edited and saved the thesis canvas through the UI,
  confirmed rejected direction/open question counts, manual timeline event, and
  thesis version 2, then deleted the disposable project. Browser console
  reported no errors.

## V1 Sprint 22 Scope

- [x] Add `WedgeOption` persistence with project/workspace scoping.
- [x] Add Alembic migration for the `wedge_options` table.
- [x] Add project APIs:
  - `GET /api/projects/{project_id}/wedges`
  - `POST /api/projects/{project_id}/wedges/generate`
  - `POST /api/projects/{project_id}/wedges/{wedge_id}/select`
  - `POST /api/projects/{project_id}/wedges/{wedge_id}/test`
  - `POST /api/projects/{project_id}/wedges/{wedge_id}/research-more`
  - `POST /api/projects/{project_id}/wedges/{wedge_id}/reject`
- [x] Generate wedge options from the current Thesis Canvas, evidence source
  count, supported claims, competitors, and top assumptions.
- [x] Support `Select wedge`, `Test this wedge`, `Research more`, and `Reject`
  actions.
- [x] Update the Thesis Canvas and create `wedge_change` evolution events when
  a wedge is selected, moved to validation, or rejected.
- [x] Preserve rejected wedges in the Thesis Canvas rejected directions.
- [x] Add a focused Wedge Explorer comparison panel inside the Thesis workspace.
- [x] Update Guide actions and Ask Thesys wedge answers to point to the Wedge
  Explorer instead of the competitor map.

## V1 Sprint 22 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_wedge_explorer.py -q`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_wedge_explorer.py apps/api/app/tests/test_guide.py apps/api/app/tests/test_thesis_canvas.py -q`
- [x] `apps/api/.venv/bin/pytest`
- [x] `apps/api/.venv/bin/ruff check apps/api/app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/web && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/next typegen && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc --noEmit`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Browser QA in the Codex in-app browser after restarting containers:
  created a disposable QA project, opened `#thesis`, generated wedges, selected
  `Manual workaround replacement`, confirmed it became the single recommended
  wedge, moved it to validation, rejected the broad concept wedge, and confirmed
  Ask Thesys answered the wedge question with the recommended wedge, why it
  might work, main risk, and first test. Browser logs reported no app warnings
  or errors.

## V1 Sprint 23 Scope

- [x] Add `ValidationMission` persistence with project/workspace scoping,
  assumption link, optional experiment link, mission status, steps, criteria,
  and validation assets.
- [x] Add Alembic migration for the `validation_missions` table.
- [x] Add mission APIs:
  - `GET /api/projects/{project_id}/experiments/missions`
  - `GET /api/projects/{project_id}/experiments/missions/current`
  - `POST /api/projects/{project_id}/experiments/missions/{mission_id}/start`
  - `POST /api/projects/{project_id}/experiments/missions/{mission_id}/interpret`
- [x] Create validation missions when validation plans generate experiments.
- [x] Advance mission state when a mission starts, results are logged, and
  results are interpreted.
- [x] Update demo seeding so the fitness coach demo includes a validation
  mission.
- [x] Update Guide actions and related entities to route to the current
  validation mission.
- [x] Redesign the Validation workspace front door around a mission-first
  current proof with steps, progress, primary CTA, criteria, assets, result
  logging, and interpretation.

## V1 Sprint 23 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_guide.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/web && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/next typegen && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc --noEmit`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Browser QA in the Codex in-app browser after restarting containers:
  created a disposable QA project, generated and started a validation mission,
  pasted raw interview/pricing/workaround notes, confirmed the interpreted
  signal summary, pain/urgency/WTP/switching fields, strengthened/weakened
  bullets, recommended next action, and pending-approval copy, then approved the
  pending memory update from Intelligence > Evidence review and confirmed the
  governance panel cleared to 0 pending with audit events recorded.
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Browser QA in the Codex in-app browser after restarting containers:
  created a disposable QA project, extracted assumptions, generated a
  validation plan, opened `#validation-mission`, started the mission, logged a
  result, interpreted the result, and confirmed the final CTA routes to
  `#decisions`. Checked desktop and mobile mission-panel viewports for
  horizontal overflow.

## V1 Sprint 24 Scope

- [x] Add persisted `ValidationResultInterpretation` records linked to
  project, mission, experiment, assumption, AI run, and approval request.
- [x] Add Alembic migration for validation result interpretations.
- [x] Replace the status-only mission interpretation endpoint with a structured
  interpretation workflow that accepts pasted validation notes or uses logged
  results.
- [x] Extract pain severity, urgency, willingness-to-pay signal, switching
  signal, objections, quotes, confidence change, next action, and decision
  recommendation.
- [x] Create a pending `memory_update` approval before applying major project
  state changes.
- [x] Apply approved interpretation updates to assumption confidence/status,
  project confidence, audit trail, and thesis evolution.
- [x] Show the latest interpretation inside the Validation Mission UI.
- [x] Add a paste-notes interpretation form with a pending-approval message.
- [x] Treat validation interpretations as decision evidence in overview
  readiness/stage logic.

## V1 Sprint 24 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py -q`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/web && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/next typegen && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc --noEmit`

## V1 Sprint 25 Scope

- [x] Add backend Decision Coach response contracts for recommendation,
  supporting evidence, missing evidence, risks, action cards, and suggested
  decision record prefill.
- [x] Add decision APIs:
  - `GET /api/projects/{project_id}/decisions/recommendation`
  - `POST /api/projects/{project_id}/decisions/coach`
- [x] Derive recommendations from interpreted validation results when present,
  with deterministic fallbacks for projects that still need evidence.
- [x] Generate suggested decision records with trace links to the key blocker,
  evidence sources, and validation experiment tied to the mission.
- [x] Route decision-related Guide chat questions through Decision Coach.
- [x] Update the Decisions workspace to show a Decision Coach panel with the
  recommended decision, rationale, missing proof, supporting evidence, risks,
  constrained Q&A, and prefilled record action.
- [x] Preserve the existing durable decision record form and evidence-link
  workflow.

## V1 Sprint 25 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_validation.py apps/api/app/tests/test_guide.py -q`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests -q`
- [x] `apps/api/.venv/bin/ruff check apps/api/app/services/validation_service.py apps/api/app/routers/decisions.py apps/api/app/services/guide_service.py apps/api/app/schemas/validation.py apps/api/app/tests/test_validation.py`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I http://localhost:3000/projects`
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 26 Scope

- [x] Add a typed playbook navigation contract to the project overview API.
- [x] Compute stage-aware playbook steps for Guide, Thesis, Research, Test,
  Decision, and History.
- [x] Mark each playbook step as available, blocked, complete, or current.
- [x] Highlight the current lifecycle step based on project stage:
  - draft idea -> Thesis
  - structured/researched stages -> Research
  - assumption/validation stages -> Test
  - results logged -> Decision
  - recorded/paused/killed stages -> History
- [x] Replace the project page "Workspaces" navigation with "Idea Playbook."
- [x] Show each playbook item with user-facing purpose text and status.
- [x] Replace mobile "Switch workspace" copy with "Switch playbook step."
- [x] Preserve existing internal tab routes while exposing guided playbook
  labels and deep links.
- [x] Rename the visible Intelligence surface to Research.

## V1 Sprint 26 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_project_overview.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 27 Scope

- [x] Add persisted `ProjectNudge` records with severity, message,
  why-it-matters copy, embedded `GuideAction`, and dismissed state.
- [x] Add Alembic migration for `project_nudges`.
- [x] Add deterministic `NudgeService` that derives project-specific nudges
  from current project state instead of generating generic chat output.
- [x] Generate proactive nudges for:
  - broad ideas that need wedge comparison
  - projects with enough research for a first validation test
  - validation plans/missions with no logged results
  - weak evidence areas such as willingness to pay or unsupported claims
- [x] Cap visible nudges to at most two active nudges.
- [x] Add nudge APIs:
  - `GET /api/projects/{project_id}/nudges`
  - `POST /api/projects/{project_id}/nudges/{nudge_id}/dismiss`
- [x] Add nudge display in the persistent Guide panel.
- [x] Add a compact nudge surface to the project overview.
- [x] Let users dismiss nudges and keep dismissal persisted.
- [x] Route nudge action cards through existing guide action navigation.

## V1 Sprint 27 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_nudges.py`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_nudges.py app/tests/test_guide.py app/tests/test_project_overview.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test created a disposable project, added evidence,
  extracted assumptions, confirmed two project-specific nudges, dismissed one,
  and confirmed it no longer appeared in active nudges.
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 28 Scope

- [x] Refresh the primary fitness-coach demo into a guided strategic journey
  rather than a generic seeded data project.
- [x] Seed a messy original idea, structured intake, Thesis Canvas, thesis
  evolution events, and rejected directions.
- [x] Seed Wedge Explorer options with a recommended narrow wedge and explicit
  avoid/research-later alternatives.
- [x] Seed a validation mission with interpreted results so the project reaches
  the Decision Coach instead of stopping at raw experiment output.
- [x] Seed a Decision Coach-aligned decision record recommendation that
  preserves the "continue research" path and trace links to the relevant
  assumption and experiment.
- [x] Reset demo nudges on refresh so the guided project is repeatable.
- [x] Update the project list demo entry point and API response so the demo
  opens at the Guide panel.
- [x] Extend demo seed counts and tests to verify the Sprint 28 journey objects.

## V1 Sprint 28 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_demo_eval_workflows.py -q`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_demo_eval_workflows.py apps/api/app/tests/test_thesis_canvas.py apps/api/app/tests/test_wedge_explorer.py apps/api/app/tests/test_validation.py apps/api/app/tests/test_guide.py apps/api/app/tests/test_project_overview.py -q`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests -q`
- [x] `apps/api/.venv/bin/ruff check apps/api/app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` created the guided demo
  project and returned `#guide` with seeded thesis canvas, thesis evolution,
  wedges, validation mission, interpretation, and decision counts.
- [x] Browser QA in the Codex in-app browser: clicked `Load guided demo`,
  verified redirect to `#guide`, checked Guide, Thesis, Validation, Decision,
  and History markers, confirmed no browser console warnings/errors, and ran
  desktop/mobile layout probes for horizontal overflow and button text overflow.

## V1 Sprint 30 Scope

- [x] Add `after_that` to guide recommendations so the Guide explains what
  happens after the primary action.
- [x] Add `recommended_action` to guide chat responses.
- [x] Cap guide secondary actions to three.
- [x] Replace vague guide action labels with specific routing commands such as
  "Show evidence behind the blocker," "Rewrite thesis with current wedge,"
  "Compare wedge options," "Open validation result form," and "Prepare decision
  record."
- [x] Keep backward-compatible aliases for older guide action IDs.
- [x] Align project nudges and Decision Coach evidence actions with the new
  guide action-router vocabulary.
- [x] Replace the inline guide disclosure with a bottom-right `Ask Thesys`
  button and bottom drawer.
- [x] Update the Guide panel copy to the Sprint 30 structure: what matters now,
  why, do this next, after that, and actions.
- [x] Update prompt chips to be action-oriented.

## V1 Sprint 30 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_nudges.py app/tests/test_wedge_explorer.py app/tests/test_thesis_canvas.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided demo
  project successfully.
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 31 Scope

- [x] Add a derived `GET /api/projects/{project_id}/idea-story` API that
  summarizes original idea, current thesis, selected wedge, rejected
  directions, why the idea changed, current blocker, and next proof from
  existing Thesis Canvas, wedge, and evolution records.
- [x] Add a compact "How this idea has changed" section to Current Step.
- [x] Replace the Current Step peer-field grid with a storyline that keeps
  original idea, thesis, selected wedge, rejected direction, blocker, and next
  proof visible together.
- [x] Simplify Wedge Explorer's default view to show the recommended wedge, one
  avoid-for-now/rejected direction, and one research-later/promising direction.
- [x] Keep the full Wedge Explorer available behind "Compare all wedges."
- [x] Extend Guide chat so it can answer idea evolution, wedge rationale,
  rejected broad-direction, and next-proof questions.
- [x] Add tests for Idea Story derivation and Sprint 31 Guide prompts.

## V1 Sprint 31 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_thesis_canvas.py app/tests/test_guide.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `pnpm --filter thesys-web test`
- [x] `docker compose config`
- [x] `docker compose restart api web temporal-worker`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and `GET /api/projects/{project_id}/idea-story` returned the
  original idea, current thesis, selected wedge, rejected directions, blocker,
  and next proof.
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 32 Scope

- [x] Update the homepage headline/subheading around the Sprint 32 promise:
  rough idea → wedge → biggest unknown → next proof.
- [x] Rename the default queue to "Ideas in progress" and reduce project rows
  to the allowed essentials: thesis/description, verdict, next action, stage,
  and evidence summary.
- [x] Hide disposable smoke, QA, and browser-test projects from the homepage by
  default while keeping the guided fitness-coach demo visible.
- [x] Add a "Show test projects" filter for inspecting hidden QA projects.
- [x] Keep new-investigation intake focused after preview by showing one
  recommended path and collapsing alternate paths.
- [x] Route newly created investigations to Current Step by default, with
  explicit actions for Current Step, research, or wedge comparison.
- [x] Compress Current Step so the primary job, CTA, thesis, selected wedge,
  biggest unknown, and next proof are visible first.
- [x] Move supporting evidence, recovery, blocker details, and idea-history
  details behind Inspect sections.
- [x] Apply Sprint 32 terminology across visible detail labels: evidence
  summary, competitors and substitutes, full research memo, active test, and
  assumptions behind the decision.
- [x] Add frontend tests for homepage test-project filtering.

## V1 Sprint 32 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned `#current-step` with seeded thesis canvas, thesis
  evolution, wedges, validation mission, interpretation, and decision counts.
- [x] Browser QA in the Codex in-app browser: verified homepage copy, "Ideas in
  progress," default hiding of QA/browser/endpoint-audit/demo clutter, "Show
  test projects" reveal behavior, guided demo visibility, direct Current Step
  landing on `#current-step`, compact thesis/wedge/biggest unknown/next proof
  story, collapsed Inspect sections, and no browser warn/error console logs.

## V1 Sprint 33 Scope

- [x] Make Current Step the quiet default project workspace surface by removing
  the default status bar, project map/sidebar, mobile project menu, mobile
  workspace action, and mobile decision spine from that tab.
- [x] Keep the current verdict/status, one primary CTA, and current test path
  visible before any process detail.
- [x] Preserve the active idea story: current thesis, selected wedge, biggest
  unknown, and next proof remain visible together.
- [x] Move project nudges, decision context, evidence summary, recovery detail,
  supporting workspace links, and decision history behind Inspect details.
- [x] Keep Ask Thesys available through the floating guide drawer instead of a
  permanent guide panel or secondary button row on the default Current Step.
- [x] Preserve workspace routes and deep links for Test, Research, Shape,
  Decide, and History from the inspect controls.
- [x] Add frontend regression coverage for the quiet Current Step rendering
  contract.

## V1 Sprint 33 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned
  `/projects/3160c9e9-5c3e-491f-9cc5-6e8081c2917c#current-step`.
- [x] Manual Chrome browser QA against the guided demo project: verified the
  desktop default Current Step shows one main panel, one primary CTA, the
  current test path, collapsed Inspect details, and the floating Ask Thesys
  drawer without the old project map/sidebar or default status/process chrome.
- [x] Manual responsive QA in Chrome DevTools at 400px width: verified the
  mobile Current Step starts with the project title, primary CTA, current test
  path, Inspect details, and Ask Thesys without the old mobile menu or mobile
  decision spine.

## V1 Sprint 34 Scope

- [x] Add a reusable `ProjectInspectDrawer` driven by existing project overview
  and idea-story data.
- [x] Move advanced status, evidence, assumptions, test path, research details,
  decision history, and project context into the drawer.
- [x] Replace the inline Current Step inspect/evolution detail with an
  `Inspect details` button that opens local drawer state without changing the
  route or hash.
- [x] Keep the closed Current Step focused on the verdict/current step, one
  primary CTA, current thesis, selected wedge, biggest unknown, next proof, and
  lightweight Ask Thesys access.
- [x] Replace the desktop project map/sidebar and mobile project menu with a
  compact `Explore` control backed by `projectNavigationItems`.
- [x] Keep canonical Explore routing at `#current-step`, `#shape`, `#research`,
  `#test`, `#decide`, and `#history`.
- [x] Preserve legacy aliases and deep-link anchors such as `#guide`,
  `#decision`, `#evidence`, `#validation`, `#record`,
  `#validation-mission`, and `#record-decision-panel`.
- [x] Add frontend regression coverage for the quiet Current Step, Inspect
  drawer sections/actions, responsive sheet sizing, compact Explore control,
  removed legacy navigation chrome, and routing compatibility.

## V1 Sprint 34 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned
  `/projects/3160c9e9-5c3e-491f-9cc5-6e8081c2917c#current-step`.
- [x] Desktop browser QA in the Codex in-app browser: verified the quiet
  Current Step has one dominant CTA, current thesis/wedge/unknown/proof path,
  Inspect details, Ask Thesys, no default evidence metrics/status history, no
  old Guided mode sidebar/mobile project menu labels, and no app console
  warnings/errors.
- [x] Desktop Inspect drawer QA in the Codex in-app browser: verified all
  required sections and action links, close-button focus, Escape close,
  backdrop close, body scroll lock cleanup, and no URL hash change for drawer
  open/close.
- [x] Desktop Explore QA in the Codex in-app browser: verified compact
  navigation opens with Current Step, Shape, Research, Test, Decide, and History;
  each item closes Explore and routes to the canonical hash.
- [x] Deep-link QA in the Codex in-app browser: verified `#research`,
  `#validation-mission`, `#record-decision-panel`, and `#history` land on the
  expected workspace surface without restoring old navigation chrome.
- [x] Responsive browser QA at 410x844 through a temporary Chrome CDP session:
  verified the quiet Current Step has no horizontal overflow, Inspect details
  opens as a full-screen sheet with required sections/actions and closes without
  changing `#current-step`, Explore opens as a full-screen sheet, and selecting
  Shape routes to `#shape`.

## V1 Sprint 35 Scope

- [x] Simplify `/projects` into a launcher with one headline, one supporting
  sentence, one dominant `Start investigation` CTA, and secondary
  `Load guided demo` access.
- [x] Remove the right-side launcher/demo cards from `/projects`.
- [x] Collapse search, stage/risk filters, sort, compact rows, and
  `Show test projects` behind one `Filter` disclosure on every viewport.
- [x] Preserve project queue behavior, keyboard shortcut entry points, and
  disposable test/demo/audit hiding by default, including existing local audit
  rows.
- [x] Convert `/projects/new` to a single-column rough-idea flow without
  persistent explanatory sidebars.
- [x] Keep context checks, clarifying questions, assumptions continuation,
  thesis preview, recommended path, loading states, validation errors, sample
  idea, and existing API calls.
- [x] Make `Continue to Current Step` the dominant post-preview creation action,
  with `Run research` and `Compare wedges` as secondary actions.
- [x] Preserve primary routing to `/projects/{id}#current-step` and secondary
  routing to `#research` and `#wedge`.
- [x] Add frontend regression coverage for disposable row hiding, collapsed
  launcher filters, removed competing launcher cards, and single-column new
  investigation structure.

## V1 Sprint 35 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose stop web`
- [x] `docker compose rm -f web`
- [x] `docker volume rm thesys_web_next_cache`
- [x] `docker compose up -d web`
- [x] `docker compose restart web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned
  `/projects/3160c9e9-5c3e-491f-9cc5-6e8081c2917c#current-step`.
- [x] Desktop Codex in-app browser QA on `/` and `/projects`: verified `/`
  redirects to `/projects`, only one dominant `Start investigation` CTA is
  visible, `Load guided demo` is secondary, the old right rail cards are gone,
  filters are collapsed behind `Filter`, disposable test/demo/audit rows are
  hidden by default, `Show test projects` lives inside the filter disclosure and
  reveals hidden rows, and the app console reported no warnings/errors.
- [x] Desktop Codex in-app browser QA on `/projects/new`: verified the page is
  single-column, no persistent explanatory sidebar cards render, the sample
  rough idea previews a first thesis, possible wedge, biggest unknown, and
  recommended path, `Continue to Current Step` is primary, `Run research` and
  `Compare wedges` are secondary, and creating from preview opens
  `/projects/{id}#current-step`.
- [x] Mobile Codex in-app browser QA at 410px width on `/projects`: verified no
  horizontal overflow, the primary CTA stays obvious, the filter menu opens
  cleanly, and `Show test projects` is usable inside the disclosure.
- [x] Mobile Codex in-app browser QA at 410px width on `/projects/new`: verified
  no horizontal overflow, the single-column preview remains usable, and the
  post-preview Current Step/research/wedge action row fits and remains usable.

## V1 Sprint 36 Scope

- [x] Standardize empty states across default project surfaces so they state
  what is missing, why it matters, and the next action.
- [x] Reduce non-primary card treatment on `/projects`, `/projects/new`,
  Current Step supporting sections, Explore, and Inspect by using border bands,
  dividers, compact rows, and sheet sections.
- [x] Remove duplicate post-preview intake copy by replacing the old
  `Continue with assumptions` path with a single dominant
  `Continue to Current Step` action that preserves assumptions when needed.
- [x] Keep `/projects` as one dominant `Start investigation` launcher with
  secondary guided-demo access and collapsed filters.
- [x] Keep `/projects/new` as a single-column rough-idea flow with stacked
  mobile actions and no persistent explanatory sidebar.
- [x] Keep Current Step focused on one current action, current thesis, selected
  wedge, biggest unknown, next proof, Inspect details, and Ask Thesys.
- [x] Keep Inspect details advanced and route-local; opening and closing it does
  not change the hash.
- [x] Add Sprint 36 source-structure regression tests for quiet launcher/intake
  structure, stale card/navigation skeleton prevention, empty-state wording, and
  the Current Step CTA wording.

## V1 Sprint 36 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose config`
- [x] `docker compose restart web` after the IDE browser showed stale Next.js
  output for `/projects/new`.
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned
  `/projects/3160c9e9-5c3e-491f-9cc5-6e8081c2917c#current-step`.
- [x] Desktop Codex in-app browser QA: verified `/` redirects to `/projects`;
  `/projects` has one dominant `Start investigation` CTA, secondary guided demo
  access, collapsed filters, and no right-rail launcher cards; `/projects/new`
  is single-column, previews cleanly, and routes `Continue to Current Step` to
  `/projects/{id}#current-step`; no horizontal overflow or app console
  warnings/errors were observed.
- [x] Desktop guided-demo browser QA: verified `#current-step` shows one clear
  current action, current thesis, selected wedge, biggest unknown, next proof,
  Inspect details, and Ask Thesys without default status/card clutter.
- [x] Desktop Inspect and Explore browser QA: verified Inspect opens/closes
  cleanly without changing the route/hash, advanced details remain grouped in
  drawer sections, Explore opens Current Step, Shape, Research, Test, Decide,
  and History, and legacy deep links `#research`, `#validation-mission`,
  `#record-decision-panel`, and `#history` land on the correct surfaces.
- [x] Mobile Codex in-app browser QA at 410px width: verified `/projects` has no
  horizontal overflow, primary CTA remains obvious, and the Filter disclosure is
  usable; `/projects/new` has no horizontal overflow and post-preview actions
  wrap cleanly.
- [x] Mobile guided-demo browser QA at 410px width: verified Current Step places
  the current action and test path before advanced detail, Inspect opens as a
  full-screen sheet, Explore opens as a full-screen sheet, and selected Explore
  destinations route correctly.

## V1 Sprint 37 Scope

- [x] Add embedding provider configuration for deterministic local embeddings
  and LiteLLM/OpenAI-compatible production embeddings, including model,
  provider, version, timeout, retry, and dimension validation.
- [x] Store embedding provenance on `evidence_chunks`: provider, model,
  dimension, version, embedded timestamp, and embedding error.
- [x] Add a migration for embedding provenance columns plus a pgvector ANN index,
  preferring HNSW and falling back to IVFFlat where needed.
- [x] Preserve deterministic dev embeddings while adding provider metadata to
  ingestion traces and retrieval results.
- [x] Implement the Postgres pgvector SQL retrieval path for semantic and hybrid
  evidence search, with project/source/freshness/metadata filters applied before
  vector ranking.
- [x] Keep deterministic Python retrieval as the non-Postgres/configured
  fallback path and return explicit fallback diagnostics.
- [x] Persist retrieval diagnostics in `ai_steps.output_json` and return them
  through the evidence retrieval API.
- [x] Add `POST /api/projects/{project_id}/evidence/reembed` with dry-run,
  project/workspace scope, current-provider eligibility checks, and per-chunk
  failure reporting.
- [x] Surface retrieval path diagnostics, per-result embedding provenance, and
  re-embedding maintenance controls in the advanced Evidence detail surface.
- [x] Extend AI status, tool schemas, docs, Docker Compose, `.env.example`, and
  LiteLLM config for the production embedding/retrieval path.

## V1 Sprint 37 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_embedding_service.py app/tests/test_ai.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_research_history_eval.py app/tests/test_tool_boundary.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api temporal-worker web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack AI status smoke test: verified embedding provider/model/version,
  dimension, retrieval vector path, and Python fallback configuration are
  returned by `/api/ai/status`.
- [x] Live-stack API fixture smoke test: created `Sprint 37 browser check`,
  ingested one note source, retrieved one hybrid result through the HNSW
  pgvector SQL path, and verified diagnostics reported `used_sql_vector_search`
  with no fallback.
- [x] Live-stack re-embed API smoke test: dry-run re-embed scanned one chunk,
  skipped it as already current, and returned zero failures.
- [x] Desktop Codex in-app browser QA: opened the fixture project, navigated
  Research -> Inspect -> Evidence summary, ran a hybrid source-chunk search,
  verified the rendered `Retrieval: pgvector SQL` diagnostics, opened the result
  receipt, verified retrieved text plus embedding provenance, and confirmed
  `Dry run` and `Re-embed project` maintenance summaries render correctly.
- [x] Browser console QA: no app console errors were present after the Sprint 37
  verification flow.

## V1 Sprint 38 Scope

- [x] Add reusable retrieval pipeline service with broad-query planning,
  strategic intent classification, target entity/evidence-type extraction, and
  subquery decomposition.
- [x] Run semantic, keyword, metadata-filtered, freshness-boosted, and
  credibility-aware retrieval through the existing pgvector SQL path with Python
  fallback.
- [x] Add deterministic reranking by default, disabled mode, and optional
  LiteLLM reranker configuration with deterministic fallback on provider errors.
- [x] Assemble bounded context with near-duplicate suppression, source diversity,
  minimum context score, token budget enforcement, and preserved source/chunk
  IDs.
- [x] Extend retrieval API schemas with rerank score, final rank, context
  inclusion, selection reason, nested query plan, reranker, context, and quality
  diagnostics.
- [x] Wire the pipeline into evidence retrieve, opportunity brief evidence
  retrieval, agentic research tool execution, evidence selection, follow-up
  retrieval, final memo structured content, and V1 research eval metrics.
- [x] Keep retrieval-quality visibility in existing Inspect, workflow trace,
  evidence search, memo review, and eval/check surfaces only.
- [x] Add reranker/context configuration to `.env.example`, Docker Compose,
  README, AI status, and frontend API types.
- [x] Refine redaction so real secrets remain redacted while non-secret
  retrieval token counts and token budgets remain inspectable.

## V1 Sprint 38 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_opportunity_brief.py app/tests/test_agentic_research.py app/tests/test_research_history_eval.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `pnpm --filter thesys-web test`
- [x] `docker compose config`
- [x] Local-stack browser QA: created `Sprint 38 retrieval QA`, seeded four
  sources, ran the broad query `Which wedge is strongest and what proof is
  missing?`, and verified Inspect showed pgvector SQL retrieval, 3 subqueries,
  deterministic reranker, 1 selected chunk, 47/3500 context tokens, precision
  1.00, recall 0.25, duplicate suppression, and no noisy source selected.
- [x] Browser brief QA: regenerated an opportunity brief in stub mode, verified
  cited claims and appendix entries preserved source/chunk-backed quotes, and
  opened the trace showing 5 retrieval queries, deterministic reranker, 2
  context chunks, and 89/3500 context tokens.
- [x] Browser agentic research QA: ran an agentic evidence review in stub mode,
  verified the memo stored 6 retrieval diagnostics plus 4 selected context
  chunks at 226/3500 tokens, and confirmed Evidence Checks showed multi-stage
  retrieval strategy, reranker visibility, context assembly, and retrieval
  quality report metrics in Inspect.
- [x] Browser console and responsive QA: console errors/warnings were empty for
  the app tab; at 410px width, the Inspect evidence-check content had no
  horizontal overflow, no overflowing buttons, and retrieval-quality lines
  remained readable and scrollable.

## V1 Sprint 39 Scope

- [x] Preserve the existing guide intent guardrail, bounded out-of-scope
  refusal, deterministic fallback path, and action-card routing.
- [x] Add traced `guide_chat` AI runs/steps for Ask Thesys with prompt version,
  model/provider metadata, latency/cost fields, intent guardrail output,
  retrieval context output, and answer summaries.
- [x] Ground in-scope Ask Thesys answers through the governed
  `search_project_evidence` read-only tool and return cited evidence IDs,
  retrieval diagnostics, confidence level, unsupported/missing evidence, and
  trace IDs in the guide chat response.
- [x] Add live-mode structured LLM guide answers with citation filtering,
  existing-action filtering, untrusted retrieved-content instructions, and
  deterministic fallback if generation or validation fails.
- [x] Keep chat non-mutating: proposal-style prompts route to existing
  navigation/workflow actions, including scoped research-plan routing, without
  executing write/proposal tools directly from chat.
- [x] Add bounded session context by sending only the last six guide turns from
  the panel and including the trimmed context in live LLM prompt input.
- [x] Surface compact Ask Thesys grounding metadata in the guide panel without
  turning the UI into a transcript-heavy chat surface.
- [x] Extend guide tests for grounded retrieval metadata, AI run/step traces,
  read-only tool logging, long-query truncation, non-mutating proposal prompts,
  research-plan routing, live structured LLM output, citation filtering, action
  filtering, and bounded recent-turn prompt context.

## V1 Sprint 39 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_guide.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `pnpm --filter thesys-web test`
- [x] `docker compose config`
- [x] Local-stack functional QA on alternate ports with a disposable SQLite
  model-created database: started the API on `127.0.0.1:8010` and web on
  `127.0.0.1:3010`, seeded the guided demo project, asked `What does the
  evidence say about weekly coach check-ins?`, and verified the guide response
  returned cited evidence IDs, medium confidence, retrieval diagnostics,
  related evidence entities, and an AI run trace ID.
- [x] Local-stack non-mutation QA: asked `Create and apply a validation plan for
  the riskiest assumption.` and verified the response returned existing guide
  actions while the tool invocation log contained only read-only
  `search_project_evidence` calls and no proposal/write invocation.

Manual environment note:

- Codex in-app browser QA was blocked in this session: the Browser plugin setup
  succeeded but no `iab`/browser target was registered, and the local
  app-control surface timed out while listing apps. Docker-backed localhost
  verification was also unavailable because Docker returned internal API errors
  and its owned `3000`/`8000` listeners did not respond.

## V1 Sprint 40 Scope

- [x] Add governed external search settings and a provider boundary with
  deterministic and Tavily adapters.
- [x] Keep external search disabled by default, with deterministic local mode
  and opt-in Tavily via `EXTERNAL_SEARCH_ENABLED`, `EXTERNAL_SEARCH_PROVIDER`,
  and `TAVILY_API_KEY`.
- [x] Route approved research-sprint source discovery through external search
  when enabled, dedupe by normalized URL, store provider/query/rank/retrieval
  provenance, and preserve the existing review/approval/rejection flow.
- [x] Carry search provenance into evidence source metadata and chunk metadata
  after source approval, including fallback snapshot ingestion when remote fetch
  fails.
- [x] Add multimodal evidence extraction through a backend extractor boundary
  with deterministic fixture extraction by default and LiteLLM multimodal
  extraction for live image/PDF paths.
- [x] Support PNG, JPG, JPEG, and WebP uploads; keep text-native PDFs on `pypdf`
  and route low-text PDFs to multimodal fallback only when configured.
- [x] Add `source_metadata` storage and expose evidence source `metadata` through
  the existing evidence API.
- [x] Keep search and extraction details behind Research/Evidence inspection
  controls so Current Step stays quiet.
- [x] Extend V1 research eval with search relevance, source diversity,
  duplicate-rate, and provenance-coverage metrics.
- [x] Document external search and multimodal extraction settings in
  `.env.example`, Docker Compose, README, API status, and frontend API types.

## V1 Sprint 40 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_discovery.py app/tests/test_evidence.py app/tests/test_research_history_eval.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `pnpm --filter thesys-web test`
- [x] `docker compose config`
- [x] IDE browser deterministic connector QA on alternate local ports
  `127.0.0.1:3010`/`127.0.0.1:8010`: created disposable project
  `Sprint 40 connector QA`, planned and approved an evidence review, ran
  `Find sources`, confirmed deterministic candidates showed provider/query/rank
  and retrieval time, approved one source, rejected one source, and confirmed
  the approved source appeared as ready evidence.
- [x] Browser evidence inspection QA: opened the approved source detail and
  confirmed search provider, query, rank, retrieval timestamp, risk, and content
  type appeared only behind the provenance details control.
- [x] Browser retrieval QA: searched stored chunks for deterministic-source text
  and confirmed the approved URL source was retrieved.
- [x] Browser multimodal QA: uploaded the Sprint 40 fixture image through the
  evidence file endpoint, inspected it in the browser, confirmed ready status,
  deterministic extraction metadata, extracted text preview, and retrieval by a
  phrase from the extracted text.
- [x] Browser PDF QA: uploaded a normal text PDF, inspected it in the browser,
  and confirmed `pypdf` metadata without multimodal fallback.
- [x] Browser quality QA: browser console errors/warnings were empty, app API
  responses during the verified flow were 2xx, and the 410px viewport had no
  horizontal overflow with extraction details absent from Current Step.

Manual environment note:

- The local Docker API/web ports were already occupied, so manual browser QA used
  isolated alternate ports plus a temporary SQLite database and local object
  storage. The optional live Tavily path was not run because no `TAVILY_API_KEY`
  was configured for this session.

## Recently Completed V1 AI Engineering Upgrade Track

Sprints 41-50 are implemented on the AI upgrade branch:

1. V1 Sprint 41: Security, AI Safety, and Abuse Hardening
   - Added SSRF-resistant URL validation, redirect re-checks, response-size
     limits, upload validation, file-name sanitization, and audit events for
     rejected ingestion.
2. V1 Sprint 42: Context Engineering and Prompt Context Architecture
   - Added typed context packs with token budgets, provenance, dropped-item
     diagnostics, and untrusted-content rules for Ask Thesys and research.
3. V1 Sprint 43: Multiple Memory Types and Memory Management
   - Added typed project memory records, workflow-aware memory selection,
     memory explanation APIs, and governed memory indexing.
4. V1 Sprint 44: MCP Adapter and External Tool Integration Boundary
   - Added MCP-shaped HTTP endpoints over the existing governed tool registry,
     preserving approvals, permissions, and audit logs.
5. V1 Sprint 45: Advanced Retrieval Quality and Citation Verification
   - Added shared citation verification and stronger source-diverse context
     selection.
6. V1 Sprint 46: Ask Thesys Streaming, Tool Proposals, and Guide Evals
   - Added guide SSE streaming, proposal-only guide actions for state changes,
     and guide grounding/governance evals.
7. V1 Sprint 47: Observability, Cost Controls, and CI Eval Gates
   - Added AI accounting, budget/circuit checks, `/evals/ai`, and
     `scripts/eval_ai_quality.py`.
8. V1 Sprint 48: External Research and Multimodal Intelligence Hardening
   - Added source provenance helpers, canonical URL/content-hash dedupe, fetch
     failure classification, prompt-injection markers, source quality signals,
     and PDF page lineage.
9. V1 Sprint 49: Codebase Architecture Cleanup
   - Added shared service utilities for metadata merging and workflow run
     finalization, with characterization tests covering evidence and retrieval.
10. V1 Sprint 50: Developer Documentation and Code Navigation
    - Added README updates, developer docs under `docs/`, and concise docstrings
      for context, memory, MCP, provenance, and shared service utilities.

The main homepage and primary project workflow remain straightforward. Advanced
diagnostics, trace details, memory internals, security findings, and retrieval
explanations stay hidden by default and are available through metadata,
inspection surfaces, eval output, or developer docs.
