# V1 Sprints 51-60 TODO

This branch implements V1 Sprint 51 through V1 Sprint 60 sequentially. Each
sprint must end with a focused commit before the next sprint begins.

## Global Rules

- Work in sprint order: 51, 52, 53, 54, 55, 56, 57, 58, 59, then 60.
- Do not skip unfinished acceptance criteria into a later sprint unless the
  implementation brief explicitly assigns that work to the later sprint.
- Treat Sprint 51-60 as gap-closure sprints for Sprint 41-50, not as loose
  wishlist work. Each sprint below names the prior incomplete sprint gap it
  closes and the concrete behavior that must exist before checking the item off.
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

- [x] Close Sprint 42 gaps: centralize context assembly, add workflow context
  profiles, route major LLM workflows through the same compiler, preserve
  provenance, compress older context, detect stale/conflicting context, and add
  local context-quality evals.
- [x] Close Sprint 43 gaps: add compaction, preference capture, conflict
  resolution, memory browser UI, memory proposal review, and memory selection
  inside context packs.
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

- [x] Close Sprint 44 gaps: replace MCP-shaped HTTP-only behavior with a real
  JSON-RPC lifecycle, local stdio bridge, client examples, contract evals, and
  governed tool-call behavior that can be exercised by external agents.
- [x] Add real MCP JSON-RPC lifecycle: `initialize`, `tools/list`,
  `tools/call`, structured errors, request IDs, and capability negotiation.
- [x] Add stdio transport for local developer agents and streamable HTTP/SSE
  where practical.
- [x] Generate MCP tool schemas from the governed internal tool registry.
- [x] Preserve auth, RBAC, approval gates, audit events, redaction, risk levels,
  and project/workspace scoping.
- [x] Add tested client configs for local Codex/IDE-style clients.
- [x] Add MCP eval harness for read tools and approval-gated proposal tools.
- [x] Add contract tests against a real MCP client or SDK.
- [x] Document MCP capabilities and limits.
- [x] Run backend MCP tests and security/governance tests.
- [x] Commit Sprint 52.

## Sprint 53: True Ask Thesys Streaming and Live Tool Events

- [x] Close Sprint 46 gaps: make Ask Thesys streaming incremental, expose live
  retrieval/tool/proposal progress, support cancellation/timeouts, add citation
  drilldowns, and expand guide evals beyond the current SSE-shaped response.
- [x] Stream provider tokens when the configured provider supports streaming;
  otherwise stream deterministic answer deltas from the generated answer before
  emitting the final event so local/dev behavior still proves the UI contract.
- [x] Emit a stable event protocol with at least:
  `message_started`, `context_compiled`, `retrieval_started`,
  `retrieval_result`, `tool_call_started`, `tool_call_completed`,
  `proposal_created`, `answer_delta`, `metadata`, `timeout`, `cancelled`,
  `error`, and `final`.
- [x] Include event payload IDs that let the UI correlate retrieval hits,
  context-pack items, tool invocations, approval requests, memory IDs,
  citation IDs, AI run IDs, and trace IDs.
- [x] Add backend cancellation behavior that stops provider work when the client
  disconnects where practical, records a cancelled AI run/step, and emits or
  persists cancellation metadata without committing state-changing proposals.
- [x] Add backend timeout behavior with configurable timeout limits, a timeout
  event, a safe fallback message, and no partial strategic writes.
- [x] Add UI support for progressive answers while keeping the main Ask Thesys
  flow simple: compact status line, streamed answer body, final action cards,
  and all trace details collapsed by default.
- [x] Add collapsed citation drilldowns for source title, URL/file/page,
  source type, quality signal, retrieved excerpt, verifier status, context item
  IDs, memory IDs, and whether any support was weak/missing/filtered.
- [x] Make streamed and non-streamed responses converge to the same final
  response shape so existing guide consumers do not need separate parsing.
- [x] Expand guide behavior evals for action routing, weak-evidence behavior,
  no direct mutation, citation validity, cancellation, timeout, event ordering,
  malformed-event fallback, and deterministic fallback parity.
- [x] Run backend guide tests, full API tests, compile checks, and AI quality
  evals.
- [ ] Run web tests, web typecheck, and IDE browser QA for streaming and
  citation drilldowns. Blocked in this environment because
  `pnpm --filter thesys-web typecheck` repeatedly failed before TypeScript while
  fetching registry packages and npm attestation metadata (`ECONNRESET`); the
  retrying process was stopped after several minutes.
- [x] Commit Sprint 53.

## Sprint 54: Security, Abuse, and Production Auth Hardening

- [x] Close Sprint 41 gaps: add real quota/concurrency protection, dependency
  audit commands, provider-egress controls, production auth shape, and a formal
  threat model for the concrete attack surfaces already in the repo.
- [x] Close the Sprint 47 pre-call budget gap: enforce token/cost budgets before
  expensive model/search/extraction work starts, not only after AI accounting.
- [x] Add per-workspace and per-user rate limits for expensive workflows:
  research sprint start, source discovery, evidence ingestion/fetching,
  Ask Thesys live-provider calls, opportunity/competitor/validation/decision
  generation, MCP tool calls, and eval/report endpoints.
- [x] Add max concurrent workflow limits for agentic research, external search,
  URL fetches, document extraction/OCR, multimodal extraction, and MCP
  proposal-generating tools.
- [x] Add budget preflight checks that estimate token/cost exposure from model,
  retrieval, rerank, extraction, and search settings; deny or degrade before
  provider calls when workspace/user budgets are exhausted.
- [x] Add backend and frontend dependency audit scripts, with clear local
  commands for Python, Node/pnpm, Docker image/dependency review where
  practical, and documented handling for known false positives.
- [x] Add CI-friendly `security_check` or equivalent command that runs
  dependency audits, redaction checks, SSRF tests, auth/RBAC tests,
  tool-boundary tests, and budget/egress policy tests.
- [x] Add formal threat model docs for uploads, URL fetching, DNS rebinding,
  prompt injection, model egress, tool/MCP access, Temporal activities, object
  storage, database multi-tenancy, auth tokens/API keys, logs/traces, and eval
  artifacts.
- [x] Add production auth path for JWT verification, workspace membership
  enforcement, API keys, service accounts, token rotation/revocation, audit
  attribution, and stricter dev-auth isolation so dev headers cannot be used in
  production mode. OIDC/JWKS is documented as the next production-auth
  hardening step.
- [x] Harden SSRF controls for redirect chains, DNS rebinding re-checks near
  connection time where practical, private/link-local/metadata IP blocks,
  content-type allowlists, max response size, scheme/port policy, and optional
  domain deny/allow lists.
- [x] Add live-provider egress allowlist, timeout, response-size, retry,
  redaction, denied-call audit events, and per-provider policy configuration for
  LLM, embedding, search, extraction, OCR, and multimodal providers.
- [x] Run security/governance tests and audit scripts. Strict dependency audits
  remain environment-limited until `pip-audit` is installed and npm registry
  access stops failing with `ECONNRESET`.
- [x] Commit Sprint 54.

## Sprint 55: Retrieval Quality V2 and Golden Evals

- [ ] Close Sprint 45 gaps: add real text-search ranking, diversity controls,
  swappable reranking, labeled retrieval evals, and consistent citation support
  verification across generated artifacts.
- [ ] Add Postgres full-text search with `tsvector`, phrase/entity matching,
  and ranking combined with vector similarity.
- [ ] Add BM25-like ranking semantics or document the exact Postgres ranking
  approximation and limitations.
- [ ] Add MMR or equivalent diversity selection with source, domain, source
  type, competitor, and recency caps so one source cannot dominate context.
- [ ] Add cross-encoder-compatible reranker adapter with deterministic local,
  LiteLLM/provider, and no-op fallback implementations behind one interface.
- [ ] Add labeled retrieval golden set with positive, negative,
  prompt-injection, stale-source, weak-evidence, competitor/source coverage,
  entity/phrase, and multi-hop project-state cases.
- [ ] Apply citation verification across opportunity briefs, competitor
  analyses, source discovery summaries, agentic research memos, validation
  plans, validation result interpretations, decision recommendations, and Ask
  Thesys answers.
- [ ] Add claim-level citation outcomes to structured artifacts:
  supported, weakly supported, unsupported, source missing, stale source, or
  filtered as unsafe.
- [ ] Block, downgrade, or explicitly label unsupported evidence-backed claims
  before persistence and before showing them as recommendations.
- [ ] Add retrieval metrics for recall@k, precision@k, MRR/nDCG proxy,
  citation support rate, unsupported-claim rate, latency, and cost by retrieval
  mode/provider.
- [ ] Add CI-ready retrieval regression command that runs without provider
  credentials and can optionally compare provider-backed reranking when keys are
  configured.
- [ ] Run retrieval, citation, artifact, and eval tests.
- [ ] Commit Sprint 55.

## Sprint 56: Observability V2, CI Gates, and Eval Reports

- [ ] Close Sprint 47 gaps: turn local accounting/eval checks into repeatable
  gates with traces, metrics, reports, trends, changelogs, and hidden developer
  surfaces.
- [ ] Add OpenTelemetry-compatible metrics/traces for workflow, model,
  retrieval, tool denial, approval wait, token, cost, cache, timeout,
  cancellation, and provider-egress policy metrics.
- [ ] Add CI commands for structured output, context, retrieval, guide,
  redaction, security, cost, citation, MCP contract, and source/document
  extraction evals.
- [ ] Add local HTML or Markdown eval reports with failing-case links, prompt
  version, schema version, context profile, retrieval mode, model/provider mode,
  cost, latency, and trace identifiers.
- [ ] Persist eval run summaries for trend comparison without requiring an
  external observability service.
- [ ] Add eval trend reports by sprint, prompt version, schema version,
  retrieval version, and model/provider mode.
- [ ] Add hidden-by-default dashboard/report surface for AI quality gates that
  shows pass/fail state, recent regressions, budget status, failing-case links,
  and last-run metadata without cluttering the homepage.
- [ ] Add prompt, schema, context-pack, retrieval-policy, memory-policy, and
  tool-schema version changelog.
- [ ] Add optional LangSmith upload/export for eval runs with redaction applied
  before external egress.
- [ ] Run eval scripts, backend tests, web checks, and browser QA for dashboard
  surfaces.
- [ ] Commit Sprint 56.

## Sprint 57: Semantic Caching and Cost Optimization

- [ ] Add the cost/latency upgrade not covered by Sprint 41-50: cache repeated
  AI work while proving cache keys cannot leak data across projects or stale
  contexts.
- [ ] Add embedding cache keyed by provider, model, version, and text hash.
- [ ] Add retrieval-plan and rerank-result cache for deterministic repeat
  queries.
- [ ] Add optional semantic cache for Ask Thesys answers keyed by project,
  workspace, evidence, memory, thesis, prompt, schema, retrieval, and
  context-pack versions.
- [ ] Invalidate caches when evidence, memory, thesis, assumptions, decisions,
  source quality, retrieval settings, tool outputs, provider settings, or
  prompt/context versions change.
- [ ] Add cache-hit, cache-miss, stale-cache-denial, saved-token, saved-cost,
  and latency metrics to AI runs and eval reports.
- [ ] Add tests that prove cache isolation across projects/workspaces, stale
  context invalidation, prompt/schema version invalidation, and no reuse after
  memory or evidence changes.
- [ ] Run cost/accounting, retrieval, guide, and eval tests.
- [ ] Commit Sprint 57.

## Sprint 58: Source Intelligence and Document AI V2

- [ ] Close Sprint 48 gaps: add better extraction for messy web/PDF evidence,
  inspectable page/section provenance, richer source-quality scoring, and live
  provider QA paths when credentials are configured.
- [ ] Add readability extraction for fetched HTML.
- [ ] Add optional page screenshot/snapshot capture with storage limits,
  redaction/egress policy, source metadata, and Inspect-only UI exposure.
- [ ] Add OCR fallback for scanned PDFs with confidence, page numbers,
  extraction method metadata, and graceful deterministic fallback.
- [ ] Add table extraction for PDFs and screenshots, including table text,
  row/column structure where available, page/region provenance, and extraction
  confidence.
- [ ] Add section/page-level quote provenance so generated citations can point
  to exact document pages, sections, table regions, screenshots, or OCR spans.
- [ ] Add richer source quality scoring for authority, freshness,
  canonical/deduped status, extraction confidence, injection markers, source
  type, domain diversity, OCR confidence, table extraction confidence,
  screenshot availability, and standard text extraction quality.
- [ ] Add live Tavily and live multimodal QA paths when credentials are
  configured, with deterministic fallback, egress policy checks, rate limits,
  and eval fixtures that do not require credentials.
- [ ] Run evidence, extraction, provenance, retrieval, and browser document QA.
- [ ] Commit Sprint 58.

## Sprint 59: Feature-Package Backend Refactor

- [ ] Close Sprint 49 gaps: complete the architecture cleanup by splitting
  oversized services, removing duplication, adding typed boundaries, and
  documenting feature ownership without changing public behavior.
- [ ] Add characterization tests around each workflow before moving code:
  evidence ingestion/retrieval, guide chat, research sprint, opportunity brief,
  competitor analysis, validation plan/result interpretation, decision
  recommendation, memory management, MCP tools, and eval endpoints.
- [ ] Split validation planning, validation result interpretation, decision
  recommendations, and shared validation DTOs into cohesive modules.
- [ ] Split agentic research graph construction, state transitions, synthesis,
  citation audit, memory proposal generation, and Temporal-facing adapters.
- [ ] Split guide routing, grounded answer generation, streaming/event protocol,
  proposal routing, and guide eval fixtures.
- [ ] Split evidence ingestion, URL fetching, parsing, chunking, embedding,
  retrieval planning, retrieval execution, reranking, and citation verification.
- [ ] Split tool definitions, permission/risk guards, execution, proposal
  application, MCP schema generation, and audit/redaction helpers.
- [ ] Move toward feature packages with shared common AI, retrieval, security,
  and DB code.
- [ ] Add typed internal DTOs for cross-module boundaries and remove large
  untyped dict payloads where they cross service/package boundaries.
- [ ] Remove meaningful duplication in prompts, structured-output repair,
  retrieval shaping, audit metadata merging, and proposal creation.
- [ ] Keep public API behavior and persisted schemas unchanged.
- [ ] Run full backend tests, web checks, evals, and targeted browser smoke if
  imports affect UI behavior.
- [ ] Commit Sprint 59.

## Sprint 60: Architecture Docs, Deployment, and Production Readiness

- [ ] Close Sprint 50 gaps: add diagrams and post-refactor developer guidance
  that reflect implemented behavior after Sprints 51-59, not aspirational
  architecture.
- [ ] Add architecture diagrams for context compilation, memory lifecycle, real
  MCP lifecycle, eval gates, and deployment/security posture.
- [ ] Update developer navigation after Sprint 59 refactor.
- [ ] Add targeted docstrings and comments for public service entrypoints,
  DTOs, invariants, security boundaries, approval gates, Temporal determinism,
  and prompt-injection boundaries.
- [ ] Add deployment documentation and environment profiles for local,
  deterministic demo, provider-backed demo, staging-like, and production-like
  modes.
- [ ] Add production object-storage and backup/restore guidance for Postgres,
  pgvector embeddings, object storage, eval reports, AI traces, and audit logs.
- [ ] Add workspace/team collaboration flows if still aligned with product
  direction.
- [ ] Add multi-project portfolio views only if the single-project workflow
  remains simple.
- [ ] Add advanced integration settings for MCP/API clients, search providers,
  model providers, OCR/multimodal providers, and egress policy behind
  developer/advanced settings.
- [ ] Add seeded hosted-demo smoke tests for the critical path: project load,
  Ask Thesys, evidence inspection, validation mission, decision recommendation,
  memory/context Inspect, MCP read tool, and eval report.
- [ ] Run docs checks, full tests/evals, web checks, and browser QA for any
  settings or portfolio UI changes.
- [ ] Commit Sprint 60.
