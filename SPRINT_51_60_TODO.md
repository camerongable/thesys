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
- Full AI quality gate: `python3 scripts/eval_quality_gate.py --json`
- Whitespace/conflict check: `git diff --check` and
  `rg -n "<{7}|={7}|>{7}" .`

## Gap Coverage Ledger

This ledger is the handoff contract for the incomplete Sprint 41-50 work. Do
not remove or soften these items unless the work has a code path, docs update,
and verification entry in `IMPLEMENTATION_STATUS.md`.

| Original gap | Owning sprint | Required concrete work |
|---|---|---|
| Sprint 41: real quotas, workflow concurrency, dependency audits, live-provider egress controls, production auth shape, formal threat model | Sprint 54, Sprint 56, Sprint 60 | Sprint 54 implements enforcement and threat-model docs; Sprint 56 turns security checks into repeatable gates/reports with egress and denial metrics; Sprint 60 documents hosted-demo/production posture, auth modes, secrets, backups, and remaining OIDC/JWKS hardening. |
| Sprint 42: central context compiler, workflow profiles, memory-aware context, compression, conflict detection, context-quality evals | Sprint 51, Sprint 56, Sprint 60 | Sprint 51 implements compiler/profiles/memory selection/compression/conflict behavior; Sprint 56 adds context eval gates and trend reports; Sprint 60 documents context architecture and where to add profiles. |
| Sprint 43: memory compaction, explicit preferences, conflict resolution, memory browser, write-review workflow, context-pack integration | Sprint 51, Sprint 60 | Sprint 51 implements memory policy and Inspect surfaces; Sprint 60 documents the memory lifecycle, developer extension points, and any post-refactor code comments/docstrings needed for maintainability. |
| Sprint 44: actual MCP protocol, stdio/SSE transport, real client configs, external harness, governed tool behavior | Sprint 52, Sprint 56, Sprint 60 | Sprint 52 implements JSON-RPC and client examples; Sprint 56 includes MCP contract evals in gates; Sprint 60 documents lifecycle diagrams and advanced integration settings without cluttering the main workflow. |
| Sprint 45: Postgres text ranking/BM25 semantics, diversity/MMR, swappable reranker, golden retrieval evals, artifact-wide citation verification | Sprint 55, Sprint 56, Sprint 57, Sprint 60 | Sprint 55 implements retrieval quality and citation verification; Sprint 56 adds regression gates/reports; Sprint 57 adds retrieval/rerank caching with safe invalidation; Sprint 60 documents retrieval provider/reranker extension points. |
| Sprint 46: real Ask Thesys streaming, cancellation/timeouts, live retrieval/tool/proposal events, citation drilldowns, stronger guide evals | Sprint 53, Sprint 56, Sprint 60 | Sprint 53 implements event protocol and UI; Sprint 56 gates guide behavior and event regressions; Sprint 60 browser-smokes the simple main workflow plus hidden advanced surfaces. |
| Sprint 47: OpenTelemetry, CI gates, eval trend reports, prompt/schema changelog, dashboard/report output, pre-call budget enforcement | Sprint 54, Sprint 56, Sprint 57 | Sprint 54 implements pre-call budget enforcement; Sprint 56 implements metrics, reports, gates, trends, and changelog; Sprint 57 adds cache cost/latency metrics and stale-cache denial coverage. |
| Sprint 48: readability extraction, snapshots, OCR, tables, source-quality scoring, live provider QA | Sprint 58, Sprint 56, Sprint 60 | Sprint 58 implements extraction/provenance/source-quality upgrades; Sprint 56 includes extraction evals in quality gates; Sprint 60 documents provider setup and browser/demo checks. |
| Sprint 49: feature-package refactor, oversized service splits, typed DTOs, characterization tests, layout docs | Sprint 59, Sprint 60 | Sprint 59 refactors behind characterization tests; Sprint 60 updates README navigation, diagrams, docstrings, and developer docs after the code has moved. |
| Sprint 50: diagrams, post-refactor navigation, targeted code docs, deployment/security posture | Sprint 60 | Sprint 60 is not complete until docs match the post-Sprint-59 architecture and explain the portfolio-grade AI engineering story plus practical deployment constraints. |

## Residual Gap Register

These are the remaining pieces called out by the Sprint 41-50 audit that must
still be closed before the branch is considered complete. Keep this list in sync
with the sprint checklists below.

| Gap source | Remaining work | Owning sprint |
|---|---|---|
| Sprint 41 | Strict dependency audits still depend on `pip-audit` being installed and stable npm registry access; hosted-production auth still needs OIDC/JWKS operational docs, token/key rotation runbooks, backup/restore guidance, and hosted-demo smoke verification. | Sprint 56 exposes audit availability as warn/fail gates; Sprint 60 documents and verifies hosted posture. |
| Sprint 42 | Context/compiler behavior is implemented, but memory/context Inspect browser QA was blocked by npm registry errors; docs still need a post-refactor map of context profiles, token budgets, compression, stale/conflict policy, dropped-context explanations, and eval entrypoints. | Sprint 60 |
| Sprint 43 | Memory compaction/preferences/conflicts are implemented, but the memory lifecycle still needs diagrams, developer navigation for adding memory types, docstrings/comments for manager/review APIs, and browser QA for Inspect filters, proposals, selection reasons, and conflict resolution. | Sprint 60 |
| Sprint 44 | MCP JSON-RPC/stdio behavior is implemented, but lifecycle diagrams, client setup docs after the refactor, advanced integration settings, stdio/API smoke commands, and hosted-demo read-tool coverage remain. | Sprint 60 |
| Sprint 45 | Retrieval quality, citation verification, cache-aware retrieval/rerank metrics, and stale-cache denial coverage are implemented; post-refactor docs still need exact provider/reranker extension points, hybrid ranking limits, cache invalidation notes, and citation-verifier ownership. | Sprint 60 |
| Sprint 46 | Ask Thesys streaming/citations are implemented, but web typecheck/tests and IDE browser QA for streaming, cancellation, timeout, event ordering, proposal cards, and citation drilldowns were blocked by npm registry errors. | Sprint 60 |
| Sprint 47 | Observability gates/reports and real cache metrics are implemented; browser QA for the hidden eval report is blocked by npm registry errors, and hosted/CI wiring still needs concrete commands, artifact paths, warn/fail policy, and environment prerequisites. | Sprint 60 |
| Sprint 48 | Current code has security guards, low-text PDF fallback, multimodal boundaries, provenance, and extraction eval gates, but still lacks maintained readability extraction, persisted page/screenshot snapshots, OCR, table extraction, richer source-quality scoring, extraction-provenance citation UI, and live Tavily/multimodal QA fixtures. | Sprint 58 |
| Sprint 49 | Earlier cleanup added shared utilities, but validation, research, guide, evidence/retrieval, tools/MCP, eval/reporting, prompt assembly, structured-output repair, proposal creation, and audit metadata paths still need a feature-package refactor with typed DTO boundaries. | Sprint 59 |
| Sprint 50 | README/docs were improved, but final diagrams, code navigation, docstrings/comments, deployment docs, hosted-demo runbooks, and honest limit notes must be regenerated after Sprints 57-59 land and after deferred browser checks are retried. | Sprint 60 |

## Deferred Verification Items

- Sprint 51 and Sprint 53 web/browser QA was blocked by transient npm registry
  failures (`ECONNRESET` / `fetch failed`). Sprint 60 must retry web typecheck,
  web tests, and IDE browser QA for memory/context Inspect, Ask Thesys
  streaming, and citation drilldowns.
- Sprint 54 strict dependency auditing depends on `pip-audit` availability and
  stable npm registry access. Sprint 56 exposes this as an explicit
  pass/warn/fail gate so it cannot disappear in local-only verification.
- Sprint 56 web/browser QA was also blocked by npm registry failures while
  trying to run the web typecheck/test commands. Sprint 60 must retry the hidden
  eval-report Inspect surface along with the earlier deferred UI checks.
- Any future sprint that changes UI must keep advanced AI internals collapsed or
  behind Inspect/developer settings; the homepage and main validation workflow
  should stay focused on founder decisions, not implementation diagnostics.
- Sprint 57 web verification must also be retried if it remains blocked when
  the cache implementation is committed: AI status tooltip cache posture,
  Evidence retrieval diagnostic cache line, and hidden eval cache metrics should
  be checked with the Sprint 56 report UI.

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

- [x] Close Sprint 45 gaps: add real text-search ranking, diversity controls,
  swappable reranking, labeled retrieval evals, and consistent citation support
  verification across generated artifacts.
- [x] Add Postgres full-text search with `tsvector`, phrase/entity matching,
  and ranking combined with vector similarity.
- [x] Add BM25-like ranking semantics or document the exact Postgres ranking
  approximation and limitations.
- [x] Add MMR or equivalent diversity selection with source, domain, source
  type, competitor, and recency caps so one source cannot dominate context.
- [x] Add cross-encoder-compatible reranker adapter with deterministic local,
  LiteLLM/provider, and no-op fallback implementations behind one interface.
- [x] Add labeled retrieval golden set with positive, negative,
  prompt-injection, stale-source, weak-evidence, competitor/source coverage,
  entity/phrase, and multi-hop project-state cases.
- [x] Apply citation verification across opportunity briefs, competitor
  analyses, source discovery summaries, agentic research memos, validation
  plans, validation result interpretations, decision recommendations, and Ask
  Thesys answers. Current V1 applies full claim verification where cited claims
  exist, and marks non-cited validation artifacts as not applicable.
- [x] Add claim-level citation outcomes to structured artifacts:
  supported, weakly supported, unsupported, source missing, stale source, or
  filtered as unsafe.
- [x] Block, downgrade, or explicitly label unsupported evidence-backed claims
  before persistence and before showing them as recommendations.
- [x] Add retrieval metrics for recall@k, precision@k, MRR/nDCG proxy,
  citation support rate, unsupported-claim rate, latency, and cost by retrieval
  mode/provider.
- [x] Add CI-ready retrieval regression command that runs without provider
  credentials and can optionally compare provider-backed reranking when keys are
  configured.
- [x] Run retrieval, citation, artifact, and eval tests.
- [x] Commit Sprint 55.

## Sprint 56: Observability V2, CI Gates, and Eval Reports

- [x] Close Sprint 47 gaps: turn local accounting/eval checks into repeatable
  gates with traces, metrics, reports, trends, changelogs, and hidden developer
  surfaces.
- [x] Inventory every existing gate/eval command and wire them into one
  CI-ready entrypoint, for example `scripts/eval_quality_gate.py`. The command
  must run or explicitly mark unavailable: structured-output smoke,
  context-quality evals, retrieval golden evals, guide behavior evals,
  citation verification evals, redaction/secret checks, security checks,
  budget/cost checks, MCP contract evals, and source/document extraction evals.
- [x] Add OpenTelemetry-compatible metric names and trace metadata for:
  workflow run count/failure/cancellation, workflow latency, model latency,
  provider name/model/prompt version, retrieval latency/mode/reranker,
  tool denial count and reason, approval wait time, token input/output/total,
  cost estimate, budget denial, cache hit/miss/stale denial, timeout,
  cancellation, and provider-egress allow/deny decisions.
- [x] Persist local eval run summaries under a stable location such as
  `reports/evals/` with JSONL trend data. Each run summary must include sprint,
  git commit when available, timestamp, provider mode, model mode, prompt
  version, schema version, context profile/version, retrieval policy/version,
  memory policy/version, gate status, failed check IDs, latency, token/cost,
  and trace IDs.
- [x] Add local Markdown and HTML reports generated from the same JSON source.
  Reports must include pass/fail/warn status, failing-case links or fixture IDs,
  expected versus actual summaries, prompt/schema/context/retrieval metadata,
  budget/cost values, latency, and instructions for rerunning only the failed
  slice.
- [x] Add trend reports by sprint, prompt version, schema version, context
  profile/version, retrieval version, memory policy version, model/provider
  mode, and git commit. Trends must make regressions obvious, not just append
  raw logs.
- [x] Add hidden-by-default dashboard/report surface for AI quality gates that
  shows pass/fail state, recent regressions, budget status, failing-case links,
  and last-run metadata without cluttering the homepage. Acceptable surfaces:
  Inspect tab, developer-only route, or generated static report linked from
  docs; do not add a new homepage card.
- [x] Add `docs/AI_CHANGELOG.md` or equivalent with versioned entries for
  prompt, schema, context-pack, retrieval-policy, memory-policy, reranker,
  provider, and tool-schema changes. Every entry should explain what changed,
  expected behavior impact, and which evals should catch regressions.
- [x] Add optional LangSmith export/upload for eval runs with secret redaction
  before egress. It must be disabled by default, controlled by configuration,
  and safe in deterministic local mode.
- [x] Add tests for report generation, trend persistence, redaction before
  external export, metric payload shape, unavailable-gate warnings, and API/UI
  access controls for any developer report surface.
- [x] Run the all-gates command, backend eval/report tests, MCP contract tests,
  and security checks.
- [ ] Run web typecheck, web tests, and IDE browser QA for the hidden eval-report
  Inspect UI. Blocked so far because pnpm repeatedly failed before TypeScript
  while fetching registry packages (`ECONNRESET` / `fetch failed`); Sprint 60
  owns the retry with the other deferred UI checks.
- [x] Commit Sprint 56.

## Sprint 57: Semantic Caching and Cost Optimization

- [x] Add the cost/latency upgrade not covered by Sprint 41-50: cache repeated
  AI work while proving cache keys cannot leak data across projects or stale
  contexts.
- [x] Design cache storage and invalidation before writing implementation code.
  Document whether each cache is DB-backed, file-backed, or in-memory, and why
  that choice is acceptable for local demo versus production-like mode.
- [x] Add embedding cache keyed by workspace, provider, model, embedding
  dimension, embedding version, normalization/chunking version, and text hash.
  Cache entries must not store raw secrets or cross workspace/project
  boundaries.
- [x] Add retrieval-plan cache keyed by workspace, project, query text/hash,
  context profile, retrieval settings, evidence corpus version, memory version,
  thesis version, assumption/decision versions, and source-quality policy
  version.
- [x] Add rerank-result cache keyed by candidate chunk IDs plus reranker
  provider/model/version, query hash, retrieval policy version, and score
  normalization version.
- [x] Add optional semantic cache for Ask Thesys answers keyed by project,
  workspace, evidence, memory, thesis, prompt, schema, retrieval, and
  context-pack versions. The V1 implementation covers validated non-streaming
  answers; streaming replay remains intentionally uncached.
- [x] Invalidate caches when evidence, memory, thesis, assumptions, decisions,
  source quality, retrieval settings, tool outputs, provider settings, or
  prompt/context versions change.
- [x] Add explicit stale-cache denial behavior. When a cache key is close but
  invalid because context changed, record the reason and recompute instead of
  silently serving stale results.
- [x] Add configuration to disable semantic answer caching by default in live
  provider mode until correctness evals pass; embedding/retrieval/rerank caches
  may be enabled independently.
- [x] Add cache-hit, cache-miss, stale-cache-denial, saved-token, saved-cost,
  and latency metrics to AI runs and eval reports.
- [x] Wire the new cache metrics into the Sprint 56 eval report service and
  hidden Inspect quality surface so cache regressions are visible without adding
  homepage/dashboard noise.
- [x] Add cache-aware quality-gate checks to `scripts/eval_quality_gate.py`:
  report cache hit/miss/stale-denial counts, saved token/cost estimates,
  isolation failures, and stale-context recomputation cases.
- [x] Add tests that prove cache isolation across projects/workspaces, stale
  context invalidation, prompt/schema version invalidation, and no reuse after
  memory or evidence changes.
- [x] Add eval cases showing equivalent answers with and without safe caches,
  and divergent answers after evidence/memory/thesis changes.
- [x] Run cost/accounting, retrieval, guide, context, and eval tests.
- [x] Commit Sprint 57 after final verification is recorded.

## Sprint 58: Source Intelligence and Document AI V2

- [ ] Close Sprint 48 gaps: add better extraction for messy web/PDF evidence,
  inspectable page/section provenance, richer source-quality scoring, and live
  provider QA paths when credentials are configured.
- [ ] Add readability extraction for fetched HTML using a maintained parser
  such as `trafilatura`, `readability-lxml`, or another explicit dependency.
  Preserve original URL, canonical URL, title, author/date when available,
  extracted text, extraction warnings, and fallback-to-raw-text reason.
- [ ] Route readability extraction through the existing source-ingestion path,
  not a one-off helper. The stored evidence record must identify the raw fetch,
  normalized readability text, parser/version, and fallback path used.
- [ ] Add optional page screenshot/snapshot capture with storage limits,
  redaction/egress policy, source metadata, and Inspect-only UI exposure.
- [ ] Persist snapshot metadata separately from normalized text: capture URL,
  canonical URL, fetched timestamp, content hash, storage key/path, byte size,
  screenshot availability, redaction status, and retention policy.
- [ ] Add OCR fallback for scanned PDFs with confidence, page numbers,
  extraction method metadata, and graceful deterministic fallback.
- [ ] Add a deterministic OCR test double so scanned-PDF behavior can be tested
  without local OCR binaries or live multimodal credentials.
- [ ] Add table extraction for PDFs and screenshots, including table text,
  row/column structure where available, page/region provenance, and extraction
  confidence.
- [ ] Store table artifacts as structured rows/cells plus plain-text summaries
  so retrieval can search them and citation drilldowns can show row/column
  provenance.
- [ ] Add section/page-level quote provenance so generated citations can point
  to exact document pages, sections, table regions, screenshots, or OCR spans.
- [ ] Extend chunk metadata with `extraction_method`, `source_snapshot_id`,
  `page_number`, `section_heading`, `table_id`, `region`, confidence, and quote
  offsets where available.
- [ ] Add richer source quality scoring for authority, freshness,
  canonical/deduped status, extraction confidence, injection markers, source
  type, domain diversity, OCR confidence, table extraction confidence,
  screenshot availability, and standard text extraction quality.
- [ ] Feed source quality into retrieval/context policy as a boost, cap, or
  warning without hiding lower-quality evidence entirely when it is relevant.
- [ ] Extend citation drilldowns and evidence Inspect metadata to show
  extraction method, confidence, page/section/table/region provenance,
  screenshot availability, and source-quality explanation.
- [ ] Add live Tavily and live multimodal QA paths when credentials are
  configured, with deterministic fallback, egress policy checks, rate limits,
  and eval fixtures that do not require credentials.
- [ ] Make live-provider QA opt-in and visibly skipped when credentials or
  egress allowlists are missing. The skip must appear in eval output as a
  warning, not as a silent pass.
- [ ] Add eval fixtures for messy HTML, prompt-injected HTML, scanned PDFs,
  low-text PDFs, table-heavy PDFs, duplicate canonical URLs, stale sources, and
  live-provider-unavailable fallback.
- [ ] Extend `scripts/eval_extraction_quality.py` from structural readiness
  checks into fixture-backed extraction regression cases with expected extracted
  text, provenance spans, source-quality outcomes, and provider-unavailable
  fallback results.
- [ ] Store raw snapshot metadata and normalized extraction artifacts separately
  enough that citations can explain whether a quote came from raw HTML,
  readability text, OCR, a table, a PDF page, or a screenshot region.
- [ ] Update docs/README portfolio language for the implemented document-AI
  stack: extraction methods, provenance model, source-quality scoring,
  deterministic fallbacks, and live-provider limits.
- [ ] Run evidence, extraction, provenance, retrieval, citation, source-quality,
  security-egress, and browser document QA.
- [ ] Commit Sprint 58.

## Sprint 59: Feature-Package Backend Refactor

- [ ] Close Sprint 49 gaps: complete the architecture cleanup by splitting
  oversized services, removing duplication, adding typed boundaries, and
  documenting feature ownership without changing public behavior.
- [ ] Add characterization tests around each workflow before moving code:
  evidence ingestion/retrieval, guide chat, research sprint, opportunity brief,
  competitor analysis, validation plan/result interpretation, decision
  recommendation, memory management, MCP tools, and eval endpoints.
- [ ] Create a target package map before moving files. Expected direction:
  feature packages for `evidence`, `retrieval`, `research`, `guide`,
  `validation`, `decisions`, `memory`, `governance/tools`, `mcp`, and `evals`;
  shared packages only for `common/ai`, `common/db`, `common/security`,
  `common/observability`, and `common/types`.
- [ ] Record the package map in a temporary migration note or architecture doc
  before code movement. For each package, list owned routers, service
  entrypoints, DTOs, models touched, tests, and allowed dependencies.
- [ ] Start with the largest mixed-responsibility modules: split
  `validation_service.py`, `agentic_research_service.py`, `guide_service.py`,
  `tool_service.py`, `retrieval_service.py`, `evidence_service.py`,
  `eval_service.py`, `eval_report_service.py`, and related routers only after
  characterization tests protect their current behavior.
- [ ] Define dependency rules: feature packages may depend on common packages;
  routers call feature service entrypoints; feature packages must not import
  each other through hidden module-level side effects; cross-feature behavior
  uses explicit DTOs or orchestration services.
- [ ] Add or document an import-boundary check for the new package layout. At a
  minimum, run a static import scan that proves feature packages do not create
  circular imports or depend on private modules from sibling features.
- [ ] Split validation planning, validation result interpretation, decision
  recommendations, experiment result parsing, and shared validation DTOs into
  cohesive modules.
- [ ] Split agentic research graph construction, state transitions, tool
  adapters, retrieval orchestration, synthesis, citation audit, memory proposal
  generation, and Temporal-facing adapters.
- [ ] Split guide intent routing, context compilation adapter, grounded answer
  generation, streaming/event protocol, proposal routing, citation drilldowns,
  and guide eval fixtures.
- [ ] Split evidence ingestion, URL fetching, upload parsing, readability/OCR/
  table extraction, chunking, embedding, retrieval planning, retrieval
  execution, reranking, citation verification, and source-quality scoring.
- [ ] Split tool definitions, permission/risk guards, execution, proposal
  application, MCP schema generation, audit events, and redaction helpers.
- [ ] Split eval case loading, gate execution, report generation, trend
  persistence, metric export, and optional LangSmith export.
- [ ] Move script-adjacent eval logic out of ad hoc script helpers where it is
  shared by API routes, local reports, or tests. Keep scripts as thin CLIs over
  package-owned services.
- [ ] Move toward feature packages with shared common AI, retrieval, security,
  and DB code.
- [ ] Add typed internal DTOs for cross-module boundaries and remove large
  untyped dict payloads where they cross service/package boundaries.
- [ ] Define DTOs for context packs, retrieval requests/results, citation
  verification outcomes, guide events, tool execution/proposal outcomes, eval
  gate results, cache diagnostics, and extraction artifacts before replacing the
  existing dict payloads.
- [ ] Remove meaningful duplication in prompts, structured-output repair,
  retrieval shaping, audit metadata merging, and proposal creation.
- [ ] Centralize shared prompt/schema repair behavior in one AI common module
  and keep feature prompts in feature-owned prompt modules.
- [ ] Centralize audit metadata merging and redaction in governance/common code
  so tool, MCP, workflow, eval, and cache paths do not each hand-roll it.
- [ ] Keep migration/model ownership clear. If DB models remain centralized,
  document that choice; if model modules move, preserve Alembic imports and
  avoid circular model imports.
- [ ] Keep public API behavior and persisted schemas unchanged.
- [ ] Run import-cycle checks or an equivalent static inspection after the
  package move.
- [ ] Run full backend tests, web checks, evals, and targeted browser smoke if
  imports affect UI behavior.
- [ ] Update `SPRINT_51_60_TODO.md`, `IMPLEMENTATION_STATUS.md`, README project
  navigation, and code-owner docs with the final package layout before the
  Sprint 59 commit.
- [ ] Commit Sprint 59.

## Sprint 60: Architecture Docs, Deployment, and Production Readiness

- [ ] Close Sprint 50 gaps: add diagrams and post-refactor developer guidance
  that reflect implemented behavior after Sprints 51-59, not aspirational
  architecture.
- [ ] Add architecture diagrams for context compilation, memory lifecycle, real
  MCP lifecycle, eval gates, and deployment/security posture.
- [ ] Context diagram must show workflow profile selection, context item
  sources, memory selection, retrieval results, compression, dropped/stale/
  conflict diagnostics, prompt-injection boundaries, and which service files own
  those steps.
- [ ] Memory diagram must show capture, proposed memory, approval/rejection,
  active memory, compaction, preference updates, conflict groups, supersession,
  archive, audit records, and context-pack links.
- [ ] MCP diagram must show client initialize, capabilities, tool list, tool
  call, RBAC/risk guard, approval-request path, denial/error path, audit event,
  redaction, and stdio versus HTTP/SSE entrypoints.
- [ ] Eval diagram must show local command, individual gates, unavailable-gate
  warnings, JSON/Markdown/HTML artifacts, trend persistence, optional LangSmith
  export, hidden Inspect UI, and CI usage.
- [ ] Deployment/security diagram must show frontend, FastAPI API, Temporal,
  Postgres/pgvector, object storage, provider egress, auth modes, audit logs,
  eval artifacts, backup boundaries, and secret-redaction boundaries.
- [ ] Update developer navigation after Sprint 59 refactor.
- [ ] Add targeted docstrings and comments for public service entrypoints,
  DTOs, invariants, security boundaries, approval gates, Temporal determinism,
  and prompt-injection boundaries.
- [ ] Update README project navigation so an interviewer or new developer can
  find: AI workflow entrypoints, context profiles, memory manager, retrieval
  pipeline, source ingestion/extraction, MCP tools, eval gates/reports,
  security/auth policy, observability, and frontend Inspect surfaces.
- [ ] Add a short "AI engineering tour" for interview prep that maps features to
  patterns and technologies: LangGraph agentic research, LiteLLM gateway,
  Pydantic structured outputs, pgvector/Postgres retrieval, MCP JSON-RPC,
  ContextCompiler/MemoryManager, eval gates/reports, LangSmith/OpenTelemetry
  observability, and governed tool approvals.
- [ ] Build diagrams from implemented code paths, not roadmap intent. Include
  source file references near diagrams so future maintainers can verify them.
- [ ] Add "how to add" docs for a new AI workflow, context profile, memory type,
  MCP tool, retrieval provider, reranker, extractor, eval case, and security
  policy check.
- [ ] Add deployment documentation and environment profiles for local,
  deterministic demo, provider-backed demo, staging-like, and production-like
  modes.
- [ ] For each environment profile, document required env vars, disabled
  provider paths, auth mode, egress posture, cache posture, eval/report
  behavior, object-storage expectation, and commands to verify the profile.
- [ ] Add production-auth notes for JWT/OIDC/JWKS expectations, API-key service
  accounts, token/key rotation, token revocation, dev-auth isolation, and known
  remaining auth limitations.
- [ ] Add production object-storage and backup/restore guidance for Postgres,
  pgvector embeddings, object storage, eval reports, AI traces, and audit logs.
- [ ] Add a dependency-audit runbook covering `pip-audit`, `pnpm audit --prod`,
  non-strict local behavior, strict CI behavior, expected failure modes, and how
  warnings appear in `scripts/security_check.py` and the quality gate.
- [ ] Add workspace/team collaboration flows if still aligned with product
  direction.
- [ ] Add multi-project portfolio views only if the single-project workflow
  remains simple.
- [ ] Add advanced integration settings for MCP/API clients, search providers,
  model providers, OCR/multimodal providers, and egress policy behind
  developer/advanced settings.
- [ ] Keep all advanced settings behind Inspect/developer navigation. Do not add
  new homepage cards, hero sections, or primary-workflow panels for MCP,
  provider, cache, eval, or extraction internals.
- [ ] Add seeded hosted-demo smoke tests for the critical path: project load,
  Ask Thesys, evidence inspection, validation mission, decision recommendation,
  memory/context Inspect, MCP read tool, and eval report.
- [ ] Retry the deferred Sprint 51 and Sprint 53 web checks: web typecheck, web
  tests, IDE browser QA for memory/context Inspect, Ask Thesys streaming,
  cancellation/timeout UI, citation drilldowns, and advanced report/settings
  surfaces.
- [ ] For Sprint 51 browser QA, explicitly exercise memory filters, proposal
  review, conflict resolution, context-pack included/dropped/compressed/stale
  rows, and no clutter in the primary project workflow.
- [ ] For Sprint 53 browser QA, explicitly exercise streamed answer deltas,
  retrieval/tool/proposal events, cancellation, timeout fallback, final metadata
  parity with non-streaming response, action cards, and collapsed citation
  drilldowns.
- [ ] Retry the deferred Sprint 56 web checks: web typecheck, web tests, and IDE
  browser QA for the hidden eval-report Inspect panel, including collapsed gate
  status, trend rows, cache/cost metrics, failing-case links, and no homepage
  clutter.
- [ ] Retry Sprint 57 cache-related web checks if they were not completed at the
  Sprint 57 commit: AI status tooltip cache posture, Evidence retrieval cache
  diagnostic line, hidden eval cache metrics, stale-denial reporting, and no
  new homepage/dashboard clutter.
- [ ] Run and record strict or non-strict security/dependency checks:
  `python3 scripts/security_check.py`, `python3 scripts/audit_dependencies.py`
  where available, `pip-audit` availability, and `pnpm audit --prod` result.
  If registry access blocks a check, record the exact error and next owner.
- [ ] Document remaining honest limits after Sprints 51-60, including any
  provider-only features not exercised in deterministic local mode, OIDC/JWKS
  production-auth gaps, live Tavily/multimodal credential requirements, and
  deployment assumptions.
- [ ] Run docs checks, full tests/evals, web checks, and browser QA for any
  settings or portfolio UI changes.
- [ ] Commit Sprint 60.
