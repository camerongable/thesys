# V1 Sprints 51-60 TODO

This branch implements V1 Sprint 51 through V1 Sprint 60 sequentially. Each
sprint must end with a focused commit before the next sprint begins.

## Global Rules

- Work in sprint order: 51, 52, 53, 54, 55, 56, 57, 58, 59, then 60.
- Do not skip unfinished acceptance criteria into a later sprint unless the
  implementation brief explicitly assigns that work to the later sprint.
- Keep the homepage and primary project workflow straightforward. Put advanced
  AI internals behind Inspect, workflow traces, eval reports, integration
  settings, or developer docs.
- Run browser-based tests in the IDE browser when a sprint changes user-facing
  workflow, Inspect UI, streaming UI, citation drilldowns, integration settings,
  or dashboard/report surfaces.
- Use subagents for parallelizable research or review work when the scope can be
  isolated without touching the same files concurrently.
- Commit after each completed sprint with a message like
  `Implement V1 Sprint 51 context and memory v2`.

## Standard Verification

- Backend targeted tests: `cd apps/api && .venv/bin/pytest <targeted tests> -q`
- Backend full tests when practical: `cd apps/api && .venv/bin/pytest -q`
- Web tests: `pnpm --filter thesys-web test`
- Web typecheck: `pnpm --filter thesys-web typecheck`
- AI quality eval: `python3 scripts/eval_ai_quality.py --json`
- Research sprint eval: `python3 scripts/eval_research_sprints.py`
- Whitespace/conflict check: `git diff --check` and
  `rg -n "<{7}|={7}|>{7}" .`

## Sprint 51: Unified Context Compiler, Memory V2, and Context Evals

- [x] Build `ContextCompiler` service for domain state, retrieved evidence,
  typed memory, tool outputs, recent turns, validation state, decisions, and
  safety instructions.
- [x] Add explicit context profiles for assumption extraction, Ask Thesys,
  agentic research memos, opportunity briefs, competitor analysis, validation
  planning, validation result interpretation, and decision recommendations.
- [x] Route all major LLM workflows through the shared compiler.
- [x] Add `MemoryManager` policy layer for selection, compaction, conflict
  resolution, preference capture, and memory write-review routing.
- [x] Add approval-gated durable memory compaction with provenance preservation.
- [x] Add explicit preference-memory capture and management.
- [x] Add memory conflict detection and approval-gated keep/supersede/archive/
  merge resolution.
- [x] Add hidden-by-default memory browser/inspector under Inspect.
- [x] Add recommendation-to-memory trace links.
- [x] Add context diff/inspector and context evals for relevant inclusion,
  poisoned-instruction isolation, stale exclusion, citation scoping, and
  dropped-context explanations.
- [x] Run backend context/memory tests and evals.
- [ ] Run IDE browser QA for the memory/context inspector if UI changes are
  included. Blocked so far because `pnpm --filter thesys-web typecheck` fails
  before TypeScript while fetching registry tarballs/supply-chain metadata
  (`ECONNRESET` / `fetch failed`); retry when npm registry access is stable.
- [x] Commit Sprint 51.

## Sprint 52: Real MCP Server and External Agent Harness

- [ ] Add real MCP JSON-RPC lifecycle: `initialize`, `tools/list`,
  `tools/call`, structured errors, request IDs, and capability negotiation.
- [ ] Add stdio transport for local developer agents and streamable HTTP/SSE
  where practical.
- [ ] Generate MCP tool schemas from the governed internal tool registry.
- [ ] Preserve auth, RBAC, approval gates, audit events, redaction, risk levels,
  and project/workspace scoping.
- [ ] Add tested client configs for local Codex/IDE-style clients.
- [ ] Add MCP eval harness for read tools and approval-gated proposal tools.
- [ ] Add contract tests against a real MCP client or SDK.
- [ ] Document MCP capabilities and limits.
- [ ] Run backend MCP tests and security/governance tests.
- [ ] Commit Sprint 52.

## Sprint 53: True Ask Thesys Streaming and Live Tool Events

- [ ] Stream provider tokens or answer deltas before the full answer is ready.
- [ ] Emit retrieval, tool, proposal, cancellation, timeout, and final metadata
  events.
- [ ] Add UI support for progressive answers with collapsed metadata.
- [ ] Add collapsed citation drilldowns for source details, retrieved excerpts,
  verifier status, context item IDs, and memory IDs.
- [ ] Expand guide behavior evals for action routing, weak-evidence behavior,
  no direct mutation, citation validity, cancellation, timeout, and fallback
  parity.
- [ ] Run guide tests, web tests, typecheck, and guide evals.
- [ ] Run IDE browser QA for streaming and citation drilldowns.
- [ ] Commit Sprint 53.

## Sprint 54: Security, Abuse, and Production Auth Hardening

- [ ] Add per-workspace and per-user rate limits for expensive AI workflows.
- [ ] Add max concurrent research sprint and external-search limits.
- [ ] Enforce AI token/cost budgets before expensive provider calls.
- [ ] Add backend and frontend dependency audit scripts.
- [ ] Add CI-friendly security checklist command.
- [ ] Add formal threat model for uploads, URL fetching, model egress, tools,
  Temporal activities, object storage, and multi-tenant access.
- [ ] Add production auth path for JWT/OIDC, workspace membership, API keys,
  service accounts, and stricter dev-auth isolation.
- [ ] Harden SSRF controls for DNS rebinding, content-type allowlists, and
  optional domain deny/allow policy.
- [ ] Add live-provider egress allowlist, timeout, response-size, retry,
  redaction, and audit controls.
- [ ] Run security/governance tests and audit scripts.
- [ ] Commit Sprint 54.

## Sprint 55: Retrieval Quality V2 and Golden Evals

- [ ] Add Postgres full-text search with `tsvector`, phrase/entity matching,
  and ranking combined with vector similarity.
- [ ] Add BM25-like ranking semantics or document the exact Postgres ranking
  approximation and limitations.
- [ ] Add MMR or equivalent diversity selection with source/domain caps.
- [ ] Add cross-encoder-compatible reranker adapter.
- [ ] Add labeled retrieval golden set with positive, negative,
  prompt-injection, stale-source, and competitor/source coverage cases.
- [ ] Apply citation verification across every generated artifact path.
- [ ] Add claim-level citation outcomes to structured artifacts.
- [ ] Block or downgrade unsupported evidence-backed claims before persistence.
- [ ] Add retrieval metrics and CI-ready regression command.
- [ ] Run retrieval, citation, artifact, and eval tests.
- [ ] Commit Sprint 55.

## Sprint 56: Observability V2, CI Gates, and Eval Reports

- [ ] Add OpenTelemetry-compatible metrics/traces for workflow, model,
  retrieval, tool denial, approval wait, token, and cost metrics.
- [ ] Add CI commands for structured output, context, retrieval, guide,
  redaction, security, cost, and citation evals.
- [ ] Add local HTML or Markdown eval reports with failing-case links.
- [ ] Persist eval run summaries for trend comparison.
- [ ] Add eval trend reports by sprint, prompt version, schema version,
  retrieval version, and model/provider mode.
- [ ] Add hidden-by-default dashboard/report surface for AI quality gates.
- [ ] Add prompt, schema, and context-pack version changelog.
- [ ] Add optional LangSmith upload for eval runs.
- [ ] Run eval scripts, backend tests, web checks, and browser QA for dashboard
  surfaces.
- [ ] Commit Sprint 56.

## Sprint 57: Semantic Caching and Cost Optimization

- [ ] Add embedding cache keyed by provider, model, version, and text hash.
- [ ] Add retrieval-plan and rerank-result cache for deterministic repeat
  queries.
- [ ] Add optional semantic cache for Ask Thesys answers keyed by project,
  evidence, memory, prompt, and context-pack versions.
- [ ] Invalidate caches when evidence, memory, thesis, assumptions, decisions,
  or prompt/context versions change.
- [ ] Add cache-hit metrics to AI runs and eval reports.
- [ ] Add tests that prove cache isolation across projects and stale contexts.
- [ ] Run cost/accounting, retrieval, guide, and eval tests.
- [ ] Commit Sprint 57.

## Sprint 58: Source Intelligence and Document AI V2

- [ ] Add readability extraction for fetched HTML.
- [ ] Add optional page screenshot/snapshot capture.
- [ ] Add OCR fallback for scanned PDFs.
- [ ] Add table extraction for PDFs and screenshots.
- [ ] Add section/page-level quote provenance.
- [ ] Add richer source quality scoring for authority, freshness,
  canonical/deduped status, extraction confidence, injection markers, source
  type, domain diversity, OCR, table extraction, and standard text extraction.
- [ ] Add live Tavily and live multimodal QA paths when credentials are
  configured.
- [ ] Run evidence, extraction, provenance, retrieval, and browser document QA.
- [ ] Commit Sprint 58.

## Sprint 59: Feature-Package Backend Refactor

- [ ] Add characterization tests around each workflow before moving code.
- [ ] Split validation planning/result interpretation/decisions.
- [ ] Split agentic research graph/synthesis/citation audit/memory proposals.
- [ ] Split guide routing/grounded generation/proposal routing.
- [ ] Split evidence ingestion/parsing/chunking/retrieval.
- [ ] Split tool definitions/guards/execution/proposal application.
- [ ] Move toward feature packages with shared common AI, retrieval, security,
  and DB code.
- [ ] Add typed internal DTOs for cross-module boundaries.
- [ ] Remove meaningful duplication in prompts, structured-output repair,
  retrieval shaping, audit metadata merging, and proposal creation.
- [ ] Keep public API behavior and persisted schemas unchanged.
- [ ] Run full backend tests, web checks, evals, and targeted browser smoke if
  imports affect UI behavior.
- [ ] Commit Sprint 59.

## Sprint 60: Architecture Docs, Deployment, and Production Readiness

- [ ] Add architecture diagrams for context compilation, memory lifecycle, real
  MCP lifecycle, eval gates, and deployment/security posture.
- [ ] Update developer navigation after Sprint 59 refactor.
- [ ] Add targeted docstrings and comments for public service entrypoints,
  DTOs, invariants, security boundaries, approval gates, Temporal determinism,
  and prompt-injection boundaries.
- [ ] Add deployment documentation and environment profiles.
- [ ] Add production object-storage and backup/restore guidance.
- [ ] Add workspace/team collaboration flows if still aligned with product
  direction.
- [ ] Add multi-project portfolio views only if the single-project workflow
  remains simple.
- [ ] Add advanced integration settings for MCP/API clients, search providers,
  and model providers.
- [ ] Add seeded hosted-demo smoke tests.
- [ ] Run docs checks, full tests/evals, web checks, and browser QA for any
  settings or portfolio UI changes.
- [ ] Commit Sprint 60.
