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
- Treat the `G41-*` through `G50-*` work items as the authoritative completion
  ledger. A checked implementation item in Sprint 51-58 means that branch code
  landed; it does not mean the original Sprint 41-50 gap is fully closed unless
  every related `G*` item also has one of the required status values
  (`implemented`, `intentionally out of V1`, or `future owner`) in
  `IMPLEMENTATION_STATUS.md`.
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

## Status Terms

Use these terms consistently in this file, commit notes, and
`IMPLEMENTATION_STATUS.md`:

- **Code-landed** means the implementation slice for that sprint exists on the
  branch and has the recorded local verification.
- **Gap-closed** means every related `G41-*` through `G50-*` item has one of the
  required status values (`implemented`, `intentionally out of V1`, or
  `future owner`), with source/doc links and verification output or exact
  blocker text.
- **Blocked** means the exact command, exact error, retry condition, and next
  owner are recorded under the related `G*` item. A broad note such as "web QA
  blocked" is not enough.

Do not write "close Sprint X gaps" for a checked Sprint 51-58 implementation
item unless every related `G*` item also has a final disposition. Use
"land code for..." for implementation slices that still carry Sprint 60 docs,
browser QA, provider QA, hosted smoke, or final audit work.

## Required Gap Disposition Format

Every `G41-*` through `G50-*` item must receive a concrete row in
`IMPLEMENTATION_STATUS.md` before the branch can claim gap closure. Use this
same shape for every row so the next person can pick up or verify the work
without reverse-engineering prose:

| Field | Required content |
|---|---|
| Gap ID | The exact `G41-*` through `G50-*` ID from this TODO. |
| Status | One of `implemented`, `intentionally out of V1`, or `future owner`. |
| Owner sprint item | The exact `S59-R*` or `S60-P*` item that owns the closeout. |
| Source/doc links | Files, docs, tests, or scripts that prove the disposition. |
| Verification | Exact command and concise result, or the exact command that could not run. |
| Blocker | Exact error, unavailable credential/tool/infrastructure, retry condition, and next owner when not implemented. |
| Portfolio claim | Whether README/portfolio language can claim the capability, must qualify it, or must omit it. |

Do not close a sprint with a vague "documented" or "tested" note. The row must
name the doc section, source owner, command, output/blocker, and portfolio
language consequence.

## Gap Capture Control

A Sprint 41-50 gap is considered captured in this TODO only when all of the
following are true:

- The gap has a stable `G41-*` through `G50-*` ID in `Carried Gap Work Items`.
- The gap appears in `Audit Gap Crosswalk` with an owning `S59-R*` or `S60-P*`
  pickup item and concrete file-level directions.
- The owning Sprint 59 or Sprint 60 queue row names the required artifact,
  source/doc edit target, verification command, and blocker-recording rule.
- `IMPLEMENTATION_STATUS.md` has or will receive a final disposition row using
  the required format above.

If any Sprint 41-50 audit issue is found later and does not satisfy those four
checks, add it here before implementing it. Do not rely on a sprint title,
roadmap paragraph, or checked code-landed item as proof that the gap is captured.

Before any `S59-R*` or `S60-P*` row is checked, verify that the row says exactly
which incomplete Sprint 41-50 gap it closes, which files were changed, which
tests/evals/browser checks prove the result, and which pieces remain
service-owned, intentionally out of V1, or assigned to a future owner. If that
evidence is missing, patch this TODO first, then implement or defer the work.

## Original Sprint 41-50 Gap Patch Manifest

Use this section when resuming the branch. It is the concrete "what is still not
done" patch list for the original Sprint 41-50 goals. The checked code-landed
items later in this file do not close these gaps unless the exact owner below
has produced the named artifact, verification output or blocker, and matching
`IMPLEMENTATION_STATUS.md` disposition rows.

### Sprint 41 Security and Production Posture

Owner: `S60-P9/G41-A` through `G41-E`, deployment docs in `G50-D`, and budget
observability notes in `S60-P7/G47-A` and `G47-C`.

Open first: `docs/DEPLOYMENT_SECURITY.md`, `scripts/security_check.py`,
`scripts/audit_dependencies.py`, auth/security settings, provider-egress guards,
`docs/EVALS_AND_OBSERVABILITY.md`, `README.md`, and
`IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G41-A`: run `python3 scripts/security_check.py`,
  `python3 scripts/audit_dependencies.py`, `pip-audit`, and
  `pnpm audit --prod`; write the exact pass/warn/fail output or unavailable
  tool/registry blocker; state whether strict CI should fail for each warning.
- `G41-B`: add an auth-mode table for local/dev, deterministic demo,
  provider-backed demo, staging-like, and production-like modes, including env
  vars, disabled dev-header behavior, provider credential expectations, and
  verification commands.
- `G41-C`: add JWT verification, OIDC/JWKS expectations, API-key and
  service-account lifecycle, rotation, revocation, audit attribution, workspace
  membership checks, and known V1 auth limits.
- `G41-D`: document provider allowlists, SSRF/provider denial behavior,
  timeout/response-size/retry limits, redaction before egress, and the exact
  tests or smoke commands proving denied calls are audited.
- `G41-E`: document backup/restore boundaries for Postgres/pgvector, object
  storage, eval reports, traces, and audit logs; run or explicitly block hosted
  smokes for project load, evidence, Ask Thesys, validation, decision,
  memory/context Inspect, MCP read tool, and eval report.
- `G47-A`/`G47-C`: include pre-call budget denials in the eval runbook, metric
  names, report examples, and cache/cost observability docs.
- `G50-D`: link the deployment/security doc from README and record the
  environment profile and hosted-demo smoke posture.

Completion bar: every `G41-*` row plus `G50-D` has a final status row with
source/doc links, command output or exact blocker, future owner when deferred,
and README portfolio-claim consequence.

### Sprint 42 Context Engineering

Owner: `S60-P2/G42-A` through `G42-D`.

Open first: `docs/CONTEXT_ENGINEERING.md`,
`apps/api/app/services/context_service.py`, `apps/api/app/features/context/*`,
`apps/api/app/features/memory/context_pack.py`,
`apps/api/app/tests/test_context_compiler.py`, README, and
`IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G42-A`: create the source-linked context architecture doc with profile
  selection, domain state, retrieved evidence, tool outputs, memory,
  compression, stale/conflict checks, dropped rows, prompt-injection boundaries,
  and owner files.
- `G42-B`: add a profile inventory covering every context profile, token
  budget, required/optional item type, memory filter, freshness/staleness
  policy, compression policy, untrusted-content wrapping, and eval coverage.
- `G42-C`: retry IDE browser QA for Context Inspect included, dropped,
  compressed, stale, conflicting, unsafe, and tool-output rows; verify advanced
  context details stay hidden by default, or record the exact npm/browser
  blocker and next owner.
- `G42-D`: document context eval commands, fixture IDs, report paths, expected
  failures, failure interpretation, and steps to add a new context profile and
  eval case.

Verification: run
`cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`,
then web typecheck/tests and browser QA or exact blocker text.

### Sprint 43 Memory Management

Owner: `S60-P3/G43-A` through `G43-D`.

Open first: `docs/MEMORY_SYSTEM.md`,
`apps/api/app/services/memory_service.py`, `apps/api/app/features/memory/*`,
`apps/api/app/tests/test_memory_service.py`,
`apps/api/app/tests/test_context_compiler.py`, README, and
`IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G43-A`: add a memory lifecycle diagram for capture, proposal,
  approval/rejection, active memory, compaction, preferences, conflicts,
  supersession, archive, audit records, and context-pack links.
- `G43-B`: document semantic, episodic, procedural, preference, working,
  project, and any other implemented memory types; include selection policy,
  compaction thresholds, conflict policy, preference edit/archive behavior,
  provenance fields, context eligibility, and owner files.
- `G43-C`: add "how to add a memory type" steps covering schema/service
  changes, review workflow, context-profile eligibility, stale/conflict tests,
  audit behavior, README/status updates, and expected eval coverage.
- `G43-D`: browser-check Memory Inspect filters, proposal review, compaction
  records, selection reasons, conflict keep/supersede/archive/merge actions,
  and hidden-by-default advanced details; record exact blocker if unavailable.
- `G50-C`: after Sprint 59 settles, add useful docstrings/comments around
  memory manager, review, compaction, conflict, and Inspect entrypoints where
  behavior is not obvious.

Verification: run
`cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`,
then browser QA or exact blocker text.

### Sprint 44 MCP Integration

Owner: `S60-P4/G44-A` through `G44-D`.

Open first: `docs/MCP_INTEGRATION.md`, `apps/api/app/mcp/adapter.py`,
`apps/api/app/features/mcp/protocol.py`,
`apps/api/app/features/governance_tools/*`, `scripts/mcp_stdio_server.py`,
MCP/tool tests, README, and `IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G44-A`: add initialize/capability negotiation, `tools/list`, `tools/call`,
  RBAC/risk guard, approval request, denial/error, audit, redaction, stdio, and
  HTTP/SSE lifecycle diagrams.
- `G44-B`: document exact stdio and HTTP/SSE commands, client config, required
  env vars, auth headers, project/workspace scoping, known client limits, and
  post-refactor owner files.
- `G44-C`: run or explicitly block smoke commands for read tools,
  approval-required proposal tools, denied writes, invalid params, missing
  project scope, structured errors, and redacted audit payloads.
- `G44-D`: if settings UI exists or is added, keep it behind developer/advanced
  navigation and browser-check that the homepage and primary workflow are
  unchanged.

Verification: run
`cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_feature_package_boundaries.py -q`,
then live stdio/API read and proposal smokes or exact blocker text.

### Sprint 45 Retrieval and Citation Quality

Owner: `S60-P5/G45-A` through `G45-D`, plus cache docs from Sprint 57 in
`G45-B`.

Open first: `docs/RETRIEVAL_AND_CITATIONS.md`,
`apps/api/app/services/retrieval_service.py`,
`apps/api/app/services/citation_verifier_service.py`,
`apps/api/app/features/retrieval/*`,
`apps/api/app/features/evidence/citation_verifier.py`, retrieval/citation tests,
README, and `IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G45-A`: add a source-linked retrieval pipeline for query planning,
  Postgres text rank, pgvector/vector fallback, hybrid scoring, MMR/source
  diversity, source-quality weighting, reranking, cache lookup/invalidation,
  context assembly, and citation verification.
- `G45-B`: document the BM25-like approximation, Postgres `ts_rank` limits,
  deterministic fallback behavior, reranker provider interface, embedding/
  retrieval-plan/rerank/guide-answer cache keys, invalidation inputs, and steps
  to add retrieval providers or rerankers.
- `G45-C`: add a citation verifier owner matrix for artifact coverage,
  not-applicable paths, weak/unsupported claim handling, downgrade/label
  persistence, and extension steps for new generated artifacts.
- `G45-D`: document golden fixture IDs, commands, metrics, report paths,
  expected pass/warn/fail behavior, and current retrieval/citation output.

Verification: run the retrieval/citation pytest slice named under `S60-P5` and
`python3 scripts/eval_retrieval_quality.py` if present; otherwise record the
exact missing-script disposition and the current replacement command.

### Sprint 46 Ask Thesys Streaming

Owner: `S60-P6/G46-A` through `G46-D`.

Open first: `apps/api/app/services/guide_service.py`,
`apps/api/app/features/guide/*`, Ask Thesys web files under `apps/web`, guide
tests, README, and `IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G46-A`: document stream event names, ordering, payload IDs, final-payload
  parity, cancellation, timeout, error/fallback behavior, proposal/action-card
  fields, citation drilldown fields, and hidden diagnostics.
- `G46-B`: rerun `pnpm --filter thesys-web typecheck` and
  `pnpm --filter thesys-web test`; paste exact pass/fail output or registry
  blocker into `IMPLEMENTATION_STATUS.md`.
- `G46-C`: browser-check provider/deterministic answer deltas, retrieval/tool/
  proposal events, cancellation, timeout fallback, final metadata parity,
  action cards, collapsed citation drilldowns, and no workflow clutter.
- `G46-D`: document guide eval fixture IDs, commands, event-order
  expectations, malformed-event behavior, deterministic fallback parity,
  failure interpretation, and steps for adding a guide case.

Verification: run
`cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`,
then web typecheck/tests and IDE browser QA or exact blocker text.

### Sprint 47 Observability, Cost Controls, and Eval Gates

Owner: `S60-P7/G47-A` through `G47-D`, with Sprint 54 budget denial and Sprint
57 cache metric carry-forwards.

Open first: `docs/EVALS_AND_OBSERVABILITY.md`,
`scripts/eval_quality_gate.py`, `apps/api/app/services/eval_report_service.py`,
`apps/api/app/features/evals/*`, hidden report UI files, README, and
`IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G47-A`: document aggregate and per-gate commands, pass/warn/fail policy,
  unavailable-gate handling, artifact paths, rerun-only-failed-slice commands,
  cache-quality gates, budget-denial checks, and CI usage.
- `G47-B`: document JSON/Markdown/HTML report locations, JSONL trend
  persistence, metadata fields, prompt/schema/context/retrieval/memory/tool
  changelog locations, and regression interpretation.
- `G47-C`: document OpenTelemetry-compatible metric names, LangSmith export
  settings, redaction behavior, trace IDs, local versus external export
  behavior, cache hit/miss/stale-denial counts, saved token/cost/latency
  examples, and budget denial metrics.
- `G47-D`: browser-check hidden eval-report Inspect state, collapsed gate
  details, trend rows, failing-case links, budget/cache/cost metrics, and no
  homepage/dashboard clutter; record exact blocker if unavailable.

Verification: run
`THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60 LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json`
or record exact unavailable gates/blockers, plus focused eval-report tests and
browser QA or exact blocker text.

### Sprint 48 Source and Document Intelligence

Owner: `S60-P8/G48-A` through `G48-E`.

Open first: `docs/SOURCE_INTELLIGENCE.md`, source ingestion/extraction services,
provenance UI files, `scripts/eval_extraction_quality.py`, README, and
`IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G48-A`: decide whether to add `trafilatura`/`readability-lxml` or document
  deterministic `html.parser` as the V1 fallback; include parser/version/
  confidence metadata and productization tradeoffs.
- `G48-B`: decide whether true page/screenshot artifact capture with storage
  keys, retention, and redaction belongs in V1; if not, create a named future
  backlog item and keep README/status honest that local V1 is metadata-only.
- `G48-C`: implement screenshot-region OCR/table provenance only if screenshot
  capture lands; otherwise mark it out of V1 with reason, future owner, and
  dependency on `G48-B`.
- `G48-D`: run opt-in Tavily and multimodal provider smoke tests with
  credentials, provider mode, rate limits, and egress allowlists, or record
  unavailable warnings and rerun commands.
- `G48-E`: browser-check Evidence Inspect, retrieval provenance, Ask Thesys
  citation drilldowns, research memo citations, source-discovery provenance,
  Project Inspect trust summaries, provider warnings, and no workflow clutter.

Verification: run `python3 scripts/eval_extraction_quality.py --json`, live
provider smokes or exact blockers, web typecheck/tests, and provenance browser
QA or exact blocker text.

### Sprint 49 Codebase Architecture Cleanup

Owner: `S59-R1` through `S59-R10`, closing `G49-A` through `G49-E`.

Open first: `docs/BACKEND_FEATURE_PACKAGE_MAP.md`,
`apps/api/app/features/*`, `apps/api/app/common/*`, touched services,
`apps/api/app/tests/test_feature_package_boundaries.py`,
`apps/api/app/tests/test_contract_shapes.py`, this TODO, README, and
`IMPLEMENTATION_STATUS.md`.

Patch exactly:

- `G49-A`: keep the characterization matrix current before every risky move.
  Each row needs service path, feature target, route/API shape pinned by tests,
  focused pytest command, and known unpinned edge cases.
- `G49-B`: for every mixed-responsibility service, move pure helpers into
  feature packages or explicitly record service-owned orchestration. Required
  targets are evidence, retrieval, validation, research, guide, tools/MCP,
  eval/reporting, context, memory, prompt/schema repair, proposal creation, and
  audit metadata.
- `G49-C`: maintain DTO ledger rows for context packs, retrieval requests/
  results, citations, guide events, tool outcomes/proposals, eval gates/reports,
  cache diagnostics, extraction artifacts, memory selections, and decision
  recommendations.
- `G49-D`: centralize only duplication protected by tests: prompt/schema repair,
  retrieval shaping, citation/provenance shaping, audit metadata merge/redaction,
  proposal/action-card creation, Markdown rendering, and fallback completion
  metadata.
- `G49-E`: maintain the shim/migration ledger with old import path, new module,
  shim type, parity test, boundary-check result, temporary/permanent status,
  and cleanup follow-up.

Verification: run each focused `S59-R*` command, `python3 scripts/check_feature_boundaries.py`,
ruff, compileall, `git diff --check`, conflict scan, and the full backend suite
when practical. Do not commit Sprint 59 while a moved helper lacks a ledger row.

### Sprint 50 Developer Docs and Readiness

Owner: `S60-P10/G50-A` through `G50-E`, with deployment `G50-D` also owned by
`S60-P9`.

Open first: README, `IMPLEMENTATION_STATUS.md`, docs under `docs/`,
`docs/BACKEND_FEATURE_PACKAGE_MAP.md`, and public service/DTO entrypoints after
Sprint 59 settles.

Patch exactly:

- `G50-A`: add source-linked diagrams for context, memory, MCP, eval gates,
  retrieval, source intelligence, and deployment/security with owner file
  references.
- `G50-B`: update README navigation and AI engineering tour so interviewers can
  map features to patterns/technologies and developers can find workflows,
  context, memory, retrieval, source ingestion, MCP, evals, security,
  observability, and Inspect entrypoints.
- `G50-C`: add targeted docstrings/comments for public service entrypoints,
  DTOs, approval gates, Temporal determinism, security boundaries,
  prompt-injection boundaries, and non-obvious orchestration only.
- `G50-D`: add environment profiles, env var tables, provider/cache/auth/egress
  posture, object-storage expectations, backup/restore guidance, hosted-demo
  smoke commands, and audit commands.
- `G50-E`: run the final honest-limit audit. Every `G41-*` through `G50-*` item
  must be `implemented`, `intentionally out of V1`, or `future owner`; README
  claims must be removed or qualified when code/tests/evals/docs are missing.

Verification: Sprint 60 is complete only when every gap has exactly one final
disposition row, README links all new docs, deferred browser/provider/audit
blockers are exact, and portfolio language matches verified implementation.

## No-Ambiguity Sprint Pickup Contract

Use this table first when picking up the branch. It turns each follow-up sprint
into an explicit gap ticket so the remaining Sprint 41-50 work cannot disappear
behind a broad sprint title. A follow-up sprint is not complete until the named
`G*` IDs have source/doc links, verification output or exact blockers, and a
final disposition row in `IMPLEMENTATION_STATUS.md`.

| Follow-up sprint | Original gap IDs it must dispose | Open these files first | Required patch before completion | Required verification/disposition |
|---|---|---|---|---|
| Sprint 51 code-landed closeout | `G42-A` through `G42-D`, `G43-A` through `G43-D` | `apps/api/app/services/context_service.py`, `apps/api/app/services/memory_service.py`, `apps/api/app/features/memory/*`, `docs/CONTEXT_ENGINEERING.md`, `docs/MEMORY_SYSTEM.md`, `README.md` | Do not reopen Sprint 51 code unless tests prove missing behavior. Finish the docs/status/QA handoff through `S60-P2` and `S60-P3`: profile inventory, token budgets, selected/dropped/compressed/stale/conflict examples, memory type inventory, proposal/review lifecycle, compaction/conflict behavior, extension steps, and Inspect hidden-by-default notes. | Run context/memory tests listed under `S60-P2`/`S60-P3`; retry browser QA for Context/Memory Inspect rows, or record the exact npm/browser blocker and next owner. Add one status row per `G42-*` and `G43-*` ID. |
| Sprint 52 code-landed closeout | `G44-A` through `G44-D` | `apps/api/app/mcp/adapter.py`, `apps/api/app/features/mcp/protocol.py`, `apps/api/app/features/governance_tools/*`, `scripts/mcp_stdio_server.py`, `docs/MCP_INTEGRATION.md`, `README.md` | Finish the MCP handoff through `S60-P4`: lifecycle diagram, stdio and HTTP/SSE commands, client config, auth/project scoping, approval-required proposal example, denied write/error examples, redacted audit examples, known limits, and advanced settings placement. | Run MCP/tool tests; run or explicitly block stdio/API read and proposal smokes; add one status row per `G44-*` ID, including exact output/blocker. |
| Sprint 53 code-landed closeout | `G46-A` through `G46-D` | `apps/api/app/services/guide_service.py`, `apps/api/app/features/guide/*`, Ask Thesys web files under `apps/web`, `README.md` | Finish the Ask Thesys handoff through `S60-P6`: stream event contract, event ordering, final-payload parity, cancellation/timeout behavior, retrieval/tool/proposal events, action-card fields, citation drilldown fields, guide eval handoff, and hidden diagnostics. | Run guide/context tests, web typecheck/tests, and IDE browser QA for deltas/events/cancel/timeout/citations; if web deps fail, record exact registry/browser blocker. Add one status row per `G46-*` ID. |
| Sprint 54 code-landed closeout | `G41-A` through `G41-E`, deployment portion of `G50-D`, budget pieces of `G47-A`/`G47-C` | `docs/DEPLOYMENT_SECURITY.md`, `scripts/security_check.py`, `scripts/audit_dependencies.py`, auth/security settings, provider egress guards | Finish security/deployment through `S60-P9`: dependency audit disposition, auth-mode table, JWT/OIDC/JWKS and API-key/service-account runbooks, rotation/revocation, provider egress/SSRF denial behavior, backup/restore boundaries, hosted-demo smoke checklist, and budget-denial observability notes. | Run or block `python3 scripts/security_check.py`, `python3 scripts/audit_dependencies.py`, `pip-audit`, `pnpm audit --prod`, and hosted smokes. Add one status row per `G41-*` ID and the relevant `G50-D` disposition. |
| Sprint 55 code-landed closeout | `G45-A` through `G45-D` | `apps/api/app/services/retrieval_service.py`, `apps/api/app/services/citation_verifier_service.py`, `apps/api/app/features/retrieval/*`, `apps/api/app/features/evidence/citation_verifier.py`, `docs/RETRIEVAL_AND_CITATIONS.md` | Finish retrieval/citation docs through `S60-P5`: pipeline diagram, Postgres text-rank/BM25-like limits, pgvector fallback, hybrid scoring, MMR/source diversity, source-quality weighting, reranker/provider extension points, cache invalidation, citation verifier owner matrix, unsupported/weak-claim handling, and golden eval handoff. | Run retrieval/citation tests and eval commands; record limitations honestly. Add one status row per `G45-*` ID. |
| Sprint 56 code-landed closeout | `G47-A` through `G47-D` | `scripts/eval_quality_gate.py`, `apps/api/app/services/eval_report_service.py`, `apps/api/app/features/evals/*`, `docs/EVALS_AND_OBSERVABILITY.md`, hidden report UI files | Finish eval/observability through `S60-P7`: aggregate/per-gate commands, pass/warn/fail policy, unavailable-gate policy, report/trend paths, rerun commands, changelog locations, metric names, LangSmith settings, redaction, cache/cost examples, CI usage, and hidden report QA. | Run quality gate with recorded output; run focused eval-report tests; retry hidden report browser QA or record exact blocker. Add one status row per `G47-*` ID. |
| Sprint 57 code-landed closeout | cache portions of `G45-B`, `G47-A`, `G47-C`, `G47-D` | cache helpers/services, retrieval/guide cache tests, `docs/RETRIEVAL_AND_CITATIONS.md`, `docs/EVALS_AND_OBSERVABILITY.md` | Finish cache documentation through `S60-P5` and `S60-P7`: cache keys, versioned invalidation inputs, stale-cache denial behavior, project/workspace isolation, saved token/cost/latency metrics, report surfacing, and hidden diagnostics. | Run cache-focused backend tests/evals named in the owning sprint rows; retry cache UI/browser checks or record exact blocker. Update the related `G45-*`/`G47-*` rows. |
| Sprint 58 code-landed closeout | `G48-A` through `G48-E` | source ingestion/extraction services, provenance UI files, `scripts/eval_extraction_quality.py`, `docs/SOURCE_INTELLIGENCE.md`, `README.md` | Finish source-intelligence dispositions through `S60-P8`: parser dependency decision, true page/screenshot storage decision, screenshot-region OCR/table scope, live Tavily/multimodal provider QA or unavailable warnings, Project Inspect trust summary, provenance field inventory, and browser provenance QA. | Run extraction eval; run or block Tavily/multimodal smoke; retry web/browser provenance checks. Add one status row per `G48-*` ID with portfolio-claim impact. |
| Sprint 59 refactor closeout | `G49-A` through `G49-E` | `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, `apps/api/app/features/*`, `apps/api/app/common/*`, touched services, `apps/api/app/tests/test_feature_package_boundaries.py`, `apps/api/app/tests/test_contract_shapes.py` | Finish `S59-R1` through `S59-R10`: add characterization before movement, move pure helpers or record service-owned side effects, maintain DTO/shim ledgers, centralize only tested duplication, run boundary checks, and update README/status/brief/TODO/package map before commit. | Run the focused `S59-R*` commands, full backend suite when practical, ruff, compileall, `python3 scripts/check_feature_boundaries.py`, `git diff --check`, and conflict scan. Add one status row per `G49-*` ID. |
| Sprint 60 final closeout | all remaining `G41-*` through `G50-*` | `IMPLEMENTATION_STATUS.md`, `README.md`, all docs under `docs/`, final source docstring targets | Complete `S60-P1` through `S60-P10` in order. Create the final disposition table first, then write/link docs, retry or block provider/browser/audit checks, add targeted code docs, update the AI engineering tour, and remove or qualify unsupported portfolio claims. | Sprint 60 is complete only when every `G*` ID appears exactly once in `IMPLEMENTATION_STATUS.md` with status, owner, source/doc link, verification/blocker, future owner when deferred, and portfolio-claim consequence. |

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
| Sprint 47: OpenTelemetry, CI gates, eval trend reports, prompt/schema changelog, dashboard/report output, pre-call budget enforcement | Sprint 54, Sprint 56, Sprint 57, Sprint 60 | Sprint 54 implements pre-call budget enforcement; Sprint 56 implements metrics, reports, gates, trends, and changelog; Sprint 57 adds cache cost/latency metrics and stale-cache denial coverage; Sprint 60 documents CI/runbook, browser QA, and hosted/CI wiring details. |
| Sprint 48: readability extraction, snapshots, OCR, tables, source-quality scoring, live provider QA | Sprint 58, Sprint 56, Sprint 60 | Sprint 58 must replace the current structural-only readiness with real extraction/provenance/source-quality behavior and fixture-backed evals; Sprint 56 quality gates must consume those evals as pass/warn/fail instead of substring checks; Sprint 60 must document provider setup and browser/demo checks without claiming unverified live-provider coverage. |
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
| Sprint 48 | Sprint 58 now covers the local document-intelligence path: parser/readability metadata, snapshot metadata with explicit local storage absence, deterministic OCR metadata, deterministic table artifacts, quote offsets, source-quality factors/explanations, retrieval weighting, enriched citations, collapsed provenance UI, and fixture-backed extraction evals. Remaining carried gaps are explicit: decide whether to add a maintained parser dependency or document the deterministic parser as the V1 fallback; add true page/screenshot artifact capture and object-storage persistence if productizing beyond metadata; run live Tavily and live multimodal credential QA; retry web typecheck/browser QA for provenance disclosures; verify Project Inspect trust summaries after web deps are available. | Sprint 60 for docs/QA/final audit; future backlog only for items given an `intentionally out of V1` or `future owner` disposition. |
| Sprint 49 | Earlier cleanup added shared utilities, but validation, research, guide, evidence/retrieval, tools/MCP, eval/reporting, prompt assembly, structured-output repair, proposal creation, and audit metadata paths still need a feature-package refactor with typed DTO boundaries. | Sprint 59 |
| Sprint 50 | README/docs were improved, but final diagrams, code navigation, docstrings/comments, deployment docs, hosted-demo runbooks, and honest limit notes must be regenerated after Sprints 57-59 land and after deferred browser checks are retried. | Sprint 60 |

## Audit Gap Crosswalk

This is the pickup map for the Sprint 41-50 audit. Every unfinished objective
from that audit must appear here, in the carried gap list, and in the Sprint 60
final disposition table before the branch can claim full gap closure. If a
future implementer finds another unfinished audit item, add a row here first,
then add the matching sprint checklist entry.

| Original unfinished objective | Gap ID | Pickup item | Concrete pickup directions |
|---|---|---|---|
| Sprint 41 strict dependency audits | `G41-A` | `S60-P9` | Run `scripts/security_check.py`, `scripts/audit_dependencies.py`, `pip-audit`, and `pnpm audit --prod`; record exact output, unavailable-tool behavior, registry failures, and strict-CI policy in `IMPLEMENTATION_STATUS.md` and `docs/DEPLOYMENT_SECURITY.md`. |
| Sprint 41 hosted-demo auth posture | `G41-B` | `S60-P9` | Add the auth-mode table covering local/dev, deterministic demo, provider-backed demo, staging-like, and production-like modes; include required env vars, disabled dev-header behavior, provider credential expectations, and verification commands. |
| Sprint 41 production auth runbook | `G41-C` | `S60-P9` | Document JWT verification, OIDC/JWKS expectations, API-key/service-account lifecycle, rotation, revocation, audit attribution, workspace membership checks, and V1 auth limitations. |
| Sprint 41 live-provider egress proof | `G41-D` | `S60-P9` | Document provider allowlists, SSRF/provider denial behavior, timeout/response-size/retry limits, redaction-before-egress rules, and exact tests or smoke commands proving denied calls are audited. |
| Sprint 41 backup/restore and hosted smoke | `G41-E` | `S60-P9` | Document backup boundaries for Postgres/pgvector, object storage, eval reports, traces, and audit logs; run or explicitly block hosted smokes for project load, evidence, Ask Thesys, validation, decision, Inspect, MCP read tool, and eval report. |
| Sprint 42 context architecture explanation | `G42-A` | `S60-P2` | Create `docs/CONTEXT_ENGINEERING.md` with source-linked context diagrams for profile selection, domain state, retrieval, memory, tool outputs, compression, stale/conflict checks, dropped rows, prompt-injection boundaries, and owner files. |
| Sprint 42 context profile inventory | `G42-B` | `S60-P2` | Document every context profile, token budget, required/optional item type, memory filter, freshness/staleness policy, compression policy, untrusted-content rule, and eval coverage. |
| Sprint 42 Context Inspect browser QA | `G42-C` | `S60-P2` | Retry IDE browser QA for included, dropped, compressed, stale, conflicting, unsafe, and tool-output context rows; verify advanced details are hidden by default or record exact browser/npm blocker and owner. |
| Sprint 42 context eval handoff | `G42-D` | `S60-P2` | Document context eval commands, fixture IDs, report paths, expected failures, failure interpretation, and exact steps to add a context profile and eval case. |
| Sprint 43 memory lifecycle explanation | `G43-A` | `S60-P3` | Create `docs/MEMORY_SYSTEM.md` with a source-linked lifecycle diagram for capture, proposal, approval/rejection, active memory, compaction, preferences, conflicts, supersession, archive, audit records, and context-pack links. |
| Sprint 43 memory type inventory | `G43-B` | `S60-P3` | Document semantic, episodic, procedural, preference, working, project, and any other implemented memory types; include selection policy, compaction thresholds, conflict policy, preference edit/archive behavior, provenance fields, context eligibility, and owner files. |
| Sprint 43 memory extension path | `G43-C` | `S60-P3` | Add "how to add a memory type" steps covering schema/service changes, review workflow, context-profile eligibility, stale/conflict tests, audit behavior, README/status updates, and expected eval coverage. |
| Sprint 43 Memory Inspect browser QA | `G43-D` | `S60-P3` | Browser-check filters, proposal review, compaction records, selection reasons, conflict keep/supersede/archive/merge actions, and hidden-by-default advanced details; record exact blocker if browser/web checks cannot run. |
| Sprint 44 MCP lifecycle explanation | `G44-A` | `S60-P4` | Add `docs/MCP_INTEGRATION.md` diagrams for initialize/capability negotiation, `tools/list`, `tools/call`, RBAC/risk guard, approval request, denial/error, audit, redaction, stdio, and HTTP/SSE paths. |
| Sprint 44 MCP client setup | `G44-B` | `S60-P4` | Document exact stdio and HTTP/SSE commands, example client config, required env vars, auth headers, project/workspace scoping, known client limits, and post-refactor owner files. |
| Sprint 44 MCP smoke evidence | `G44-C` | `S60-P4` | Run or explicitly block smoke commands for read tools, approval-required proposal tools, denied writes, invalid params, missing project scope, structured errors, and redacted audit payloads. |
| Sprint 44 integration settings placement | `G44-D` | `S60-P4` | If settings UI exists or is added, keep it behind developer/advanced navigation and browser-check that the homepage and primary project workflow are unchanged. |
| Sprint 45 retrieval architecture docs | `G45-A` | `S60-P5` | Create `docs/RETRIEVAL_AND_CITATIONS.md` with a source-linked pipeline for query planning, Postgres text rank, pgvector/vector fallback, hybrid scoring, MMR/source diversity, source-quality weighting, reranking, cache lookup/invalidation, context assembly, and citation verification. |
| Sprint 45 ranking limits and extension docs | `G45-B` | `S60-P5` | Document the exact BM25-like approximation, Postgres `ts_rank` limits, deterministic fallback behavior, reranker provider interface, cache invalidation inputs, and how to add retrieval providers or rerankers. |
| Sprint 45 citation verifier ownership | `G45-C` | `S60-P5` | Add an artifact-type matrix for verifier coverage, not-applicable paths, weak/unsupported claim handling, downgraded/labeled persistence behavior, and extension steps for new generated artifacts. |
| Sprint 45 retrieval/citation eval handoff | `G45-D` | `S60-P5` | Document golden fixture IDs, commands, metrics, report paths, expected pass/warn/fail behavior, and current retrieval/citation verification output. |
| Sprint 46 streaming event contract | `G46-A` | `S60-P6` | Document Ask Thesys stream events, ordering, payload IDs, final-payload parity, cancellation, timeout, error/fallback behavior, proposal/action-card fields, citation drilldown fields, and hidden diagnostics. |
| Sprint 46 web checks | `G46-B` | `S60-P6` | Rerun `pnpm --filter thesys-web typecheck` and `pnpm --filter thesys-web test`; paste exact pass/fail output or registry blocker into `IMPLEMENTATION_STATUS.md`. |
| Sprint 46 Ask Thesys browser QA | `G46-C` | `S60-P6` | Browser-check provider/deterministic answer deltas, retrieval/tool/proposal events, cancellation, timeout fallback, final metadata parity, action cards, collapsed citation drilldowns, and no workflow clutter. |
| Sprint 46 guide eval handoff | `G46-D` | `S60-P6` | Document guide eval fixture IDs, commands, event-order expectations, malformed-event behavior, deterministic fallback parity, failure interpretation, and steps for adding a guide case. |
| Sprint 47 quality-gate runbook | `G47-A` | `S60-P7` | Create `docs/EVALS_AND_OBSERVABILITY.md` with aggregate/per-gate commands, pass/warn/fail policy, unavailable-gate policy, artifact paths, failed-slice rerun commands, and CI usage. |
| Sprint 47 report/trend docs | `G47-B` | `S60-P7` | Document JSON/Markdown/HTML report locations, JSONL trend persistence, metadata fields, prompt/schema/context/retrieval/memory/tool changelog locations, and regression interpretation. |
| Sprint 47 observability setup | `G47-C` | `S60-P7` | Document OpenTelemetry metric names, LangSmith settings, redaction behavior, cache/cost examples, trace IDs, pre-call budget denial metrics, and local versus external export behavior. |
| Sprint 47 eval report browser QA | `G47-D` | `S60-P7` | Browser-check hidden eval-report Inspect state, collapsed gate details, trend rows, failing-case links, budget/cache/cost metrics, and no homepage/dashboard clutter, or record exact blocker. |
| Sprint 48 parser dependency decision | `G48-A` | `S60-P8` | Decide whether to add a maintained readability dependency or document deterministic `html.parser` as V1 fallback; include parser/version/confidence metadata and productization tradeoffs. |
| Sprint 48 page/screenshot storage decision | `G48-B` | `S60-P8` | Decide whether true page/screenshot artifact capture with storage keys, retention, and redaction belongs in V1; if not, create a named future backlog item and keep README/status honest that local V1 is metadata-only. |
| Sprint 48 screenshot-region OCR/table scope | `G48-C` | `S60-P8` | Implement screenshot-region OCR/table provenance only if screenshot capture lands; otherwise mark it out of V1 with reason, future owner, and dependency on `G48-B`. |
| Sprint 48 live provider QA | `G48-D` | `S60-P8` | Run opt-in Tavily and multimodal provider smoke tests with credentials, provider mode, rate limits, and egress allowlists, or record unavailable warnings and rerun commands. |
| Sprint 48 provenance browser QA | `G48-E` | `S60-P8` | Browser-check Evidence Inspect, retrieval provenance, Ask Thesys citation drilldowns, research memo citations, source-discovery provenance, Project Inspect trust summaries, provider warnings, and no workflow clutter. |
| Sprint 49 characterization before risky moves | `G49-A` | `S59-R1` through `S59-R10` | Add focused tests before moving evidence/retrieval, guide, research, opportunity/competitor, validation, decisions, memory, MCP/tools, eval, structured-output, and context-profile behavior. |
| Sprint 49 feature-package movement | `G49-B` | `S59-R1` through `S59-R10` | Move pure helpers into feature packages or explicitly mark orchestration as service-owned for validation, research, guide, evidence/retrieval, tool/MCP, eval/reporting, prompt repair, proposal creation, and audit metadata. |
| Sprint 49 DTO boundary ledger | `G49-C` | `S59-R1` through `S59-R10` | Keep `docs/BACKEND_FEATURE_PACKAGE_MAP.md` current for context pack, retrieval, citation, guide event, tool outcome, eval gate, cache diagnostic, extraction, proposal, audit, and fallback metadata shapes. |
| Sprint 49 duplication cleanup | `G49-D` | `S59-R9` | Centralize only tested shared behavior in prompt/schema repair, retrieval shaping, audit metadata merge/redaction, fallback completion metadata, and proposal/action-card creation without changing public API shapes. |
| Sprint 49 migration evidence | `G49-E` | `S59-R10` | Record compatibility shims, target feature modules, parity tests, dependency-boundary check output, centralized model ownership decisions, intentionally centralized services, and future cleanup backlog. |
| Sprint 50 source-linked diagrams | `G50-A` | `S60-P10` | Add diagrams for context, memory, MCP, eval gates, retrieval, and deployment/security with source file references and post-refactor owner packages. |
| Sprint 50 README navigation and AI tour | `G50-B` | `S60-P10` | Update README so an interviewer can map features to AI patterns/technologies and a developer can find workflow, context, memory, retrieval, source-ingestion, MCP, eval, security, observability, and Inspect entrypoints. |
| Sprint 50 targeted code documentation | `G50-C` | `S60-P10` | Add useful docstrings/comments around public service entrypoints, DTOs, approvals, Temporal invariants, security boundaries, prompt-injection boundaries, and non-obvious orchestration logic after Sprint 59 settles. |
| Sprint 50 deployment docs | `G50-D` | `S60-P9` and `S60-P10` | Add environment profiles, env var tables, provider/cache/auth/egress posture, object-storage expectations, backup/restore guidance, hosted-demo smoke commands, and audit commands. |
| Sprint 50 honest-limit audit | `G50-E` | `S60-P1` and `S60-P10` | Update README/status so every Sprint 41-50 gap is implemented, intentionally out of V1 with reason, or still open with a future owner; remove or qualify unsupported portfolio claims. |

## Per-Sprint Completion Gates

Use this table before marking any Sprint 51-60 work complete. The left side
states what has landed; the right side states the remaining gap closure that
must be picked up. A sprint title is not completion evidence.

| Sprint | Current gap status | Required pickup before claiming complete |
|---|---|---|
| Sprint 51 | Context compiler, profile, memory, compaction, preference, and conflict code has landed, but the original Sprint 42 and Sprint 43 gaps remain open until docs and browser QA are complete. | Finish `S60-P2/G42-A` through `G42-D` and `S60-P3/G43-A` through `G43-D`: create context and memory docs, include source-linked lifecycle/profile diagrams, document token budgets, memory selection, compression, stale/conflict rules, extension steps, eval commands, and retry or explicitly block Context/Memory Inspect browser QA. |
| Sprint 52 | MCP JSON-RPC, stdio-facing protocol behavior, and governed tool reuse have landed, but the original Sprint 44 gap remains open until integration docs and smoke evidence exist. | Finish `S60-P4/G44-A` through `G44-D`: document initialize/capability/list/call/error lifecycle, stdio and HTTP/SSE commands, client config, auth/project scope, approval-required and denied-write examples, redacted audit examples, advanced settings location, and run or explicitly block MCP read/proposal smoke commands. |
| Sprint 53 | Ask Thesys streaming/event/citation work has landed, but the original Sprint 46 gap remains open because web checks and IDE browser QA were blocked. | Finish `S60-P6/G46-A` through `G46-D`: document stream event contract, cancellation, timeout fallback, final payload parity, proposal/action cards, citation drilldowns, guide eval fixtures, rerun web typecheck/tests, and browser-check streamed deltas, retrieval/tool/proposal events, cancellation, timeout, and no main-workflow clutter. |
| Sprint 54 | Rate limits, workflow concurrency, budget checks, and security shape have landed, but the original Sprint 41 production posture gap remains open until audits, auth docs, egress docs, and hosted smoke disposition are recorded. | Finish `S60-P9/G41-A` through `G41-E` plus the relevant `S60-P7/G47-A` and `G47-C` budget-observability docs: record dependency audit results or blockers, auth mode table, JWT/OIDC/JWKS expectations, API key/service-account rotation and revocation, provider egress/SSRF denial evidence, backup/restore boundaries, and hosted-demo smoke status. |
| Sprint 55 | Retrieval quality, reranking, citation verification, and golden eval code has landed, but the original Sprint 45 gap remains open until the post-refactor retrieval/citation docs and eval handoff are complete. | Finish `S60-P5/G45-A` through `G45-D`: document query planning, Postgres `ts_rank` and BM25-like limits, pgvector/vector fallback, hybrid scoring, MMR/source diversity, source-quality weighting, reranker extension, cache invalidation, citation-verifier ownership, artifact coverage, unsupported/weak-claim handling, fixture IDs, commands, metrics, and current limitations. |
| Sprint 56 | Eval gates, trend/report artifacts, metrics, LangSmith export shaping, and unavailable-gate warnings have landed, but the original Sprint 47 gap remains open until CI/runbook docs and hidden report QA are complete. | Finish `S60-P7/G47-A` through `G47-D`: document aggregate and per-gate commands, pass/warn/fail policy, unavailable-gate handling, JSON/Markdown/HTML report paths, JSONL trend paths, rerun commands, changelog locations, OpenTelemetry metric names, LangSmith settings, redaction, cache/cost examples, CI usage, and hidden eval-report browser QA or blocker. |
| Sprint 57 | Semantic caching and cost metrics have landed as a new V1 upgrade, but related retrieval/eval documentation and web QA remain carried into Sprint 60. | Finish the cache portions of `S60-P5/G45-B`, `S60-P7/G47-A`, `S60-P7/G47-C`, and `S60-P7/G47-D`: document retrieval-plan/rerank-result/embedding/guide-answer cache keys, invalidation inputs, stale-cache denial behavior, cache cost/latency metrics, report surfacing, and browser QA for cache diagnostics or exact blocker. |
| Sprint 58 | Local deterministic document-intelligence behavior has landed, but the original Sprint 48 gap remains open until productization decisions, live-provider QA, and provenance browser QA are explicit. | Finish `S60-P8/G48-A` through `G48-E`: decide maintained parser dependency versus deterministic fallback, decide true page/screenshot storage, decide screenshot-region OCR/table scope, run or block Tavily/multimodal credential smoke tests, document provider-unavailable warnings, and browser-check Evidence/retrieval/guide/research/source-discovery provenance plus Project Inspect trust summaries. |
| Sprint 59 | Backend cleanup is in progress. Many pure helpers have moved into feature packages, but Sprint 49 is not closed while any `S59-R*` slice lacks characterization coverage, DTO ledger entries, shim disposition, or verification. | Finish `S59-R1` through `S59-R10` and close `G49-A` through `G49-E`: either move or explicitly mark service-owned each remaining retrieval, evidence, validation, research, guide, tool/MCP, eval, context, memory, prompt/schema repair, audit metadata, proposal, and shared DTO boundary; update package map/status/TODO; run focused tests, full backend suite when practical, feature-boundary check, ruff, compileall, diff check, and conflict scan. |
| Sprint 60 | Sprint 60 is pending and is the only sprint allowed to close or explicitly defer the remaining carried Sprint 41-50 gaps after Sprint 59 lands. | Finish `S60-P1` through `S60-P10`: create the final `G41-*` through `G50-*` disposition table, write and link all docs, retry or record blocked browser/provider/audit checks, add targeted code docs, update README navigation and AI engineering tour, and remove or qualify any portfolio claim that lacks implementation, docs, and verification. |

## Carried Gap Work Items

Use these IDs in commits, status updates, and final sprint notes. A Sprint 59 or
Sprint 60 checklist item is not done until every referenced gap ID has one of:
implemented with verification, intentionally out of V1 scope with reason, or
still open with a named future owner.

### Sprint 41 Carry-Forwards: Security and Production Posture

- [ ] `G41-A` Dependency audit closure: run `python3 scripts/security_check.py`,
  `python3 scripts/audit_dependencies.py`, `pip-audit` when installed, and
  `pnpm audit --prod`. Record exact pass/warn/fail output, registry/tool
  blockers, and whether strict CI should fail on each unavailable audit.
- [ ] `G41-B` Hosted-demo auth posture: document local/dev auth, deterministic
  demo auth, provider-backed demo auth, staging-like auth, and production-like
  auth in one table with required env vars and disabled dev-header behavior.
- [ ] `G41-C` Production auth runbook: add JWT/OIDC/JWKS expectations,
  API-key/service-account creation, token/key rotation, revocation, audit
  attribution, workspace membership checks, and known auth limitations.
- [ ] `G41-D` Provider egress verification: document allowed providers,
  timeout/response-size/retry policy, SSRF/provider egress denial behavior,
  redaction before egress, and commands/tests proving denied calls are audited.
- [ ] `G41-E` Backup/restore and hosted smoke: document Postgres/pgvector,
  object storage, eval report, trace, and audit-log backup boundaries, then run
  or explicitly block hosted-demo smoke checks for project load, evidence,
  Ask Thesys, validation, decision, memory/context Inspect, MCP read tool, and
  eval report.

### Sprint 42 Carry-Forwards: Context Engineering

- [ ] `G42-A` Context architecture docs: create a source-linked context diagram
  showing profile selection, context sources, retrieval, memory selection,
  compression, stale/conflict detection, dropped-context explanations,
  prompt-injection boundaries, and owner files.
- [ ] `G42-B` Context profile inventory: document every profile, token budget,
  required/optional item types, freshness policy, compression policy, memory
  filters, untrusted-content wrapping, and eval coverage.
- [ ] `G42-C` Context Inspect browser QA: run IDE browser checks for included,
  dropped, compressed, stale, conflicting, unsafe, and tool-output context rows;
  verify advanced details stay hidden by default.
- [ ] `G42-D` Context eval handoff: document commands, fixture IDs, report
  locations, failure interpretation, and how to add a new profile/eval case.

### Sprint 43 Carry-Forwards: Memory Management

- [ ] `G43-A` Memory lifecycle docs: add a source-linked diagram for capture,
  proposal, approval/rejection, active memory, compaction, preferences,
  conflicts, supersession, archive, audit records, and context-pack links.
- [ ] `G43-B` Memory type inventory: document memory types, selection policy,
  compaction thresholds, conflict policy, preference edit/archive behavior,
  provenance fields, and owner files.
- [ ] `G43-C` Memory extension docs: document how to add a memory type, how to
  make it eligible for a context profile, how to test stale/conflict behavior,
  and how memory write-review approvals are audited.
- [ ] `G43-D` Memory Inspect browser QA: exercise filters, proposal review,
  compaction records, selection reasons, conflict keep/supersede/archive/merge
  actions, and no clutter in the primary workflow.

### Sprint 44 Carry-Forwards: MCP Integration

- [ ] `G44-A` MCP lifecycle docs: add source-linked initialize/capability,
  tools/list, tools/call, RBAC/risk guard, approval request, denial/error,
  audit, redaction, stdio, and HTTP/SSE flow diagrams.
- [ ] `G44-B` MCP client setup: document local stdio command, HTTP/SSE command,
  example client config, required env vars, auth headers, project/workspace
  scoping, and known client limitations.
- [ ] `G44-C` MCP smoke checks: run or explicitly block read-tool and
  approval-required proposal-tool smoke commands; capture structured error,
  denied write, invalid params, missing project scope, and redacted audit
  examples.
- [ ] `G44-D` MCP advanced settings: if UI is added, keep client/provider
  settings behind developer/advanced navigation and browser-check that the
  homepage/main project workflow is unchanged.

### Sprint 45 Carry-Forwards: Retrieval and Citation Quality

- [ ] `G45-A` Retrieval architecture docs: add a source-linked pipeline diagram
  for query planning, Postgres text rank, pgvector/vector fallback, hybrid
  scoring, MMR/source diversity, source-quality weighting, reranking, cache
  lookup/invalidation, context assembly, and citation verification.
- [ ] `G45-B` Ranking limits and extension docs: document the exact BM25-like
  approximation, Postgres `ts_rank` limits, deterministic fallback behavior,
  reranker provider interface, cache invalidation inputs, and how to add a new
  provider or reranker.
- [ ] `G45-C` Citation verifier ownership: document which artifacts run claim
  verification, which artifacts are not applicable, where unsupported/weak
  claims are downgraded or labeled, and how to add verifier coverage for a new
  artifact path.
- [ ] `G45-D` Retrieval/citation eval handoff: document golden-set fixture IDs,
  commands, metrics, report paths, and expected pass/warn/fail behavior.

### Sprint 46 Carry-Forwards: Ask Thesys Streaming

- [ ] `G46-A` Streaming event contract docs: document event names, payload IDs,
  final-payload parity, cancellation, timeout, error, fallback, proposal, and
  citation drilldown fields.
- [ ] `G46-B` Web/typecheck retry: rerun web typecheck/tests after registry
  access is stable and record exact pass/fail/blocker output.
- [ ] `G46-C` Ask Thesys browser QA: exercise provider/deterministic answer
  deltas, retrieval/tool/proposal events, cancellation, timeout fallback, final
  metadata parity, action cards, collapsed citation drilldowns, and no primary
  workflow clutter.
- [ ] `G46-D` Guide eval handoff: document guide eval commands, fixture IDs,
  event-order expectations, failure interpretation, and how to add a new guide
  behavior case.

### Sprint 47 Carry-Forwards: Observability and Eval Gates

- [ ] `G47-A` Quality-gate runbook: document the aggregate command, individual
  gate commands, pass/warn/fail policy, unavailable-gate handling, artifact
  paths, rerun-only-failed-slice commands, and CI usage.
- [ ] `G47-B` Report/trend docs: document JSON/Markdown/HTML report locations,
  JSONL trend persistence, metadata fields, prompt/schema/context/retrieval/
  memory/tool changelog location, and how to interpret regressions.
- [ ] `G47-C` Observability setup: document OpenTelemetry-compatible metric
  names, LangSmith export settings, redaction behavior, cache/cost examples,
  trace IDs, and local versus external export behavior.
- [ ] `G47-D` Eval report browser QA: exercise hidden Inspect report state,
  collapsed gate details, trend rows, failing-case links, budget/cache/cost
  metrics, and no homepage/dashboard clutter.

### Sprint 48 Carry-Forwards: Source and Document Intelligence

- [ ] `G48-A` Parser dependency decision: either add a maintained readability
  dependency such as `trafilatura`/`readability-lxml`, or document the current
  deterministic `html.parser` path as the V1 fallback with parser/version/
  confidence metadata and clear productization tradeoffs.
- [ ] `G48-B` Page/screenshot storage decision: either implement true page/
  screenshot artifact capture with storage keys, retention, and redaction, or
  create a named future backlog item and keep README/status honest that V1 is
  metadata-only in local mode.
- [ ] `G48-C` Screenshot-region OCR/table decision: implement screenshot-region
  OCR/table provenance only if screenshot capture lands; otherwise mark it out
  of V1 with reason and a future owner.
- [ ] `G48-D` Live provider QA: run opt-in Tavily and multimodal provider smoke
  tests with credentials, provider mode, rate limits, and egress allowlists, or
  record the explicit unavailable warning and rerun command.
- [ ] `G48-E` Provenance browser QA: verify Evidence Inspect, retrieval result
  provenance, Ask Thesys citation drilldowns, research memo citations,
  source-discovery provenance, Project Inspect trust summaries, provider
  warnings, and no homepage/main workflow clutter.

### Sprint 49 Carry-Forwards: Feature Package Refactor

- [ ] `G49-A` Characterization matrix: add focused tests before each risky move
  for evidence/retrieval, guide, research, opportunity/competitor artifacts,
  validation, decisions, memory, MCP/tools, eval endpoints, structured-output
  repair, and context profiles.
- [ ] `G49-B` Feature package movement: finish splitting validation, research,
  guide, evidence/retrieval, tool/MCP, eval/reporting, prompt assembly,
  structured-output repair, proposal creation, and audit metadata into cohesive
  feature/common packages.
- [ ] `G49-C` DTO boundary ledger: define context pack, retrieval, citation,
  guide event, tool outcome, eval gate, cache diagnostic, and extraction DTOs;
  record old dict keys, new fields, conversion boundary, owner package, and
  compatibility serializer.
- [ ] `G49-D` Duplication cleanup: centralize prompt/schema repair, retrieval
  shaping, audit metadata merge/redaction, and proposal creation without
  changing route response shapes.
- [ ] `G49-E` Migration evidence: record compatibility shims, target feature
  modules, parity tests, dependency-boundary check output, centralized model
  ownership decisions, and known future cleanup backlog.

### Sprint 50 Carry-Forwards: Developer Docs and Readiness

- [ ] `G50-A` Source-linked diagrams: add diagrams for context, memory, MCP,
  eval gates, retrieval, and deployment/security with owner file references.
- [ ] `G50-B` README navigation and AI tour: update README so an interviewer can
  map features to patterns and technologies and a developer can find workflow,
  context, memory, retrieval, source-ingestion, MCP, eval, security,
  observability, and Inspect entrypoints.
- [ ] `G50-C` Code documentation: add docstrings/comments to public service
  entrypoints, DTOs, approval gates, security boundaries, Temporal invariants,
  prompt-injection boundaries, and non-obvious orchestration logic.
- [ ] `G50-D` Deployment docs: add environment profiles, env var tables,
  provider/cache/auth/egress posture, object-storage expectations,
  backup/restore guidance, hosted-demo smoke commands, and audit commands.
- [ ] `G50-E` Final honest-limit audit: update README/status so every Sprint
  41-50 gap is implemented, intentionally out of V1 with reason, or still open
  with a future owner; remove any portfolio claim that lacks code, tests/evals,
  docs, and verification.

## Pickup-Ready Gap Directions

Use this table when resuming the branch. Each row names the exact sprint work
that remains after the Sprint 41-50 audit. Do not check off a row unless the
referenced `G*` IDs have a status entry in `IMPLEMENTATION_STATUS.md`, a source
or doc artifact, and verification output or an explicit blocker.

| Gap IDs | Edit targets | Required pickup work | Verification and completion bar |
|---|---|---|---|
| `G41-A` through `G41-E` | `docs/DEPLOYMENT_SECURITY.md`, `README.md`, `IMPLEMENTATION_STATUS.md`, `scripts/security_check.py`, `scripts/audit_dependencies.py` | Record dependency audit results, hosted-demo auth posture, JWT/OIDC/JWKS expectations, API key/service-account lifecycle, provider egress policy, SSRF/provider denial behavior, backup/restore boundaries, and seeded hosted-demo smoke steps. If `pip-audit`, `pnpm audit --prod`, provider credentials, or hosted infrastructure are unavailable, keep the blocker explicit and assign a future owner. | Run or record blockers for `python3 scripts/security_check.py`, `python3 scripts/audit_dependencies.py`, `pip-audit`, `pnpm audit --prod`, and hosted smoke for project load, evidence, Ask Thesys, validation, decision, memory/context Inspect, MCP read tool, and eval report. Close only after `IMPLEMENTATION_STATUS.md` has one row per `G41-*` item. |
| `G42-A` through `G42-D` | `docs/CONTEXT_ENGINEERING.md`, `README.md`, `apps/api/app/services/context_service.py`, `apps/api/app/features/memory/context_pack.py`, context/eval tests | Add a source-linked context diagram, profile inventory, token budget table, source inventory, memory/retrieval/tool inputs, compression/stale/conflict policy, dropped-context examples, untrusted-content boundaries, Inspect surface notes, and "how to add a context profile" steps. | Run `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`; retry web typecheck/tests and IDE browser QA for included/dropped/compressed/stale/conflicting/unsafe/tool-output rows, or record exact registry/browser blocker. |
| `G43-A` through `G43-D` | `docs/MEMORY_SYSTEM.md`, `README.md`, `apps/api/app/services/memory_service.py`, `apps/api/app/features/memory/*`, memory/context tests | Document memory type inventory, capture/proposal/approval lifecycle, compaction thresholds, preference edit/archive flow, conflict groups, supersession/archive behavior, audit links, context-pack linkage, and "how to add a memory type." Patch code docstrings/comments around non-obvious manager/review APIs if missing after Sprint 59. | Run `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`; browser-check memory filters, proposals, selection reasons, compaction records, and conflict keep/supersede/archive/merge actions, or record blocker. |
| `G44-A` through `G44-D` | `docs/MCP_INTEGRATION.md`, `README.md`, `apps/api/app/mcp/adapter.py`, `apps/api/app/features/mcp/protocol.py`, `apps/api/app/features/governance_tools/*` | Document initialize/capabilities/tools/list/tools/call lifecycle, stdio and HTTP/SSE commands, client config, auth/project scoping, approval-required proposal example, denied write example, invalid params example, redacted audit example, and advanced settings location. | Run `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_feature_package_boundaries.py -q`; run or explicitly block stdio/API smoke commands for read and proposal tools; verify no homepage/main workflow clutter if UI/settings change. |
| `G45-A` through `G45-D` | `docs/RETRIEVAL_AND_CITATIONS.md`, `README.md`, `apps/api/app/services/retrieval_service.py`, `apps/api/app/features/retrieval/*`, `apps/api/app/features/evidence/citations.py` | Document retrieval pipeline, Postgres `ts_rank` and BM25-like limits, vector fallback, hybrid scoring, MMR/source diversity, source-quality weighting, reranker provider interface, cache invalidation inputs, citation verifier ownership, artifact coverage, unsupported/weak claim handling, and eval fixture maintenance. | Run `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py app/tests/test_feature_package_boundaries.py -q` and `python3 scripts/eval_retrieval_quality.py`; record current limitations in status. |
| `G46-A` through `G46-D` | README guide/Ask Thesys sections, `apps/web/*` guide UI files, `apps/api/app/services/guide_service.py`, `apps/api/app/features/guide/*`, guide tests | Document streaming event names and payload IDs, final-response parity, cancellation, timeout fallback, action/proposal cards, citation drilldown fields, guide eval handoff, and hidden advanced diagnostics. Keep the homepage and main project workflow simple. | Run `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`, `pnpm --filter thesys-web typecheck`, `pnpm --filter thesys-web test`, and IDE browser QA for deltas/events/cancellation/timeout/citations, or record registry/browser blocker. |
| `G47-A` through `G47-D` | `docs/EVALS_AND_OBSERVABILITY.md`, `README.md`, `scripts/eval_quality_gate.py`, `apps/api/app/features/evals/*`, `apps/api/app/services/eval_report_service.py` | Document aggregate/per-gate commands, pass/warn/fail policy, unavailable gates, report/trend paths, failed-slice reruns, prompt/schema/context/retrieval/memory/tool changelog locations, OpenTelemetry metric names, LangSmith export settings, redaction, cache/cost examples, and hidden report UI behavior. | Run `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60 LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json`, plus focused eval report tests; retry hidden eval-report browser QA or record blocker. |
| `G48-A` through `G48-E` | `docs/SOURCE_INTELLIGENCE.md`, `README.md`, source ingestion/extraction services and UI provenance surfaces | Decide maintained parser dependency versus deterministic fallback; decide true page/screenshot storage and screenshot-region OCR/table scope; document live Tavily/multimodal credential QA, provider-unavailable warnings, provenance fields, source-quality factors, and Project Inspect trust summaries. | Run `python3 scripts/eval_extraction_quality.py --json`; run or record blockers for live Tavily/multimodal smoke; retry web typecheck/tests and browser QA for Evidence, retrieval, guide, research memo, source-discovery, and Project Inspect provenance. |
| `G49-A` through `G49-E` | `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, `SPRINT_51_60_TODO.md`, `IMPLEMENTATION_STATUS.md`, `apps/api/app/features/*`, `apps/api/app/common/*`, compatibility services | Keep the characterization matrix, DTO boundary ledger, shim/migration ledger, package map, dependency rules, and future cleanup backlog current for every moved slice. The identified low-risk function extractions are now implemented; continue larger orchestration moves only behind characterization tests. | Run focused tests named in each `S59-*` slice, `python3 scripts/check_feature_boundaries.py`, `cd apps/api && .venv/bin/pytest -q`, `git diff --check`, and `rg -n "<{7}|={7}|>{7}" .`; do not commit Sprint 59 while any moved helper lacks a ledger row. |
| `G50-A` through `G50-E` | `README.md`, `IMPLEMENTATION_STATUS.md`, docs under `docs/`, targeted source docstrings/comments | Add source-linked diagrams, README navigation, AI engineering tour, project navigation, code docs, deployment profiles, advanced settings docs, hosted-demo smoke notes, and final honest-limit audit. Make docs reflect implemented code after Sprint 59, not roadmap intent. | Sprint 60 is complete only when every `G41-*` through `G50-*` item has an `implemented`, `intentionally out of V1`, or `future owner` disposition in `IMPLEMENTATION_STATUS.md`, all new docs are linked from README, deferred browser/audit blockers are exact, and portfolio claims match code/tests/evals. |

### Per-ID Pickup Checklist

This checklist prevents a completed sprint title from hiding an unfinished
audit item. Every row below must receive a matching final disposition row in
`IMPLEMENTATION_STATUS.md` with source/doc links, verification output or exact
blocker text, and a future owner when deferred.

| ID | Pickup owner | Specific work before the item can be closed |
|---|---|---|
| `G41-A` | `S60-P9` | Run `python3 scripts/security_check.py`, `python3 scripts/audit_dependencies.py`, `pip-audit` when available, and `pnpm audit --prod`; record pass/warn/fail output, unavailable-tool behavior, registry errors, and whether strict CI should fail on each unavailable audit. |
| `G41-B` | `S60-P9` | Add the auth-mode table to `docs/DEPLOYMENT_SECURITY.md`: local/dev, deterministic demo, provider-backed demo, staging-like, and production-like modes; include required env vars, disabled dev-header behavior, provider credential expectations, and verification commands. |
| `G41-C` | `S60-P9` | Add the production auth runbook covering JWT verification, OIDC/JWKS expectations, API-key and service-account creation, rotation, revocation, audit attribution, workspace membership checks, and known limitations that remain outside V1. |
| `G41-D` | `S60-P9` | Document provider allowlists, SSRF/provider denial behavior, timeout/response-size/retry limits, redaction before egress, and exact tests or smoke commands proving denied provider calls are audited. |
| `G41-E` | `S60-P9` | Document backup/restore boundaries for Postgres/pgvector, object storage, eval reports, traces, and audit logs; run hosted-demo smokes for project load, evidence, Ask Thesys, validation, decision, memory/context Inspect, MCP read tool, and eval report, or record the exact missing infrastructure blocker. |
| `G42-A` | `S60-P2` | Create `docs/CONTEXT_ENGINEERING.md` with a source-linked context diagram showing profile selection, domain state, retrieved evidence, tool outputs, memory, compression, stale/conflict checks, dropped rows, prompt-injection boundaries, and owner files. |
| `G42-B` | `S60-P2` | Add a complete context profile inventory: profile name, owner code, token budget, required/optional item types, memory filters, freshness/staleness policy, compression policy, untrusted-content wrapping, and eval coverage. |
| `G42-C` | `S60-P2` | Retry IDE browser QA for Context Inspect included, dropped, compressed, stale, conflicting, unsafe, and tool-output rows; verify details stay hidden by default; if blocked, record exact command, error, retry condition, and owner. |
| `G42-D` | `S60-P2` | Document context eval commands, fixture IDs, report paths, expected failures, failure interpretation, and exact steps for adding a new profile and eval case. |
| `G43-A` | `S60-P3` | Create `docs/MEMORY_SYSTEM.md` with a source-linked lifecycle diagram for capture, proposal, approval/rejection, active memory, compaction, preferences, conflicts, supersession, archive, audit records, and context-pack links. |
| `G43-B` | `S60-P3` | Document every memory type, selection policy, compaction thresholds, conflict policy, preference edit/archive behavior, provenance fields, context eligibility, and owner files. |
| `G43-C` | `S60-P3` | Add "how to add a memory type" steps: schema/service changes, review workflow, context-profile eligibility, stale/conflict tests, audit behavior, and status/README links. |
| `G43-D` | `S60-P3` | Browser-check Memory Inspect filters, proposal review, compaction records, selection reasons, and conflict keep/supersede/archive/merge actions; verify advanced details stay out of the primary workflow or record exact blocker. |
| `G44-A` | `S60-P4` | Add MCP lifecycle diagrams for initialize/capability negotiation, `tools/list`, `tools/call`, RBAC/risk guard, approval request, denial/error handling, audit, redaction, stdio, and HTTP/SSE paths. |
| `G44-B` | `S60-P4` | Document exact stdio and HTTP/SSE commands, example client config, required env vars, auth headers, project/workspace scoping, and known client limitations after the Sprint 59 package refactor. |
| `G44-C` | `S60-P4` | Run or explicitly block MCP smoke commands for a read tool, approval-required proposal tool, denied write, invalid params, missing project scope, structured error response, and redacted audit payload. |
| `G44-D` | `S60-P4` | If integration settings UI exists or is added, keep it under developer/advanced navigation and browser-check that the homepage and primary project workflow are unchanged. |
| `G45-A` | `S60-P5` | Create `docs/RETRIEVAL_AND_CITATIONS.md` with a source-linked pipeline diagram for query planning, Postgres text rank, pgvector/vector fallback, hybrid scoring, MMR/source diversity, source-quality weighting, reranking, cache lookup/invalidation, context assembly, and citation verification. |
| `G45-B` | `S60-P5` | Document the exact BM25-like approximation, Postgres `ts_rank` limits, deterministic fallback behavior, reranker provider interface, cache invalidation inputs, and steps for adding retrieval providers or rerankers. |
| `G45-C` | `S60-P5` | Add a citation verifier ownership matrix by artifact type; identify not-applicable paths, weak/unsupported claim handling, downgraded/labeled persistence behavior, and extension steps for new generated artifacts. |
| `G45-D` | `S60-P5` | Document golden retrieval/citation fixture IDs, commands, metrics, report paths, expected pass/warn/fail behavior, and current retrieval/citation verification output. |
| `G46-A` | `S60-P6` | Document Ask Thesys streaming event names, event ordering, payload IDs, final payload parity, cancellation, timeout, error/fallback behavior, proposal/action-card fields, citation drilldown fields, and hidden diagnostic metadata. |
| `G46-B` | `S60-P6` | Rerun `pnpm --filter thesys-web typecheck` and `pnpm --filter thesys-web test`; paste exact pass/fail output or registry blocker into `IMPLEMENTATION_STATUS.md`. |
| `G46-C` | `S60-P6` | IDE-browser-check provider/deterministic answer deltas, retrieval/tool/proposal events, cancellation, timeout fallback, final metadata parity, action cards, collapsed citation drilldowns, and no homepage/main workflow clutter. |
| `G46-D` | `S60-P6` | Document guide eval fixture IDs, commands, event-order expectations, malformed-event behavior, deterministic fallback parity, failure interpretation, and steps for adding a new guide behavior case. |
| `G47-A` | `S60-P7` | Add the quality-gate runbook: aggregate command, individual gate commands, pass/warn/fail policy, unavailable-gate policy, artifact paths, rerun-only-failed-slice commands, and CI usage. |
| `G47-B` | `S60-P7` | Document JSON/Markdown/HTML report locations, JSONL trend persistence, metadata fields, prompt/schema/context/retrieval/memory/tool changelog locations, and regression interpretation. |
| `G47-C` | `S60-P7` | Document OpenTelemetry-compatible metric names, LangSmith export settings, redaction behavior, cache/cost examples, trace IDs, pre-call budget denial metrics, and local versus external export behavior. |
| `G47-D` | `S60-P7` | Browser-check hidden eval-report Inspect state, collapsed gate details, trend rows, failing-case links, budget/cache/cost metrics, and no homepage/dashboard clutter, or record exact blocker. |
| `G48-A` | `S60-P8` | Decide and record whether to add a maintained readability dependency or document deterministic `html.parser` as the V1 fallback; include parser/version/confidence metadata and tradeoffs. |
| `G48-B` | `S60-P8` | Decide and record whether true page/screenshot artifact capture with storage keys, retention, and redaction is in V1; if not, create a named future backlog item and keep README/status honest that local V1 is metadata-only. |
| `G48-C` | `S60-P8` | Decide screenshot-region OCR/table provenance: implement only if screenshot capture lands, otherwise mark it out of V1 with reason, future owner, and dependency on `G48-B`. |
| `G48-D` | `S60-P8` | Run opt-in Tavily and multimodal provider smoke tests with credentials, provider mode, rate limits, and egress allowlists, or record explicit unavailable warnings and rerun commands. |
| `G48-E` | `S60-P8` | Browser-check Evidence Inspect, retrieval provenance, Ask Thesys citation drilldowns, research memo citations, source-discovery provenance, Project Inspect trust summaries, provider warnings, and no homepage/main workflow clutter. |
| `G49-A` | `S59-P1` through `S59-P9` | Keep characterization tests ahead of risky movement across evidence/retrieval, guide, research, opportunity/competitor artifacts, validation, decisions, memory, MCP/tools, eval endpoints, structured-output repair, and context profiles. |
| `G49-B` | `S59-P1` through `S59-P9` | Finish or explicitly defer feature-package movement for validation, research, guide, evidence/retrieval, tool/MCP, eval/reporting, prompt assembly, structured-output repair, proposal creation, and audit metadata. |
| `G49-C` | `S59-P1` through `S59-P9` | Keep the DTO ledger current for context pack, retrieval, citation, guide event, tool outcome, eval gate, cache diagnostic, and extraction shapes; record old dict keys, new fields, conversion boundary, owner package, and compatibility serializer. |
| `G49-D` | `S59-P8` | Centralize only tested duplication in prompt/schema repair, retrieval shaping, audit metadata merge/redaction, and proposal/action-card creation without changing public API or persisted schemas. |
| `G49-E` | `S59-P9` | Record compatibility shims, target feature modules, parity tests, dependency-boundary output, model ownership decisions, intentionally centralized services, and future cleanup backlog before the Sprint 59 commit. |
| `G50-A` | `S60-P10` | Add source-linked diagrams for context, memory, MCP, eval gates, retrieval, and deployment/security, and place owner file references next to each diagram. |
| `G50-B` | `S60-P10` | Update README navigation and AI engineering tour so interviewers can map features to AI patterns/technologies and developers can find workflow, context, memory, retrieval, source-ingestion, MCP, eval, security, observability, and Inspect entrypoints. |
| `G50-C` | `S60-P10` | Add targeted docstrings/comments to public service entrypoints, DTOs, approval gates, security boundaries, Temporal determinism constraints, prompt-injection boundaries, and non-obvious orchestration logic; avoid comments that restate obvious assignments. |
| `G50-D` | `S60-P9`, `S60-P10` | Add deployment docs for environment profiles, env var tables, provider/cache/auth/egress posture, object-storage expectations, backup/restore guidance, hosted-demo smoke commands, and audit commands. |
| `G50-E` | `S60-P1`, `S60-P10` | Run the final honest-limit audit: every `G41-*` through `G50-*` item must be implemented, intentionally out of V1 with reason, or still open with future owner; remove or qualify any README/status/portfolio claim that lacks code, tests/evals, docs, and verification. |

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
- Sprint 58 extraction checks are now fixture-backed, but Sprint 60 must retry
  the environment-blocked web checks and any credential-backed live-provider
  smoke tests. Required retry scope: `pnpm --filter thesys-web typecheck`,
  `pnpm --filter thesys-web test`, IDE browser QA for Evidence/retrieval/guide/
  research/source-discovery provenance disclosures, and opt-in Tavily plus
  multimodal provider smoke tests when credentials and egress allowlists are
  configured. If the environment is still blocked, record the exact blocker and
  next owner instead of marking the checks complete.

## Explicit Remaining Pickup Queue

This queue is the authoritative remaining TODO list for the unfinished Sprint
41-50 gaps. The broader sprint checklists below provide context, but these
items are the concrete work packages to pick up. Do not mark a package complete
unless the named gap IDs are updated in `IMPLEMENTATION_STATUS.md` with source
links and verification output.

### How to Use This Queue

- Treat each `S59-*` and `S60-*` row as an implementation ticket, not as a
  reminder. A row is not complete until the code/doc targets, status updates,
  and verification commands in that row are done or explicitly blocked.
- If a carried gap is intentionally left outside V1, add the reason, exact
  future owner, and current evidence to `IMPLEMENTATION_STATUS.md`. Do not
  silently absorb it into a broad "future work" note.
- If a browser, provider, audit, or hosted-demo check cannot run, record the
  exact command, exact blocker/error, retry condition, and next owner. The
  blocker must still appear under the relevant `G41-*` through `G50-*` ID.
- Keep the homepage and primary project workflow simple. Any UI work below
  should expose detailed AI, MCP, eval, cache, provenance, or security state in
  Inspect/developer/collapsed surfaces unless the sprint explicitly says
  otherwise.

### Gap-Patching Rule for Completed Sprints

Sprints 51-58 are code-landed only. They are not gap-closed until the owning
Sprint 60 package writes final `IMPLEMENTATION_STATUS.md` rows for each related
`G*` ID. When picking up work, do not infer completion from checked Sprint 51-58
items. Pick the row below, patch the named doc/source targets, run or block the
named commands, and then write the final status row with the required
portfolio-claim consequence.

### Residual Gap Routing from Completed Sprints

These rows make the unfinished portions of Sprints 51-58 visible in the active
TODO, even when the implementation sprint itself is already committed. Pick up
the owning Sprint 60 package named here instead of reopening the completed
sprint.

| Completed sprint | Open gap IDs | What is still not complete | Owning pickup item |
|---|---|---|---|
| Sprint 51 context compiler | `G42-A` through `G42-D` | Source-linked context docs, complete profile inventory, Inspect browser QA for selected/dropped/compressed/stale/conflicting/unsafe/tool-output rows, and eval handoff docs. | `S60-P2` |
| Sprint 51 memory v2 | `G43-A` through `G43-D` | Memory lifecycle docs, memory type inventory, extension guide, and browser QA for filters, proposals, compaction, selection reasons, and conflict actions. | `S60-P3` |
| Sprint 52 MCP server | `G44-A` through `G44-D` | Lifecycle/client docs, stdio/API smoke output, denial/error/redaction examples, advanced settings docs, and verification that MCP details stay out of the main workflow. | `S60-P4` |
| Sprint 53 Ask Thesys streaming | `G46-A` through `G46-D` | Web typecheck/tests, IDE browser QA for streaming/cancel/timeout/events/action cards/citations, and guide eval/event-contract docs. | `S60-P6` |
| Sprint 54 security and auth | `G41-A` through `G41-E` | Strict dependency audit disposition, hosted-demo auth posture, JWT/OIDC/JWKS runbook, rotation/revocation docs, provider-egress verification, backup/restore, and hosted smoke disposition. | `S60-P9` |
| Sprint 55 retrieval quality | `G45-A` through `G45-D` | Retrieval/citation docs, BM25/`ts_rank` limitation notes, provider/reranker extension points, citation verifier ownership, cache invalidation notes, and eval handoff. | `S60-P5` |
| Sprint 56 evals/observability | `G47-A` through `G47-D` | CI/runbook docs, report/trend paths, unavailable gate policy, LangSmith/OpenTelemetry setup, hidden report browser QA, and cache/cost metric examples. | `S60-P7` |
| Sprint 57 semantic cache | `G45-B`, `G47-A`, `G47-C` | Cache invalidation docs, stale-cache denial explanation, saved token/cost/latency report examples, and cache diagnostics in the eval/observability runbook. | `S60-P5`, `S60-P7` |
| Sprint 58 source intelligence | `G48-A` through `G48-E` | Parser dependency decision, true page/screenshot storage decision, screenshot-region OCR/table disposition, live Tavily/multimodal QA or blocker, provenance browser QA, and Project Inspect trust-summary QA. | `S60-P8` |

### Sprint 59 Pickup Queue: `G49-A` through `G49-E`

| Item | Gap IDs | Required implementation direction | Required docs/status updates | Required verification |
|---|---|---|---|---|
| `S59-P1` evidence/retrieval feature ownership | `G49-A`, `G49-B`, `G49-C`, `G49-E` | Continue feature ownership for remaining pure evidence/retrieval helpers. Evidence extraction metadata is implemented for direct URL responses, upload/file identity, image uploads, text uploads, PDF parser metadata, and OCR fallback metadata. Remaining candidates are chunk/result DTO shaping, retrieval execution result shaping, cache-key diagnostics, citation enrichment payloads, and any source-quality explanation helpers not already in `app.features.evidence.source_provenance`. Keep DB writes, transaction boundaries, fetch/storage/parser/provider orchestration, and route orchestration in services unless typed DTOs are introduced. | Add rows to `docs/BACKEND_FEATURE_PACKAGE_MAP.md` for old service helper, new feature module, DTO fields/old keys, compatibility shim, focused test, and future cleanup. Update this file and `IMPLEMENTATION_STATUS.md` with what stayed service-owned. | `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; `python3 scripts/check_feature_boundaries.py`. |
| `S59-P2` validation and decision boundaries | `G49-A`, `G49-B`, `G49-C`, `G49-D`, `G49-E` | Finish typed boundaries for validation generation inputs/results, validation interpretation outcomes, experiment-result parsing, approval/proposal payload creation, decision recommendation DTOs, weak-evidence labels, and audit metadata. Implemented slices now cover validation interpretation fallback heuristics, validation result prompt payload shaping, validation mission context projection, validation interpretation proposed-update payload shaping, weak-evidence decision labels, route contract fields, approval rejection/no-mutation behavior, and deterministic validation generation prompts/fallbacks. Keep approval persistence, memory writes, artifacts, missions, provider calls, AI run accounting, confidence mutation, and DB transactions service-owned. | Record validation/decision DTO ledger rows, shim rows, and intentionally centralized service responsibilities. Note any proposal/action-card duplication that remains and why. If experiment-result parsing or broader validation-plan DTOs stay service-owned, add that disposition instead of leaving it as generic cleanup. | `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_project_overview.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`. |
| `S59-P3` research workflow boundaries | `G49-A`, `G49-B`, `G49-C`, `G49-E` | Add characterization tests before moving any LangGraph/Temporal-adjacent logic. Move only pure graph-state serialization, research plan/memo shaping, selected-evidence bundles, citation-audit payload shaping, source-discovery candidate metadata, and memory-proposal DTO helpers. Keep Temporal activities, workflow status transitions, DB writes, tool execution, and approval writes service-owned unless typed adapters are created. | Add package-map rows for `agentic_research_service.py`, `research_sprint_service.py`, and `source_discovery_service.py`; record graph/Temporal invariants and future cleanup. | `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_research_sprints.py app/tests/test_research_discovery.py app/tests/test_temporal_research_orchestration.py app/tests/test_feature_package_boundaries.py -q`. |
| `S59-P4` guide and streaming boundaries | `G49-A`, `G49-B`, `G49-C`, `G49-D`, `G49-E` | Move remaining pure guide helpers for context adapter output, grounded deterministic answer shaping, proposal/action-card routing, citation drilldown DTOs, stream event DTOs, final-payload parity, guide eval fixture shaping, and weak-evidence labels. Keep AI run writes, provider calls, cancellation handling, approval writes, and route orchestration service-owned. | Update guide DTO ledger rows for event names, payload IDs, citation drilldown fields, proposal/action-card fields, and compatibility serializers. Record any intentionally duplicated UX copy or route response shaping. | `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_context_compiler.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`. |
| `S59-P5` governed tools and MCP boundaries | `G49-A`, `G49-B`, `G49-C`, `G49-D`, `G49-E` | Finish pure governed-tool/MCP movement for execution dispatch DTOs, proposal payload shaping, audit metadata shaping, redaction helpers, stdio bridge serialization, JSON-RPC envelope helpers, and schema generation. Keep auth, RBAC, DB approval writes, audit persistence, and request-scoped service orchestration outside feature modules. | Add DTO/shim rows for tool outcome, tool proposal, MCP request/response, denied-call audit, and redacted payload shapes. Record permanent versus temporary adapter shims. | `cd apps/api && .venv/bin/pytest app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py app/tests/test_security_governance.py app/tests/test_feature_package_boundaries.py -q`; run or explicitly block stdio smoke. |
| `S59-P6` eval/report boundaries | `G49-A`, `G49-B`, `G49-C`, `G49-D`, `G49-E` | Finish typed eval/report/export DTO boundaries. Keep CLI parsing, subprocess execution, live API fetches, local file permissions, and upload side effects script/service-owned. Implemented slices now cover gate result parsing/shaping, typed gate result validation, typed metric-record validation, typed report failure validation, typed LangSmith export-result validation, typed OpenTelemetry metric-point validation, typed eval-run summary validation, typed token/cost summary validation, typed cache diagnostic validation, rerun metadata, report file readers/writers/summary shaping, missing/malformed/unreadable report payloads, malformed/unreadable/unwritable trend warning payloads, live-provider-unavailable warning metric shaping, local metric export payload assembly, LangSmith export payload/path/result/run-input shaping, metric records for all local eval scripts, and research case dataset loading/schema validation/scoring. | Update eval gate/report DTO ledger rows, script-shim rows, report artifact ownership, and the future cleanup path for `scripts/eval_quality_gate.py`, `scripts/eval_mcp_contract.py`, and `scripts/eval_research_sprints.py`. Full gate-execution, trend-persistence, and upload side-effect movement remain future cleanup. | `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_research_history_eval.py app/tests/test_demo_eval_workflows.py app/tests/test_feature_package_boundaries.py -q`; `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-final LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security`; `python3 scripts/eval_research_sprints.py --json`; `python3 scripts/eval_mcp_contract.py --help`; run the full MCP contract with `--project-id` when a live API project is available. |
| `S59-P7` context and memory boundaries | `G49-A`, `G49-B`, `G49-C`, `G49-D`, `G49-E` | Finish pure context/memory movement for context-pack DTO serialization, selected/dropped/compressed/stale/conflict item shapes, memory selection policy, compaction policy helpers, conflict resolution payload helpers, proposal/review DTOs, explanation payloads, and token estimate helpers. Keep DB reads/writes, approval gates, conflict mutations, and Inspect route orchestration service-owned. | Add DTO rows for context pack, context item, memory selection, memory proposal, memory conflict, memory compaction, and Inspect payloads. Record exact service-owned responsibilities. | `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`. |
| `S59-P8` shared duplication cleanup | `G49-C`, `G49-D`, `G49-E` | Centralize only duplication proven by tests: structured-output repair dispatch, deterministic fallback completion metadata, audit metadata merge/redaction, proposal/action-card creation, citation/provenance shaping, Markdown rendering, and retrieval result shaping. Use `app.common` only for behavior shared by multiple features; otherwise keep helpers feature-owned. | Record each cleanup in the migration ledger with old helper, new module, parity test, shim status, and whether more cleanup is intentionally deferred. | Focused tests for touched features, then `cd apps/api && .venv/bin/pytest app/tests/test_ai.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; `python3 scripts/check_feature_boundaries.py`. |
| `S59-P9` final Sprint 59 closeout | `G49-A`, `G49-B`, `G49-C`, `G49-D`, `G49-E` | Stop moving code and audit the refactor. No helper that moved to `app.features.*` can be missing from the characterization matrix, DTO ledger, or shim ledger. No high-risk orchestration move can be marked complete without tests and explicit service-owned boundaries. | Update `README.md`, `IMPLEMENTATION_STATUS.md`, `IMPLEMENTATION_BRIEF.md`, this TODO, and `docs/BACKEND_FEATURE_PACKAGE_MAP.md` with final package map, remaining shims, intentionally centralized modules, and future cleanup backlog. | `cd apps/api && .venv/bin/pytest -q`; `cd apps/api && .venv/bin/ruff check app`; `cd apps/api && .venv/bin/python -m compileall app -q`; `python3 scripts/check_feature_boundaries.py`; `git diff --check`; `rg -n "<{7}|={7}|>{7}" .`. |

### Sprint 59 Open Code Cleanup Punch List

This punch list is intentionally more concrete than the sprint title. Use it to
finish `G49-*` without another broad audit. A row may be closed by moving the
pure helper into a feature package, or by documenting why it must stay
service-owned. In both cases, the package map and status file must say exactly
what happened.

| Item | Gap IDs | Edit targets | Required pickup work | Verification |
|---|---|---|---|---|
| `S59-R1` retrieval execution DTOs | `G49-B`, `G49-C`, `G49-E` | `apps/api/app/services/retrieval_service.py`, `apps/api/app/features/retrieval/*`, `docs/BACKEND_FEATURE_PACKAGE_MAP.md` | Implemented for query planning/tokenization, score math, result fusion, source-quality/freshness reranking, context selection, quality proxies, fallback aggregation, citation dedupe, and base/pipeline retrieval diagnostics through `app.features.retrieval.*` and `app.features.evidence.citation_verifier`. Remaining retrieval cleanup is limited to typed request/result/cache-key DTOs, DB retrieval execution, cache lookup/invalidation/write orchestration, citation enrichment/persistence, embedding similarity, SQL/vector query paths, candidate loading, and route orchestration. Keep those service-owned unless typed DTO boundaries are added. | `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_diagnostic_helpers_are_feature_owned_and_service_compatible app/tests/test_evidence.py::test_broad_evidence_retrieval_plans_reranks_and_assembles_context app/tests/test_retrieval_quality_eval.py -q`; `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_retrieval_quality_eval.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q` |
| `S59-R2` evidence extraction boundaries | `G49-B`, `G49-C`, `G49-E` | `apps/api/app/services/evidence_service.py`, `apps/api/app/features/evidence/*`, `apps/api/app/features/evidence/source_provenance.py` | Implemented for direct URL response metadata, file identity metadata, image upload metadata, text upload metadata, PDF parser metadata, OCR fallback metadata, HTML parsing, chunking, table artifact metadata, quote provenance, source-quality explanations, and extraction eval ownership through `app.features.evidence.extraction` and `app.features.evidence.source_provenance`. Remaining evidence cleanup is limited to URL fetch validation/HTTP orchestration, upload validation/object storage, PDF parsing, OCR/multimodal provider calls, chunk persistence, embedding writes, security audit writes, DB transactions, and route orchestration. Keep those service-owned unless typed ingestion/extraction DTOs are added. | `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_extraction_feature_module_exposes_service_compatible_helpers app/tests/test_evidence.py -q`; `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; `python3 scripts/eval_extraction_quality.py --json` |
| `S59-R3` validation proposal and parse DTOs | `G49-B`, `G49-C`, `G49-D`, `G49-E` | `apps/api/app/services/validation_service.py`, `apps/api/app/features/validation/*`, `apps/api/app/features/decisions/*`, `docs/BACKEND_FEATURE_PACKAGE_MAP.md` | Implemented: validation interpretation fallback heuristics, validation mission context projection, skeptical result-interpretation prompt payloads, interpretation proposed-update payloads, weak-evidence decision labels, decision route contract fields, validation interpretation rejection/no-mutation coverage, and validation generation prompt/fallback helpers are feature-owned or route-pinned. Remaining: experiment-result parsing, broader validation generation input/outcome DTOs, validation interpretation outcome DTOs, DB-backed decision recommendation/proposal boundaries, and any audit/proposal helpers not yet in feature packages. Provider calls, AI run accounting, artifact/mission creation, approval persistence, memory writes, confidence mutation, audit persistence, DB commits, and route orchestration stay service-owned unless typed boundaries and route-level tests are added. | `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_project_overview.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; update the package-map DTO/shim ledger before checking this row. |
| `S59-R4` research graph-safe helpers | `G49-A`, `G49-B`, `G49-C`, `G49-E` | `apps/api/app/services/agentic_research_service.py`, `apps/api/app/services/research_sprint_service.py`, `apps/api/app/services/source_discovery_service.py`, `apps/api/app/features/research/*`, `docs/BACKEND_FEATURE_PACKAGE_MAP.md` | Implemented for JSON-safe graph-state serialization, deterministic subquestion planning, bounded tool-call strategy, lookup-tool mapping, lookup payload projection, evidence-gap detection, research text/list normalization, memo markdown/rendering, selected-evidence bundles, final memo prompt message assembly, trusted/untrusted context splitting, untrusted retrieved-content wrapping, citation-audit shaping, claim support downgrades, finding-level citation filtering, citation enrichment/de-dupe, research sprint planning prompts, deterministic fallback research plans, memory-preview/fallback assumption/risk payloads, research memo proposal payload/input shaping, source-discovery prompt payloads, source-discovery candidate metadata, external-search result normalization, snapshot text, evidence metadata, URL cleanup/dedupe, source-type/risk inference, and fallback candidate specs. Remaining R4 work is service-owned orchestration only: LangGraph construction, Temporal activities, workflow status transitions, tool execution, retrieval execution, context-pack construction, provider calls, structured-output parsing, AI run/step writes, artifact/claim persistence, tool proposal/approval writes, memory upserts, project confidence mutation, DB writes, and route orchestration unless a future typed orchestration DTO is introduced. | `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_research_planning_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_research_graph_state_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_research_strategy_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_research_memo_prompt_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_research_citation_audit_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_research_memo_proposal_payloads_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_source_discovery_helpers_are_feature_owned_and_service_compatible app/tests/test_agentic_research.py::test_agentic_research_runs_multi_step_rag_and_writes_reviewable_memo app/tests/test_research_sprints.py::test_research_sprint_plan_generation_waits_for_human_approval app/tests/test_research_discovery.py -q`; broader closeout still requires `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_research_sprints.py app/tests/test_research_discovery.py app/tests/test_temporal_research_orchestration.py app/tests/test_feature_package_boundaries.py -q`. |
| `S59-R5` guide answer and nudge action DTOs | `G49-B`, `G49-C`, `G49-D`, `G49-E` | `apps/api/app/services/guide_service.py`, `apps/api/app/services/nudge_service.py`, `apps/api/app/services/eval_service.py`, `apps/api/app/features/guide/*` | Implemented for stream event DTOs, citation drilldowns, deterministic routing/proposal payloads, action cards, nudge action payloads, recommendation copy, recent-turn bounding, overview-to-guide-context projection, risk/unknown projection, grounded prompt assembly with trusted/untrusted context splitting, grounded-answer DTO shaping, and guide eval read-model shaping through `app.features.guide.events`, `citations`, `routing`, `actions`, `recommendations`, `context_projection`, `prompting`, `grounding`, and `evals`. Remaining guide cleanup is limited to active workflow DB lookup, larger context adapter ownership, provider-backed grounded generation orchestration, guide eval fixture loading beyond DB counts, AI run/cache/cancellation side effects, DB-backed proposal creation, approval lookup, citation verification orchestration, nudge candidate persistence, and route orchestration. Keep those service-owned unless typed boundaries are added. | `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_context_projection_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_guide_prompt_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_guide_grounding_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_guide_eval_helpers_are_feature_owned_and_service_compatible app/tests/test_guide.py::test_guide_eval_reports_grounding_and_proposal_governance -q`; `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_nudges.py app/tests/test_context_compiler.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q` |
| `S59-R6` governed tool transport edges | `G49-A`, `G49-B`, `G49-C`, `G49-E` | `apps/api/app/services/tool_service.py`, `apps/api/app/mcp/adapter.py`, `scripts/mcp_stdio_server.py`, `apps/api/app/features/governance_tools/*`, `apps/api/app/features/mcp/*` | Implemented/pinned for automated contract coverage: stdio command-failure characterization, transport serialization helpers, JSON-RPC envelope helpers, approval-required proposal shape, denied write shape, missing/invalid project scope behavior, redacted audit payloads, direct MCP HTTP/JSON-RPC schema parity, HTTP tool-invocation/approval route parity, approval rejection parity, denial audit parity, and redacted proposal `output_summary`. Stdio bridge HTTP failure preserves the JSON-RPC request ID and returns a `-32000` JSON-RPC error without crashing. Auth, RBAC, approval persistence, audit persistence, redaction calls, commits, and request orchestration stay at service/adapter edges. Live stdio read/proposal smoke remains `S60-P4/G44-C` unless a live API project is available before Sprint 59 closeout. | `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py::test_mcp_jsonrpc_proposal_matches_http_approval_and_audit_contracts -q`; `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_security_governance.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; run or block live stdio smoke with exact command/output |
| `S59-R7` eval/report failure surfaces | `G49-B`, `G49-C`, `G49-D`, `G49-E` | `apps/api/app/services/eval_service.py`, `apps/api/app/services/eval_report_service.py`, `scripts/eval_quality_gate.py`, `scripts/eval_ai_quality.py`, `scripts/eval_extraction_quality.py`, `scripts/eval_mcp_contract.py`, `scripts/eval_research_sprints.py`, `apps/api/app/features/evals/*` | Typed eval DTO boundary validation is implemented for gate results, shared metric records, UI-safe report failures, LangSmith export results, OpenTelemetry metric points, eval-run summaries, token/cost summaries, and cache diagnostics. Already implemented: gate result parsing/shaping, rerun metadata, shared local metric records, research case loading/scoring, LangSmith export payload shaping, local metric export payload assembly, report file readers/writers/summary shaping, missing-report payloads, malformed/unreadable report warning payloads, malformed/unreadable trend-read warning payloads, trend-write warning payloads, live-provider-unavailable warning metric shaping, aggregate summary shaping, token/cost projection, trace IDs, and live cache metric projection. Keep CLI parsing, subprocess execution, live API fetches, local report directory selection, required project/API setup, full gate execution, trend persistence policy, and external upload side effects script/service-owned. | `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_research_history_eval.py app/tests/test_demo_eval_workflows.py app/tests/test_feature_package_boundaries.py -q`; `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-final LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security`; `python3 scripts/eval_research_sprints.py --json`; `python3 scripts/eval_mcp_contract.py --help`; run the full MCP contract with `--project-id` when a live API project is available |
| `S59-R8` context and memory policy helpers | `G49-B`, `G49-C`, `G49-E` | `apps/api/app/services/context_service.py`, `apps/api/app/services/memory_service.py`, `apps/api/app/features/memory/*`, `apps/api/app/features/context/*` if introduced | Context-pack DTO serialization, selected/dropped/compressed/stale/conflict item shapes, memory review metadata/audit DTO helpers, dropped-item reasons, conflict IDs, and Inspect payloads are implemented and pinned. Remaining future cleanup is limited to larger compaction source-selection DTOs, conflict resolution payload DTOs, and any direct feature-owned compiler boundary; DB reads/writes, approval gates, mutations, audit persistence, and Inspect route orchestration stay service-owned. | `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q` |
| `S59-R9` shared duplication audit | `G49-C`, `G49-D`, `G49-E` | `apps/api/app/ai/*`, `apps/api/app/common/*`, `apps/api/app/features/*`, `docs/BACKEND_FEATURE_PACKAGE_MAP.md` | Audit duplicate prompt/schema repair, fallback completion metadata, audit metadata merge/redaction, proposal/action-card creation, citation/provenance shaping, Markdown rendering, and retrieval result shaping. Centralize only helpers used by multiple features and backed by parity tests; otherwise record the helper as feature-owned. | Focused touched tests, then `cd apps/api && .venv/bin/pytest app/tests/test_ai.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; `python3 scripts/check_feature_boundaries.py` |
| `S59-R10` package-map closeout | `G49-A` through `G49-E` | `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, `README.md`, `IMPLEMENTATION_STATUS.md`, `IMPLEMENTATION_BRIEF.md`, this file | Before committing Sprint 59, the characterization matrix, DTO ledger, shim ledger, dependency rules, intentionally centralized service list, model ownership decision, and future cleanup backlog must include every helper moved or explicitly left behind. | `cd apps/api && .venv/bin/pytest -q`; `cd apps/api && .venv/bin/ruff check app`; `cd apps/api && .venv/bin/python -m compileall app -q`; `python3 scripts/check_feature_boundaries.py`; `git diff --check`; conflict-marker scan |

#### Sprint 59 Row Closure Checklist

Use this checklist to close each `S59-R*` row. The row is still open if any
unchecked item remains, even if the code compiles.

- `S59-R1` retrieval execution DTOs:
  - [x] Decide whether to introduce typed request/result/cache DTOs for
    `retrieve_evidence`, `retrieve_evidence_results`,
    `retrieve_evidence_search`, `retrieve_evidence_pipeline`,
    `_retrieve_single_query_search`, `_retrieve_with_sql_vector_search`,
    `_retrieve_with_python_scoring`, `_load_candidates`, `_score_candidates`,
    `_serialize_result`, and `_rerank_results`. Sprint 59 does not introduce
    the broader execution DTO set; the DTO ledger records retrieval request/
    result fields and assigns typed `RetrievalPlan`, `RetrievalCandidate`,
    `RerankedResult`, and `RetrievalContextSelection` to future cleanup.
  - [x] Because broader DTOs are not added in Sprint 59, leave old dict keys,
    conversion points, service-owned DB/cache/query responsibilities, and
    compatibility tests recorded in `docs/BACKEND_FEATURE_PACKAGE_MAP.md`
    rather than adding new route-facing DTO classes in this slice.
  - [x] Explicitly mark DB retrieval
    execution, cache lookup/write/invalidation, SQL/vector query paths,
    embedding similarity, candidate loading, citation enrichment/persistence,
    and route orchestration as service-owned future cleanup.
- `S59-R2` evidence extraction boundaries:
  - [x] Move direct URL response metadata, file identity metadata, image upload
    metadata, text upload metadata, PDF parser metadata, and OCR fallback
    metadata into `app.features.evidence.extraction` behind service
    compatibility aliases.
  - [x] Review `add_url_source`, `add_discovered_url_source`,
    `add_discovered_url_snapshot`, `add_file_source`, `reprocess_source`,
    `_process_source_text`, `_merge_source_chunk_metadata`, `_fetch_url`,
    `_parse_file`, `_validate_fetch_target`, and
    `_record_ingestion_security_event`. The package map records these as mixed
    ingestion/orchestration entrypoints and keeps fetch validation, storage,
    persistence, security events, embedding writes, and transactions
    service-owned for V1.
  - [x] Move or document only pure normalization/provenance helpers in
    `app.features.evidence.extraction` or `app.features.evidence.source_provenance`.
    Implemented and documented shapes include fetch/response metadata,
    upload/PDF extraction metadata, OCR/multimodal fallback metadata, table
    artifact metadata, source-quality factors/explanations, quote offsets,
    parser warnings, and provider-unavailable warnings; source/chunk
    persistence remains a service boundary.
  - [x] Keep storage, transactions, source/chunk persistence, security-event
    writes, and route orchestration service-owned unless a typed ingestion DTO
    and route-contract tests are added.
- `S59-R3` validation proposal and parse DTOs:
  - [x] Review `extract_assumptions_and_risks`, `generate_validation_plan`,
    `interpret_validation_results`, `log_experiment_result`,
    `_validation_result_interpretation_messages`,
    `_interpretation_notes`, `_write_validation_interpretation`,
    `_validation_interpretation_proposed_updates`,
    `_create_validation_interpretation_approval`, and
    `apply_validation_interpretation_approval`. The package map records prompt/
    fallback/proposed-update helpers as feature-owned and keeps provider calls,
    artifact/mission persistence, approvals, memory writes, confidence
    mutation, and DB commits service-owned.
  - [x] Move validation mission context projection, result-interpretation prompt
    payload construction, and interpretation proposed-update payload shaping
    into `app.features.validation.result_interpretation` behind
    `validation_service.py` compatibility aliases/wrappers.
  - [x] Move or document service ownership for experiment-result parsing,
    broader validation generation input/outcome DTOs, validation-plan proposal
    payloads, validation interpretation outcome DTOs, approval/rejection
    metadata not already pinned, DB-backed decision-recommendation drafts, and
    any remaining weak-evidence label DTOs. The DTO ledger records validation
    result interpretation and validation generation fields, while experiment
    result parsing, typed generation/result/proposal DTOs, and DB-backed
    proposal orchestration remain future cleanup.
  - [x] Keep provider calls, AI run accounting, artifact/mission creation,
    approval persistence, memory writes, confidence mutation, and DB commits
    service-owned unless route-level no-mutation and rejection tests cover the
    new boundary.
- `S59-R4` research graph-safe helpers:
  - [x] Review `run_agentic_research`, `_research_context`,
    `_plan_subquestions`, `_select_tool_calls`, `_execute_tool_calls`,
    `_source_reader_results`, `_select_evidence`, `_detect_gaps`,
    `_follow_up_retrieval`, `_generate_memo`, `_memo_messages`,
    `_critic_review`, `_write_research_memo_step`, `_fallback_memo`,
    `_audit_citations`, `_evidence_bundles`, and `_to_jsonable`. The package
    map records pure graph-state, planning, strategy, memo prompt, citation
    audit, proposal, and source-discovery helpers as feature-owned and keeps
    LangGraph/Temporal/DB/tool/provider side effects service-owned.
  - [x] Move `_to_jsonable` and `_json_safe` graph step output serialization
    into `app.features.research.graph_state` behind service compatibility
    aliases.
  - [x] Move deterministic subquestion planning, bounded tool-call strategy,
    lookup-tool mapping, lookup payload projection, evidence-gap detection, and
    research text/list normalization into `app.features.research.strategy`
    behind service compatibility aliases/wrappers.
  - [x] Move final memo prompt message assembly, trusted/untrusted context
    splitting, compact payload serialization, and untrusted retrieved-content
    wrapping into `app.features.research.memo_prompting` behind a service
    compatibility alias.
  - [x] Move memo citation-audit shaping, claim support downgrades,
    finding-level citation filtering, citation enrichment/de-dupe, and
    unsupported-claim summary updates into `app.features.research.citation_audit`
    behind a service compatibility alias.
  - [x] Move research sprint planning prompt assembly and deterministic fallback
    plan shaping into `app.features.research.planning` behind service
    compatibility aliases.
  - [x] Move source-discovery prompt payload assembly and draft/candidate
    shaping into `app.features.research.source_discovery` behind service
    compatibility aliases.
  - [x] Move research memo memory-update, validation-plan, and decision proposal
    payload/input shaping into `app.features.research.proposals` behind a
    service compatibility alias.
  - [x] Keep LangGraph construction, Temporal activities/status transitions,
    tool execution, context-pack construction, provider calls,
    structured-output parsing, AI run/step writes, approval writes,
    artifact/claim persistence, tool proposal creation, and project confidence
    mutation service-owned unless dedicated characterization tests pin those
    side effects.
- `S59-R5` guide answer and nudge action DTOs:
  - [x] Review `_stream_grounded_chat_response`,
    `_deterministic_chat_response`, `_proposal_chat_response`,
    `_attach_grounding_metadata`, `_grounded_chat_response`,
    `_search_guide_evidence`, `_grounded_guide_messages`,
    `_bounded_recent_turns`, `_guide_context_from_overview`, `_risk_level`,
    `_biggest_unknown`, `_active_validation_plan_id`, and nudge candidate
    builders in `nudge_service.py`. Moved bounded recent turns, overview
    projection, risk/unknown projection, and grounded prompt assembly into
    `app.features.guide.context_projection` and `app.features.guide.prompting`.
  - [x] Record which remaining guide helpers stay service-owned: active
    workflow DB lookup, context adapter ownership, provider-backed grounded
    generation orchestration, guide eval fixture loading beyond DB counts, AI
    run/cache/cancellation side effects, DB-backed proposal creation, approval
    lookup, citation verifier orchestration, nudge candidate persistence, and
    route orchestration.
  - [x] Do not add broader typed guide orchestration DTOs until final streamed
    and non-streamed payload parity, citation drilldown keys, action-card keys,
    proposal IDs, selected memory IDs, and run/trace metadata are pinned by
    tests.
- `S59-R6` governed tool transport edges:
  - [x] Record service-owned boundaries for `_run_tool`,
    `_authorize_tool_invocation`, `_audit_tool_denial`,
    `_create_tool_approval_request`, `_attach_mcp_metadata`,
    `_call_tool_result`, and approval lookup/write paths. Tool execution,
    auth/RBAC checks, denial audit persistence, approval writes/lookups,
    MCP metadata redaction/persistence, request commits/refreshes, and
    transport orchestration remain service/adapter-owned; pure registry,
    schema guard, audit payload, and MCP protocol serialization helpers are
    feature-owned.
  - [x] Keep live stdio read/proposal smoke assigned to `S60-P4/G44-C` unless
    a real API project and auth context are available before Sprint 59 closes.
- `S59-R7` eval/report failure surfaces:
  - [x] Record why full gate execution, subprocess/cwd selection, report
    directory selection, trend persistence policy, live API fetches, LangSmith
    upload side effects, and required project/API setup remain script or
    service-owned. Feature-owned eval modules now cover gate result DTO
    shaping, metric records, report file readers/writers/summary shaping,
    report/trend failure payloads, provider-unavailable warning metrics,
    LangSmith export payload/result shaping, research case loading/scoring,
    and typed eval/report read models; command execution, cwd/report-dir
    selection, live API fetches, trend policy, external upload, and required
    project/API setup remain script/service-owned.
  - [x] If any of those side effects move, add characterization tests for
    failed command output, malformed JSON output, missing report files,
    unreadable trend rows, unwritable trend files, unavailable live providers,
    redacted LangSmith payloads, and cache metric precedence. No additional
    side-effect movement happened in this closeout; the already-moved failure
    and payload helpers are covered by focused eval report tests.
- `S59-R8` context and memory policy helpers:
  - [x] Review `ContextCompiler`, `build_guide_context_pack`,
    `build_research_context_pack`, `select_memory_for_workflow`,
    `select_memory_for_context`, `inspect_memory`, `explain_memory`,
    `propose_compacted_memory`, `approve_memory_proposal`,
    `reject_memory_proposal`, `detect_memory_conflicts`,
    `resolve_memory_conflict`, and `_compaction_source_items`.
  - [x] Move or document service ownership for context profile serialization,
    selected/dropped/compressed/stale/conflict item shapes, compaction
    source-selection payloads, conflict-resolution payloads, review metadata,
    explanation payloads, and token estimates. Context packing, evidence item
    shaping, memory context-pack serialization, compaction payloads, review
    metadata, selection/conflict helpers, and Inspect/explanation payloads are
    feature-owned in `app.features.context.*` and `app.features.memory.*`;
    package-map rows record the exact service aliases and parity tests.
  - [x] Keep profile selection, DB memory policy queries, approval gates,
    memory mutation, audit persistence, and Inspect route orchestration
    service-owned unless a typed compiler boundary is introduced. The package
    map now explicitly lists `ContextCompiler`, memory DB command/query
    orchestration, compaction source lookup, conflict mutation, approval/audit
    persistence, and Inspect route orchestration as V1 service-owned boundaries.
- `S59-R9` shared duplication audit:
  - [x] Search for duplicate schema instruction, repair prompt, fallback
    completion, redaction, audit metadata merge, proposal/action-card,
    citation/provenance, markdown rendering, and retrieval result shaping
    helpers before deciding whether to centralize.
  - [x] Centralize only behavior used by at least two features and protected by
    parity tests; otherwise record it as feature-owned or service-owned to avoid
    a vague shared utility layer. The package map now records the duplication
    disposition: structured-output schema instruction and repair stay in the AI
    gateway, fallback completion metadata and metadata merge are shared,
    retrieval/citation/audit/MCP helpers are feature-owned, and action-card plus
    Markdown rendering remain feature-specific.
- `S59-R10` package-map closeout:
  - [x] Confirm `docs/BACKEND_FEATURE_PACKAGE_MAP.md` has target packages,
    implemented slices, remaining pickup matrix, characterization matrix, DTO
    ledger, shim ledger, dependency rules, intentionally centralized services,
    model ownership decision, and future cleanup backlog.
  - [x] Confirm `README.md`, `IMPLEMENTATION_STATUS.md`,
    `IMPLEMENTATION_BRIEF.md`, and this TODO all agree on what is implemented,
    service-owned, intentionally out of V1, or future-owned.
  - [x] Run the full Sprint 59 verification commands and remove generated
    `__pycache__` directories before committing.

  Final Sprint 59 closeout verification recorded for pickup:

  - `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
    passed (`70 passed, 1 warning`) for `S59-R8`.
  - `cd apps/api && .venv/bin/pytest app/tests/test_ai.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
    passed (`68 passed, 1 warning`) for `S59-R9`.
  - Initial full backend run exposed a stale static evaluator reference to the
    old evidence service path for `pdf_page_lineage`; `scripts/eval_ai_quality.py`
    was patched to check the feature-owned evidence extraction/provenance files.
  - `cd apps/api && .venv/bin/pytest app/tests/test_demo_eval_workflows.py::test_static_ai_eval_gate_script_passes app/tests/test_eval_reports.py::test_eval_quality_gate_script_writes_reports app/tests/test_eval_reports.py::test_eval_quality_gate_script_exports_langsmith_payload_without_upload -q`
    passed (`3 passed, 1 warning`) after the evaluator patch.
  - `cd apps/api && .venv/bin/pytest -q` passed (`264 passed, 3 warnings`).
  - `cd apps/api && .venv/bin/ruff check app` passed after import-order fixes
    in `app/main.py` and `app/routers/memory.py`.
  - `cd apps/api && .venv/bin/python -m compileall app -q` passed.
  - `python3 scripts/check_feature_boundaries.py` passed.
  - `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-final LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security`
    completed with warn status (`40/40`, no failed checks, warning gates:
    `mcp_contract`, `security_check`).
  - `git diff --check` passed, conflict-marker scan found no matches, and
    generated `__pycache__` directories under `apps/api` were removed.

### Sprint 59 Must-Not-Miss Edge Cases

These are the specific Sprint 49 cleanup gaps that are easy to lose inside the
broader package-refactor rows. Do not commit Sprint 59 until each row is either
implemented or explicitly recorded as service-owned/future-owned in
`docs/BACKEND_FEATURE_PACKAGE_MAP.md` and `IMPLEMENTATION_STATUS.md`.

| Edge case | Gap IDs | File-level pickup directions | Required verification |
|---|---|---|---|
| Provider timeout and fallback metadata | `G49-A`, `G49-C`, `G49-D`, `G49-E` | Implemented in `apps/api/app/ai/fallback_completion.py` and pinned in `apps/api/app/tests/test_ai.py`: fallback completions now preserve the legacy fallback/error keys while adding provider mode, fallback key/reason, model provider/name, redacted provider failure type/message, timeout/cause classification, token/cost defaults, and redacted trace/run metadata. Structured-output repair orchestration still stays in `app.ai.structured_output` until a later repair-dispatch extraction. | `cd apps/api && .venv/bin/pytest app/tests/test_ai.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; keep DTO/shim ledger rows current if more fallback metadata fields are added. |
| Decision recommendation weak-evidence paths | `G49-A`, `G49-B`, `G49-C`, `G49-E` | Implemented in `apps/api/app/features/decisions/recommendation.py`, `apps/api/app/schemas/validation.py`, and `apps/api/app/services/validation_service.py`: decision recommendation and decision-coach responses now expose typed `evidence_labels` for no-supporting-evidence, weak-evidence, weak-validation-signal, and decision-ready cases. Route tests pin insufficient-evidence copy, suggested next action cards, linked evidence IDs, weak-evidence labels, and no-direct-mutation behavior for recommendation/chat calls. DB-backed decision loading/persistence remains service-owned. | `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_project_overview.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; package-map rows name the weak-evidence DTO owner and route/schema compatibility tests. |
| Validation interpretation prompt/proposal payloads | `G49-B`, `G49-C`, `G49-D`, `G49-E` | Implemented in `apps/api/app/features/validation/result_interpretation.py` and `apps/api/app/services/validation_service.py`: mission context projection, skeptical interpretation prompt payloads, raw-note wrapping, and approval proposed-change dictionaries are feature-owned behind service aliases/wrappers. Remaining validation work is explicit: experiment-result parsing, broader generation/result DTOs, DB-backed decision proposal boundaries, provider calls, AI run accounting, approval persistence, memory writes, confidence mutation, audit persistence, DB commits, and route orchestration stay service-owned unless future typed boundaries and route tests are added. | `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_validation_result_interpretation_helpers_are_feature_owned app/tests/test_validation.py::test_interpret_validation_notes_creates_pending_memory_update app/tests/test_validation.py::test_validation_interpretation_rejection_does_not_write_memory_or_confidence app/tests/test_validation.py::test_decision_coach_uses_interpreted_results_and_prefills_record -q`; update `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, `IMPLEMENTATION_STATUS.md`, and this TODO before closing `S59-R3`. |
| Approval rejection and proposal/audit payloads | `G49-A`, `G49-B`, `G49-C`, `G49-D`, `G49-E` | Implemented across `apps/api/app/services/validation_service.py`, `apps/api/app/services/tool_service.py`, `apps/api/app/services/memory_service.py`, `apps/api/app/features/governance_tools/audit.py`, and `apps/api/app/features/memory/review.py`: validation interpretation rejection now pins no confidence/memory/thesis mutation plus approval resolution and audit metadata; governed tool proposal rejection through approval routes now pins tool invocation status, approval resolution, proposed-change shape, and denial audit metadata; memory proposal rejection now archives proposed memory, removes it from Inspect selection/proposal surfaces, writes review provenance, and emits `memory_update_rejected` audit metadata. DB approval writes, memory mutations, and audit persistence remain service-owned. | `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_tool_boundary.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; package-map rows identify governed-tool audit helper ownership, memory-review helper ownership, and service-owned approval/audit persistence. |
| Context compression, conflict, and Inspect serialization | `G49-A`, `G49-B`, `G49-C`, `G49-E` | Implemented across `apps/api/app/services/context_service.py`, `apps/api/app/features/context/packing.py`, `apps/api/app/features/memory/context_pack.py`, `apps/api/app/features/memory/inspection.py`, and `apps/api/app/tests/test_context_compiler.py`: selected memory, stale/excluded memory, conflict IDs, compressed context summaries, unsafe/untrusted external input fallback, tool-output items, token-budget dropped-item reasons, selected-memory metadata, hidden Inspect payloads, and service aliases are pinned. Context compiler orchestration, profile selection, DB memory policy, approval writes, and Inspect route orchestration remain service-owned. | `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; package-map rows identify context packing, memory context-pack, memory Inspect, memory review, and service-owned orchestration boundaries. |
| Route serializer and public contract parity | `G49-A`, `G49-C`, `G49-E` | Implemented in `apps/api/app/tests/test_contract_shapes.py`: evidence source metadata, artifact/version structured content, decision recommendation evidence labels, approval responses, tool invocation responses, audit event responses, memory item responses, and Memory Inspect responses now have route-level key/enum/payload compatibility coverage. Refactors may move internal helpers, but external route payloads must stay pinned until a deliberate API migration is documented. | `cd apps/api && .venv/bin/pytest app/tests/test_contract_shapes.py app/tests/test_tool_boundary.py app/tests/test_memory_service.py app/tests/test_mcp_adapter.py app/tests/test_feature_package_boundaries.py -q`; package-map rows must stay current for any future route serializer touched. |
| MCP/stdout, HTTP, and approval parity | `G49-A`, `G49-B`, `G49-C`, `G49-E` | Implemented across `apps/api/app/mcp/adapter.py`, `apps/api/app/features/mcp/protocol.py`, `apps/api/app/features/governance_tools/*`, `scripts/mcp_stdio_server.py`, `apps/api/app/services/tool_service.py`, and `apps/api/app/tests/test_mcp_adapter.py`: JSON-RPC request IDs, structured error codes, missing/invalid project scope, approval-required proposal shape, denied writes, redacted MCP audit payloads, direct MCP HTTP/JSON-RPC structured-content parity, HTTP tool-invocation route parity, approval-list route parity, approval rejection parity, denial audit metadata, and proposal `output_summary` redaction are pinned. Live stdio read/proposal smoke remains Sprint 60 unless a live API project is available during Sprint 59. | `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py::test_mcp_jsonrpc_proposal_matches_http_approval_and_audit_contracts -q`; `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_security_governance.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`; run or explicitly block live stdio smoke with exact command/output and carry it to `S60-P4/G44-C` if environment-bound. |

### Sprint 60 Pickup Queue: `G41-*` through `G50-*`

| Item | Gap IDs | Required output | Completion bar |
|---|---|---|---|
| `S60-P1` final carried-gap audit | all `G41-*` through `G50-*` | Add the final disposition table to `IMPLEMENTATION_STATUS.md` before writing any new doc prose. Required columns: gap ID, status, owner sprint item, source/doc links, verification command plus result, blocker, future owner, and README/portfolio claim consequence. Use the `Carried Gap Work Items` list as the source of truth and include every `G41-*`, `G42-*`, `G43-*`, `G44-*`, `G45-*`, `G46-*`, `G47-*`, `G48-*`, `G49-*`, and `G50-*` ID exactly once. | Run a duplicate/missing-ID check manually or with a short script, then update README/status language so no claim outruns the disposition table. Sprint 60 cannot close while any ID is missing, duplicated, or described only by sprint-title prose. |
| `S60-P2` context engineering docs and QA | `G42-A` through `G42-D` | Create/update `docs/CONTEXT_ENGINEERING.md`, README links, and final status rows. Required content: context architecture diagram, `ContextCompiler` owner files, every context profile, token budgets, source inventory, memory/retrieval/tool inputs, selected/dropped/compressed/stale/conflict/unsafe item examples, untrusted-content wrapping, Inspect behavior, eval commands, fixture IDs, expected failures, and "how to add a profile" steps. | Run `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`. Retry web typecheck/tests and IDE browser QA for Context Inspect rows; if blocked, record the exact command, error, retry condition, and next owner under `G42-C`. |
| `S60-P3` memory system docs and QA | `G43-A` through `G43-D` | Create/update `docs/MEMORY_SYSTEM.md`, README links, and final status rows. Required content: memory type inventory, lifecycle diagram, capture/proposal/approval/rejection flow, active/compacted/preference/conflict/superseded/archived states, review and audit records, context-pack eligibility, compaction thresholds, conflict keep/supersede/archive/merge behavior, and "how to add a memory type" steps. | Run `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`. Browser-check Memory Inspect filters, proposals, compaction, selection reasons, conflict actions, and hidden advanced details, or record the exact blocker under `G43-D`. |
| `S60-P4` MCP integration docs and smoke | `G44-A` through `G44-D` | Create/update `docs/MCP_INTEGRATION.md`, README links, and final status rows. Required content: initialize/capability negotiation, `tools/list`, read `tools/call`, approval-required `tools/call`, denied write, invalid params, missing project scope, structured errors, redacted audit examples, stdio command, HTTP/SSE command, client config, env vars, auth headers, project/workspace scoping, known client limits, and advanced settings placement. | Run `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_feature_package_boundaries.py -q`. Run or explicitly block live stdio/API read and proposal smokes, denied-write smoke, invalid-param smoke, and missing-scope smoke; record exact command/output or blocker under `G44-C`. |
| `S60-P5` retrieval and citation docs | `G45-A` through `G45-D`, cache portion of `G45-B` | Create/update `docs/RETRIEVAL_AND_CITATIONS.md`, README links, and final status rows. Required content: retrieval pipeline diagram, query planning, Postgres `ts_rank` and BM25-like limitation notes, pgvector/vector fallback, hybrid scoring, MMR/source diversity, source-quality weighting, reranker provider interface, retrieval/rerank/embedding/guide-answer cache keys and invalidation inputs, citation verifier owner matrix, artifact coverage, unsupported/weak-claim policy, golden fixture IDs, commands, metrics, and current output. | Run `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py app/tests/test_feature_package_boundaries.py -q`; run `python3 scripts/eval_retrieval_quality.py` if present, otherwise record the replacement eval command and missing-script disposition under `G45-D`. |
| `S60-P6` Ask Thesys streaming docs and QA | `G46-A` through `G46-D` | Create/update README or guide docs plus final status rows. Required content: event names, ordering, payload IDs, final-payload parity, cancellation, timeout, error/fallback behavior, retrieval/tool/proposal events, action-card fields, citation drilldown fields, selected memory/run/trace IDs, hidden diagnostics, guide eval fixture IDs, malformed-event behavior, deterministic fallback parity, and steps to add guide cases. | Run `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`, then `pnpm --filter thesys-web typecheck`, `pnpm --filter thesys-web test`, and IDE browser QA for streamed deltas, cancellation, timeout, proposal cards, citation drilldowns, and no main-workflow clutter; record exact registry/browser blocker under `G46-B`/`G46-C` if unavailable. |
| `S60-P7` evals and observability docs | `G47-A` through `G47-D`, cache/budget portions from Sprints 54 and 57 | Create/update `docs/EVALS_AND_OBSERVABILITY.md`, README links, and final status rows. Required content: aggregate/per-gate commands, pass/warn/fail policy, unavailable-gate behavior, artifact paths, report/trend schemas, JSONL trend location, failed-slice reruns, changelog locations, OpenTelemetry metric names, LangSmith settings, redaction behavior, trace IDs, budget-denial metrics, cache hit/miss/stale-denial counts, saved token/cost/latency examples, CI usage, and hidden report QA. | Run `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60 LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json`, plus focused eval-report tests. Browser-check hidden eval report state, trend rows, failing links, budget/cache/cost metrics, and no dashboard clutter, or record exact blocker under `G47-D`. |
| `S60-P8` source intelligence dispositions | `G48-A` through `G48-E` | Create/update `docs/SOURCE_INTELLIGENCE.md`, README links, and final status rows. Required content: maintained parser dependency decision versus deterministic `html.parser` fallback, parser/version/confidence metadata, page/screenshot storage disposition, screenshot-region OCR/table scope, named future backlog item when outside V1, Tavily/multimodal provider smoke commands or unavailable warnings, provenance field inventory, source-quality explanation, Project Inspect trust-summary QA, and browser provenance QA. | Run `python3 scripts/eval_extraction_quality.py --json`. Run or explicitly block live Tavily and multimodal provider smokes with credentials/provider mode/egress allowlists. Retry web typecheck/tests and browser QA for Evidence/retrieval/guide/research/source-discovery provenance and Project Inspect trust summaries, or record exact blockers under `G48-D`/`G48-E`. |
| `S60-P9` security and deployment posture | `G41-A` through `G41-E`, deployment portion of `G50-D` | Create/update `docs/DEPLOYMENT_SECURITY.md`, README links, and final status rows. Required content: environment profiles, env var table, auth mode table, dev-header isolation, JWT/OIDC/JWKS expectations, API key/service-account lifecycle, token/key rotation and revocation, provider egress policy, SSRF/provider denial behavior, redaction before egress, dependency audit runbook, object-storage boundaries, backup/restore for Postgres/pgvector/eval artifacts/traces/audit logs, hosted-demo smoke commands, and exact unavailable infrastructure blockers. | Run or block `python3 scripts/security_check.py`, `python3 scripts/audit_dependencies.py`, `pip-audit`, `pnpm audit --prod`, and hosted smokes for project load, evidence, Ask Thesys, validation, decision, memory/context Inspect, MCP read tool, and eval report. Record exact outputs/blockers under `G41-*` and `G50-D`. |
| `S60-P10` post-refactor navigation and code docs | final `G49-*`, `G50-A` through `G50-E` | After Sprint 59 only, update README, `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, targeted docstrings/comments, and final status rows. Required content: source-linked diagrams, AI engineering feature/pattern/technology tour, project navigation, hidden advanced surfaces, final package map, characterization matrix, DTO/shim ledger, intentionally centralized services, future cleanup backlog, "how to add" docs for workflows/context/memory/MCP/retrieval/rerankers/extractors/security/evals, and honest portfolio limits. | Run final Sprint 59/60 docs checks, `python3 scripts/check_feature_boundaries.py`, `git diff --check`, conflict-marker scan, targeted backend tests for touched docs/code examples where applicable, and README claim audit. Docstrings/comments must cover public entrypoints, DTOs, approvals, Temporal invariants, security boundaries, prompt-injection boundaries, and non-obvious orchestration without noisy restatements. |

#### Sprint 60 Required Artifact Checklist

Sprint 60 is the final disposition sprint. Each `S60-P*` item must leave a
concrete artifact, not only prose in a commit message.

Before checking any `S60-P*` item, update all three handoff surfaces together:

- the owning doc or source file named by the row
- README navigation or portfolio language when the user/interviewer should see
  the capability or limitation
- `IMPLEMENTATION_STATUS.md` rows for every owned `G*` ID, including exact
  commands, concise output or blocker, next owner when deferred, and portfolio
  claim impact

- `S60-P1` final gap disposition:
  - [x] Add one `IMPLEMENTATION_STATUS.md` table row for every `G41-*` through
    `G50-*` ID.
  - [x] Each row must include status, owner sprint item, source/doc links,
    exact verification command and result or exact blocker, future owner when
    deferred, and README/portfolio claim consequence.
  - [x] Check that no `G*` ID appears twice and none are missing.
- `S60-P2` context engineering:
  - [x] Create `docs/CONTEXT_ENGINEERING.md` with source-linked diagram,
    profile table, owner files, token budgets, context source inventory,
    required/optional items, memory filters, compression policy,
    stale/conflict/unsafe handling, dropped-context examples, untrusted-content
    wrapping, Inspect behavior, eval commands, and "add a profile" steps.
  - [x] Link it from README and add `G42-A` through `G42-D` status rows.
- `S60-P3` memory system:
  - [x] Create `docs/MEMORY_SYSTEM.md` with memory type inventory, lifecycle
    diagram, capture/proposal/approval/rejection flow, compaction thresholds,
    preference edit/archive behavior, conflict keep/supersede/archive/merge
    behavior, audit/context links, extension steps, and Memory Inspect QA.
  - [x] Link it from README and add `G43-A` through `G43-D` status rows.
- `S60-P4` MCP integration:
  - [x] Create `docs/MCP_INTEGRATION.md` with initialize/capability,
    `tools/list`, read `tools/call`, approval-required `tools/call`, denied
    write, invalid params, missing scope, redacted audit output, stdio command,
    HTTP/SSE command, client config, env vars, auth/project scope, known limits,
    and smoke output or exact blocker.
  - [x] Link it from README and add `G44-A` through `G44-D` status rows.
- `S60-P5` retrieval and citations:
  - [x] Create `docs/RETRIEVAL_AND_CITATIONS.md` with pipeline diagram,
    Postgres `ts_rank` and BM25-like limitation notes, pgvector/vector fallback,
    hybrid scoring, MMR/source diversity, source-quality weighting, reranker
    provider interface, cache keys/invalidation, citation verifier ownership,
    artifact coverage matrix, unsupported/weak-claim policy, golden fixture
    IDs, commands, metrics, and current output.
  - [x] Link it from README and add `G45-A` through `G45-D` status rows.
- `S60-P6` Ask Thesys streaming:
  - [x] Document the stream event contract with event names, ordering, payload
    IDs, final-response parity, cancellation, timeout, error/fallback,
    proposal/action cards, citation drilldown fields, hidden diagnostics,
    guide eval fixture IDs, commands, malformed-event behavior, and browser QA.
  - [x] Link it from README or relevant docs and add `G46-A` through `G46-D`
    status rows.
- `S60-P7` evals and observability:
  - [x] Create `docs/EVALS_AND_OBSERVABILITY.md` with aggregate/per-gate
    commands, pass/warn/fail policy, unavailable-gate policy, artifact paths,
    report/trend schemas, failed-slice reruns, AI changelog locations,
    OpenTelemetry metric names, LangSmith settings, redaction behavior,
    cache/cost examples, CI use, and hidden report QA.
  - [x] Link it from README and add `G47-A` through `G47-D` status rows.
- `S60-P8` source intelligence:
  - [x] Create `docs/SOURCE_INTELLIGENCE.md` with parser dependency decision,
    deterministic fallback tradeoffs, page/screenshot storage disposition,
    screenshot-region OCR/table scope, live Tavily/multimodal smoke command or
    unavailable warning, provenance field inventory, source-quality explanation,
    Project Inspect trust-summary QA, and browser provenance QA.
  - [x] Link it from README and add `G48-A` through `G48-E` status rows.
- `S60-P9` security and deployment:
  - [x] Create `docs/DEPLOYMENT_SECURITY.md` with environment profiles, env var
    table, auth mode table, JWT/OIDC/JWKS expectations, API key/service-account
    lifecycle, rotation/revocation, provider egress policy, SSRF/provider denial
    behavior, dependency audit runbook, object storage, backup/restore,
    hosted-demo smoke commands, and exact unavailable-infrastructure blockers.
  - [x] Link it from README and add `G41-A` through `G41-E` plus `G50-D`
    status rows.
- `S60-P10` post-refactor navigation and code docs:
  - [x] Update README with project navigation, AI engineering portfolio tour,
    feature-to-pattern-to-technology table, source links, hidden advanced
    surfaces, and honest limits.
  - [x] Update `docs/BACKEND_FEATURE_PACKAGE_MAP.md` after Sprint 59 and add
    "how to add" docs for workflows, memory types, context profiles, MCP tools,
    retrieval providers/rerankers, source extractors, security checks, and eval
    cases.
  - [x] Add targeted docstrings/comments for public entrypoints, DTOs, approval
    gates, Temporal determinism, security boundaries, prompt-injection
    boundaries, and non-obvious orchestration.
  - [x] Add `G49-*` and `G50-A` through `G50-E` status rows.

### Sprint 60 Step-by-Step Pickup Notes

- `S60-P1`: build the final disposition table first. Use the `Carried Gap Work
  Items` list as the source of truth and add exactly one row for every `G41-*`
  through `G50-*` ID. Each row needs status, source/doc link, verification
  command plus result, blocker text when applicable, and future owner when
  deferred.
- `S60-P2`: create `docs/CONTEXT_ENGINEERING.md` before touching README. Include
  context profile table, source file owners, token budget table, profile policy
  table, dropped/stale/conflict examples, Inspect screenshot/browser notes or
  blocker, and eval commands with expected output. Then link it from README.
- `S60-P3`: create `docs/MEMORY_SYSTEM.md` with lifecycle diagram, memory type
  inventory, proposal/review flow, compaction policy, preference edit/archive
  path, conflict-resolution path, audit/context links, "add a memory type"
  steps, and browser QA disposition.
- `S60-P4`: create `docs/MCP_INTEGRATION.md` with JSON-RPC examples for
  `initialize`, `tools/list`, read `tools/call`, approval-required
  `tools/call`, denied write, invalid params, missing scope, and redacted audit
  output. Include stdio and HTTP/SSE commands exactly as run or blocked.
- `S60-P5`: create `docs/RETRIEVAL_AND_CITATIONS.md` with owner files,
  retrieval diagram, scoring/rerank/cache sequence, BM25-like limitation
  statement, citation verifier coverage matrix, unsupported-claim behavior,
  provider/reranker extension steps, and eval commands.
- `S60-P6`: document the Ask Thesys streaming event contract before browser QA.
  Verify or block web typecheck, web tests, streaming deltas, cancellation,
  timeout, live events, final parity, action/proposal cards, citation
  drilldowns, and collapsed diagnostics.
- `S60-P7`: create `docs/EVALS_AND_OBSERVABILITY.md` with aggregate and
  per-gate commands, artifact paths, report/trend schema, failed-slice rerun
  commands, unavailable-gate policy, OpenTelemetry names, LangSmith export
  setup, redaction behavior, and cache/cost examples.
- `S60-P8`: create `docs/SOURCE_INTELLIGENCE.md` and explicitly decide
  `G48-A`, `G48-B`, and `G48-C`. Do not leave parser/screenshot/screenshot-OCR
  scope implicit. Run extraction evals and live provider QA when configured, or
  record exact unavailable warnings and rerun commands.
- `S60-P9`: create `docs/DEPLOYMENT_SECURITY.md` with environment profile
  table, env var table, auth mode table, JWT/OIDC/JWKS expectations, API
  key/service account lifecycle, provider-egress/SSRF policy, dependency audit
  runbook, backup/restore boundaries, hosted-demo smoke checklist, and exact
  blockers for unavailable infrastructure. This closes `G41-A` through `G41-E`
  and the deployment-doc portion of `G50-D`.
- `S60-P10`: after Sprint 59 only, update README navigation, AI engineering
  tour, `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, and targeted docstrings/comments.
  This step must remove or qualify any portfolio claim that lacks code,
  tests/evals, docs, or a status row.

## Sprint 51: Unified Context Compiler, Memory V2, and Context Evals

Completion scope: Sprint 51 landed the core context and memory implementation,
but it does not fully close the original Sprint 42 or Sprint 43 gaps until
`S60-P2` disposes `G42-A` through `G42-D` and `S60-P3` disposes `G43-A`
through `G43-D`. The remaining work is source-linked documentation, extension
guides, deferred browser QA, and exact status rows in `IMPLEMENTATION_STATUS.md`.

- [x] Land code for Sprint 42 context gaps: centralize context assembly, add
  workflow context profiles, route major LLM workflows through the same
  compiler, preserve provenance, compress older context, detect stale/
  conflicting context, and add local context-quality evals.
- [x] Land code for Sprint 43 memory gaps: add compaction, preference capture,
  conflict resolution, memory browser UI, memory proposal review, and memory
  selection inside context packs.
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

Residual handoff that still belongs in the TODO:

- [ ] `S60-P2/G42-A` through `G42-D`: add `docs/CONTEXT_ENGINEERING.md`,
  README links, context profile/token budget/source inventory tables,
  dropped/stale/conflict examples, prompt-injection boundary notes, eval
  commands, and an `IMPLEMENTATION_STATUS.md` row for each context gap.
- [ ] `S60-P2/G42-C`: rerun IDE browser QA for Context Inspect included,
  dropped, compressed, stale, conflicting, unsafe, and tool-output rows; if
  blocked, record the exact command, registry/browser error, retry condition,
  and future owner under `G42-C`.
- [ ] `S60-P3/G43-A` through `G43-D`: add `docs/MEMORY_SYSTEM.md`, README
  links, memory lifecycle diagram, memory type inventory, proposal/review and
  conflict-resolution docs, "how to add a memory type" steps, and status rows
  for each memory gap.
- [ ] `S60-P3/G43-D`: browser-check memory filters, proposals, compaction
  records, selection reasons, keep/supersede/archive/merge conflict actions,
  and hidden-by-default advanced details; record an exact blocker if unavailable.

## Sprint 52: Real MCP Server and External Agent Harness

Completion scope: Sprint 52 landed the MCP implementation path, but the
original Sprint 44 gap is not fully closed until `S60-P4` disposes `G44-A`
through `G44-D`. The remaining work is lifecycle/client documentation,
stdio/API smoke output, structured denial/error/redaction examples, advanced
settings placement, and status rows with exact blockers if external smoke
checks cannot run.

- [x] Land code for Sprint 44 MCP gaps: replace MCP-shaped HTTP-only behavior
  with a real JSON-RPC lifecycle, local stdio bridge, client examples, contract
  evals, and governed tool-call behavior that can be exercised by external
  agents.
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

Residual handoff that still belongs in the TODO:

- [ ] `S60-P4/G44-A`: add `docs/MCP_INTEGRATION.md` lifecycle diagrams for
  `initialize`, capability negotiation, `tools/list`, `tools/call`,
  RBAC/risk guard, approval request, denial/error, audit, redaction, stdio, and
  HTTP/SSE paths.
- [ ] `S60-P4/G44-B`: document exact stdio and HTTP/SSE client commands,
  client config, required env vars, auth headers, project/workspace scoping,
  and known client limitations after the Sprint 59 package refactor.
- [ ] `S60-P4/G44-C`: run or explicitly block MCP smoke checks for a read tool,
  an approval-required proposal tool, denied write, invalid params, missing
  project scope, structured error, and redacted audit payload. Record command
  output or exact blocker in `IMPLEMENTATION_STATUS.md`.
- [ ] `S60-P4/G44-D`: if any MCP integration settings UI is added, keep it
  under developer/advanced navigation and browser-check that the homepage and
  primary project workflow remain unchanged.

## Sprint 53: True Ask Thesys Streaming and Live Tool Events

Completion scope: Sprint 53 landed backend streaming, events, cancellation,
timeouts, and citation drilldowns, but the original Sprint 46 gap is not fully
closed until `S60-P6` disposes `G46-A` through `G46-D`. The remaining work is
web typecheck/test retry, IDE browser QA for the streaming/citation workflow,
event-contract documentation, guide eval handoff docs, and exact registry or
browser blockers if the checks remain unavailable.

- [x] Land code for Sprint 46 Ask Thesys gaps: make Ask Thesys streaming
  incremental, expose live retrieval/tool/proposal progress, support
  cancellation/timeouts, add citation drilldowns, and expand guide evals beyond
  the current SSE-shaped response.
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

Residual handoff that still belongs in the TODO:

- [ ] `S60-P6/G46-A`: document Ask Thesys stream event names, event ordering,
  payload IDs, final-payload parity, cancellation, timeout, error/fallback,
  proposal/action-card fields, citation drilldown fields, and hidden diagnostic
  metadata.
- [ ] `S60-P6/G46-B`: rerun `pnpm --filter thesys-web typecheck` and
  `pnpm --filter thesys-web test`; paste exact pass/fail output or registry
  blocker into `IMPLEMENTATION_STATUS.md`.
- [ ] `S60-P6/G46-C`: IDE-browser-check deterministic/provider answer deltas,
  retrieval/tool/proposal events, cancellation, timeout fallback, final metadata
  parity, action cards, collapsed citation drilldowns, and no homepage/main
  workflow clutter.
- [ ] `S60-P6/G46-D`: document guide eval fixture IDs, commands, event-order
  expectations, failure interpretation, and extension steps for new guide
  behavior cases.

## Sprint 54: Security, Abuse, and Production Auth Hardening

Completion scope: Sprint 54 landed runtime enforcement and core security
hardening, but the original Sprint 41 residuals remain open until `S60-P9`
disposes `G41-A` through `G41-E`. The Sprint 47 pre-call budget slice is also
not fully documented until `S60-P7` records the eval/observability runbook
pieces that reference budget and denial reporting. Remaining work includes
strict dependency-audit disposition, hosted-demo auth posture, OIDC/JWKS
runbook, provider-egress verification, backup/restore, hosted smoke, and exact
tooling/infrastructure blockers.

- [x] Land code for Sprint 41 security gaps: add real quota/concurrency
  protection, dependency audit commands, provider-egress controls, production
  auth shape, and a formal threat model for the concrete attack surfaces
  already in the repo.
- [x] Land code for the Sprint 47 pre-call budget gap: enforce token/cost
  budgets before expensive model/search/extraction work starts, not only after
  AI accounting.
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

Residual handoff that still belongs in the TODO:

- [ ] `S60-P9/G41-A`: run `python3 scripts/security_check.py`,
  `python3 scripts/audit_dependencies.py`, `pip-audit` when installed, and
  `pnpm audit --prod`; record pass/warn/fail output, unavailable-tool behavior,
  registry blockers, and strict-CI policy.
- [ ] `S60-P9/G41-B`: document local/dev, deterministic demo,
  provider-backed demo, staging-like, and production-like auth modes with env
  vars, dev-header behavior, disabled provider paths, and verification commands.
- [ ] `S60-P9/G41-C`: add the production auth runbook for JWT/OIDC/JWKS,
  API-key/service-account lifecycle, token/key rotation, revocation, audit
  attribution, workspace membership, and known limitations.
- [ ] `S60-P9/G41-D`: document provider allowlists, SSRF/provider denial,
  timeout/response-size/retry policy, redaction before egress, and tests or
  smoke commands proving denied provider calls are audited.
- [ ] `S60-P9/G41-E`: document Postgres/pgvector, object storage, eval report,
  trace, and audit-log backup/restore boundaries; run or explicitly block hosted
  smoke for project load, evidence, Ask Thesys, validation, decision,
  memory/context Inspect, MCP read tool, and eval report.
- [ ] `S60-P7/G47-A` and `G47-C`: make sure pre-call budget denials from Sprint
  54 are included in the quality-gate runbook, observability metric docs,
  report examples, and final status disposition.

## Sprint 55: Retrieval Quality V2 and Golden Evals

Completion scope: Sprint 55 landed retrieval/citation quality behavior, but the
original Sprint 45 gap is not fully closed until `S60-P5` disposes `G45-A`
through `G45-D`. The remaining work is source-linked retrieval/citation docs,
BM25-like and `ts_rank` limitation notes, provider/reranker extension steps,
cache invalidation documentation, citation verifier ownership, and eval handoff
instructions.

- [x] Land code for Sprint 45 retrieval/citation gaps: add real text-search
  ranking, diversity controls, swappable reranking, labeled retrieval evals, and
  consistent citation support verification across generated artifacts.
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

Residual handoff that still belongs in the TODO:

- [ ] `S60-P5/G45-A`: add `docs/RETRIEVAL_AND_CITATIONS.md` with source-linked
  pipeline diagram for query planning, Postgres text rank, vector fallback,
  hybrid scoring, MMR/source diversity, source-quality weighting, reranking,
  cache lookup/invalidation, context assembly, and citation verification.
- [ ] `S60-P5/G45-B`: document the exact BM25-like approximation,
  Postgres `ts_rank` limits, deterministic fallback behavior, reranker provider
  interface, cache invalidation inputs, and steps to add a provider or reranker.
- [ ] `S60-P5/G45-C`: document citation verifier ownership by artifact type,
  not-applicable paths, weak/unsupported claim handling, and how to extend
  verifier coverage for a new generated artifact.
- [ ] `S60-P5/G45-D`: document golden-set fixture IDs, commands, metrics,
  report paths, expected pass/warn/fail behavior, and final retrieval/citation
  verification output in `IMPLEMENTATION_STATUS.md`.

## Sprint 56: Observability V2, CI Gates, and Eval Reports

Completion scope: Sprint 56 landed the local quality-gate/reporting system, but
the original Sprint 47 gap is not fully closed until `S60-P7` disposes
`G47-A` through `G47-D`. The remaining work is the complete runbook, report and
trend artifact documentation, OpenTelemetry/LangSmith setup notes, cache/cost
examples, hidden eval-report browser QA, and exact unavailable-gate policy.

- [x] Land code for Sprint 47 observability gaps: turn local accounting/eval
  checks into repeatable gates with traces, metrics, reports, trends,
  changelogs, and hidden developer surfaces.
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

Residual handoff that still belongs in the TODO:

- [ ] `S60-P7/G47-A`: add `docs/EVALS_AND_OBSERVABILITY.md` with aggregate and
  per-gate commands, pass/warn/fail policy, unavailable-gate handling,
  artifact paths, rerun-only-failed-slice commands, and CI usage.
- [ ] `S60-P7/G47-B`: document JSON/Markdown/HTML report locations, JSONL trend
  persistence, metadata fields, prompt/schema/context/retrieval/memory/tool
  changelog locations, and regression interpretation.
- [ ] `S60-P7/G47-C`: document OpenTelemetry-compatible metric names,
  LangSmith export settings, redaction behavior, cache/cost examples, trace IDs,
  and local versus external export behavior.
- [ ] `S60-P7/G47-D`: rerun hidden eval-report Inspect browser QA for collapsed
  gate details, trend rows, failing-case links, budget/cache/cost metrics, and
  no homepage/dashboard clutter; record exact blocker if web deps still fail.

## Sprint 57: Semantic Caching and Cost Optimization

Completion scope: Sprint 57 landed the cache implementation, but its residual
documentation/QA is routed through `S60-P5` and `S60-P7`: `G45-B` for retrieval
and reranker cache invalidation/extension notes, and `G47-A`/`G47-C` for
quality-gate, cache/cost metric, and observability examples. Do not mark the
cache work fully closed until those docs, web/browser retries, and status rows
exist or are explicitly deferred with owners.

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

Residual handoff that still belongs in the TODO:

- [ ] `S60-P5/G45-B`: add retrieval-plan, rerank-result, embedding, and optional
  guide-answer cache invalidation details to the retrieval docs, including every
  version input that prevents stale evidence, memory, thesis, decision,
  provider, prompt, schema, retrieval-policy, and context-pack reuse.
- [ ] `S60-P7/G47-A` and `G47-C`: add cache diagnostics to the eval/observability
  runbook: cache hit/miss/stale-denial counts, saved token/cost/latency metrics,
  stale-cache denial examples, report locations, and failed-slice rerun commands.
- [ ] `S60-P7/G47-D`: browser-check AI status tooltip cache posture, Evidence
  retrieval diagnostic cache lines, and hidden eval cache metrics, or record the
  exact web dependency/browser blocker and future owner.

## Sprint 58: Source Intelligence and Document AI V2

Completion scope: Sprint 58 landed the deterministic local source-intelligence
path, but the original Sprint 48 gap is not fully closed until `S60-P8`
disposes `G48-A` through `G48-E`. Remaining work must explicitly decide
maintained parser dependency versus deterministic fallback, true page/screenshot
artifact storage, screenshot-region OCR/table scope, live Tavily/multimodal QA,
provenance browser QA, Project Inspect trust summaries, and exact future owners
for any productization items left outside V1.

- [x] Land local code for Sprint 48 source-intelligence behavior: messy HTML/PDF
  evidence, inspectable page/section/table/OCR provenance, richer
  source-quality scoring, retrieval use of source quality, and explicit
  provider-unavailable warnings.
- [x] Route fetched HTML extraction through
  `apps/api/app/services/evidence_service.py` and preserve raw fetch metadata,
  canonical/final URLs, parser/provider metadata, normalized text, section
  headings, section offsets, warnings, and fallback metadata.
- [x] Add messy HTML and prompt-injected HTML fixtures that assert boilerplate
  removal, script/style stripping, title handling, section names, section
  offsets, prompt-injection marker propagation, and fallback behavior.
- [x] Persist snapshot metadata separately from normalized text through
  `apps/api/app/services/source_provenance_service.py`: capture URL, final URL,
  canonical URL, fetched timestamp, content hash, byte hash, byte size,
  redaction status, retention policy, source snapshot ID, screenshot
  availability, and explicit local-mode storage absence reason.
- [x] Add OCR fallback metadata for scanned/low-text PDFs and image extraction:
  extraction method, provider/model, confidence, page numbers, warnings, and a
  deterministic test path that does not require OCR binaries or live multimodal
  credentials.
- [x] Add deterministic OCR test coverage for marker-present, marker-missing,
  low-confidence, provider-unavailable, and local deterministic fallback paths.
- [x] Add positive table extraction artifacts for text/PDF-like content:
  headers, rows, cells, plain-text summaries, page/region provenance,
  confidence, and searchable extraction metadata.
- [x] Add table-heavy fixture coverage proving headers, rows, cells, page/region
  metadata, summaries, confidence, and retrieval/rerank behavior are not limited
  to `table_extraction.enabled: false`.
- [x] Add chunk-level quote provenance with `extraction_method`,
  `source_snapshot_id`, `page_number`, `section_heading`, `table_id`, `region`,
  confidence, normalized quote offsets, and source artifact metadata.
- [x] Add offset/provenance tests that fail if chunking or whitespace
  normalization causes the stored quote offsets to drift.
- [x] Add richer source-quality scoring for authority, freshness,
  canonical/deduped status, extraction confidence, injection markers, source
  type, OCR confidence, table confidence, screenshot availability, standard text
  extraction quality, retrieval weight, factors, explanation, and policy
  version.
- [x] Feed source quality into deterministic retrieval/reranking as a boost or
  warning while keeping relevant lower-quality evidence inspectable.
- [x] Prove source quality affects retrieval/context in tests: equivalent
  higher-quality evidence ranks higher, lower-quality evidence remains
  inspectable, and prompt-injected evidence is not promoted by semantic
  relevance alone.
- [x] Normalize Sprint 58 provenance fields before UI wiring:
  `extraction_method`, `extraction_provider`, `extraction_confidence`,
  `page_number`, `section_heading`, `table_id`, `region`, `quote_offsets`,
  `source_snapshot_id`, `screenshot.captured`, `snapshot.storage_key`, and
  `source_quality.explanation`.
- [x] Update Evidence source metadata rendering in
  `apps/web/src/features/projects/evidence-tab.tsx` so extraction method,
  provider, confidence, `pdf_page_lineage`, `text_lineage.sections`,
  `table_extraction`, `raw_html_snapshot.screenshot`, snapshot
  storage/retention, and `source_quality` are collapsed but visible.
- [x] Add collapsed retrieval-result provenance in Evidence retrieval results:
  chunk provenance, source quality, rerank reason, `context_included`,
  page/section/table/region, quote offsets, and snapshot availability.
- [x] Enrich citation DTOs and guide citation details in
  `apps/api/app/schemas/artifacts.py`, `apps/api/app/schemas/guide.py`,
  `apps/api/app/services/guide_service.py`, and `apps/web/src/lib/api.ts` with
  optional source type, metadata/provenance, source quality, extraction,
  snapshot, locator fields, quote offsets, and warning labels.
- [x] Update guide and research memo citation renderers so provenance appears
  only inside existing collapsed citation/source controls.
- [x] Preserve rich provenance through citation verification and fallback
  citation creation for agentic research, opportunity brief, and competitor
  artifacts.
- [x] Extend source-discovery review provenance behind the existing
  "Show search provenance" disclosure with provider score/rank, search
  provenance, snapshot fallback status, and extraction warnings.
- [x] Update `eval_service.run_context_eval` so Inspect diagnostics retain
  `provenance.metadata` instead of reducing provenance to `source`.
- [x] Make live-provider QA opt-in and visibly skipped when credentials,
  provider mode, or egress allowlists are missing. The extraction eval reports
  missing Tavily and deterministic multimodal mode as warnings rather than
  silent passes.
- [x] Extend `scripts/eval_extraction_quality.py` from structural readiness
  checks into fixture-backed behavior checks that execute service paths and
  report fixture IDs, expected/actual values, warnings, and rerun commands.
- [x] Add fixture coverage for messy HTML, prompt-injected HTML, OCR fallback,
  low-text PDFs, table-heavy documents, quote provenance, source-quality
  scoring, and live-provider-unavailable fallback.
- [x] Store raw snapshot metadata and normalized extraction artifacts separately
  enough that citations can explain whether a quote came from raw HTML,
  normalized HTML text, OCR, a table, or a PDF page.
- [x] Update README/status/changelog portfolio language for the implemented
  document-AI stack: extraction methods, provenance model, source-quality
  scoring, deterministic fallbacks, and live-provider limits.
- [x] Run backend evidence, extraction, provenance, retrieval, citation, and
  source-quality checks:
  `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py -q --maxfail=1`
  (`17 passed`) and `python3 scripts/eval_extraction_quality.py --json`
  (`7/7` with explicit provider-unavailable warnings).
- [x] Run the broader backend regression suite:
  `cd apps/api && .venv/bin/pytest -q` (`174 passed`).
- [ ] Add or intentionally defer a maintained HTML readability dependency
  (`trafilatura`, `readability-lxml`, or equivalent). Current branch uses an
  improved deterministic `html.parser` fallback with parser/version/confidence
  metadata; Sprint 60 must document that as the V1 local fallback or add the
  dependency before final sign-off.
- [ ] Add true page/screenshot artifact capture and object-storage persistence
  if this moves beyond metadata-only local mode. Current branch records
  `screenshot.captured: false`, `storage_key: null`, and an explicit
  local-mode absence reason; Sprint 60 must keep this honest in README/status
  or create a follow-up backlog item for Playwright/screenshot storage.
- [ ] Add screenshot-region OCR/table provenance only if screenshot capture is
  implemented. Current positive table extraction covers text/PDF-like content,
  not screenshot table regions; Sprint 60 must mark screenshot-region table
  extraction out of V1 or assign a future backlog owner.
- [ ] Retry web typecheck/tests and IDE browser QA for the Sprint 58 UI changes
  once npm registry access is stable:
  `pnpm --filter thesys-web typecheck`,
  `pnpm --filter thesys-web test`, and browser checks for Evidence source
  metadata, retrieval-result provenance, Ask Thesys citation drilldowns,
  research memo citations, source-discovery provenance, and no homepage/main
  workflow clutter. The latest typecheck retry again stopped before TypeScript
  because pnpm hit npm registry `ECONNRESET` package fetch failures and was
  interrupted during `pnpm install`.
- [ ] Run opt-in live Tavily and live multimodal QA with real credentials,
  provider mode enabled, egress allowlists configured, and rate limits active.
  If credentials or egress are unavailable, record the eval warning and exact
  rerun command in Sprint 60 rather than claiming live-provider coverage.
- [ ] Verify Project Inspect trust summaries in the browser after web deps are
  available. Backend context eval items now retain provenance metadata, but the
  hidden UI must still be checked for source-quality/extraction indicators and
  no primary-workflow clutter.
- [x] Update this TODO and `IMPLEMENTATION_STATUS.md` with exact verification
  results and remaining unchecked carry-forward items.
- [x] Commit Sprint 58.

Residual handoff that still belongs in the TODO:

- [ ] `S60-P8/G48-A`: decide and record whether to add
  `trafilatura`/`readability-lxml` or keep deterministic `html.parser` as the
  V1 fallback. Update `docs/SOURCE_INTELLIGENCE.md`, README, and
  `IMPLEMENTATION_STATUS.md` with parser/version/confidence metadata and
  productization tradeoffs.
- [ ] `S60-P8/G48-B`: either implement true page/screenshot artifact capture
  with storage keys, retention, and redaction, or create a named future backlog
  item and keep local-mode metadata-only limits explicit in README/status.
- [ ] `S60-P8/G48-C`: implement screenshot-region OCR/table provenance only if
  screenshot capture lands; otherwise mark it out of V1 with reason and future
  owner.
- [ ] `S60-P8/G48-D`: run opt-in Tavily and multimodal smoke tests with
  credentials, provider mode, rate limits, and egress allowlists, or record the
  exact unavailable warning and rerun command.
- [ ] `S60-P8/G48-E`: retry web typecheck/tests and IDE browser QA for Evidence
  Inspect, retrieval provenance, Ask Thesys citations, research memo citations,
  source-discovery provenance, Project Inspect trust summaries, provider
  warnings, and no homepage/main workflow clutter.

## Sprint 59: Feature-Package Backend Refactor

Completion scope: Sprint 59 is not complete while any `S59-P*` or `S59-R*`
row lacks either a tested code move or an explicit service-owned disposition in
`docs/BACKEND_FEATURE_PACKAGE_MAP.md` and `IMPLEMENTATION_STATUS.md`. The
authoritative closeout is `G49-A` through `G49-E`: characterization matrix,
feature package movement, DTO boundary ledger, duplication cleanup, and
migration/shim evidence.

Pickup rule: use the `Sprint 59 Pickup Queue`, `Sprint 59 Open Code Cleanup
Punch List`, `Sprint 59 Row Closure Checklist`, and `Sprint 59 Must-Not-Miss
Edge Cases` sections above as the authoritative gap-closure checklist. The
older broad checklist below is retained as implementation history; do not infer
gap closure from one of those broad boxes unless the matching `S59-P*`/`S59-R*`
row and `G49-*` disposition evidence is also updated.

- [ ] Close Sprint 49 gaps: complete the architecture cleanup by splitting
  oversized services, removing duplication, adding typed boundaries, and
  documenting feature ownership without changing public behavior. Required
  carried-gap IDs: `G49-A`, `G49-B`, `G49-C`, `G49-D`, and `G49-E`.
- [ ] Add characterization tests around each workflow before moving code:
  evidence ingestion/retrieval, guide chat, research sprint, opportunity brief,
  competitor analysis, validation plan/result interpretation, decision
  recommendation, memory management, MCP tools, and eval endpoints. Current
  progress: evidence response serialization, artifact/version structured JSON,
  feature-package shims, common metadata, extraction behavior, and read-tool
  output-schema keys are pinned. Remaining required tests before high-risk
  movement:
  - MCP parity and edge cases: JSON-RPC request ID preservation, structured
    error shape, stdio bridge command failure, approval-required proposal tool,
    denied write tool, missing/invalid project scope, redacted audit payload,
    and tool schema parity between HTTP and MCP surfaces.
  - Context profile coverage: every `ContextCompiler` profile has a focused
    test proving required item types, memory filters, token budgets,
    compression policy, stale/conflict handling, dropped-context explanations,
    and untrusted-content wrapping.
  - Validation and decision paths: validation plan approval,
    validation result interpretation, experiment-result parse failures, and
    remaining proposal/audit path shapes. Approval rejection and decision
    recommendation weak-evidence labels, route DTO fields, suggested action
    cards, linked evidence IDs, and no-direct-mutation behavior are already
    pinned.
  - Eval/report endpoints: missing report file, malformed JSON report,
    unreadable report file, malformed/unreadable/unwritable trend records, and
    hidden-report serializer shape.
    Live-provider-unavailable warning metric shaping, rerun metadata, and
    local metric export payload assembly are already pinned.
  - Structured-output dispatch: deterministic stub routing for each schema,
    repair prompt on invalid JSON, validation error propagation, and
    prompt/schema version recording.
  Current added Sprint 59 coverage now also pins context profile policy
  metadata, token budgets, dropped-context reasons, unknown untrusted input
  fallback, tool-output context items, MCP schema parity, JSON-RPC request ID
  preservation, invalid-params no-invocation behavior, MCP client ID aliases,
  MCP redaction, missing/malformed eval report handling, eval cache metric
  precedence, structured-output named-schema stub dispatch, repair exhaustion,
  nested camelCase normalization, provider timeout/fallback metadata,
  validation-plan context metadata, and validation interpretation rejection
  behavior, plus memory context-pack helper aliases, selected/excluded/conflict
  metadata, UUID string normalization, title truncation, and token-estimate
  behavior.
  The source-discovery slice now also pins candidate-spec service aliases,
  search result provenance metadata, source-type/risk inference, URL
  cleanup/dedupe, snapshot text, evidence metadata, and score clamping.
  The eval-observability slice now pins metric helper aliases,
  OpenTelemetry-compatible metric payload shape, workflow/model/retrieval
  latency helpers, timeout counts, cache metric coercion, provider-egress
  attributes, and cache-quality gate detection after metric ownership moved to
  `app.features.evals.observability_metrics`.
  The eval report-summary slice now also pins partial gate failure fallback:
  failed gates without failing metric rows surface their gate ID in
  `failed_check_ids`.
  The MCP protocol slice now pins adapter aliases, initialize negotiation,
  JSON-RPC tool schema annotations, client ID alias extraction, argument
  validation, result/error envelope helpers, MCP invocation metadata, and
  tool-call read serialization in `app.features.mcp.protocol`.
- [ ] Use the following pickup contract before the Sprint 59 commit so each
  `G49-*` gap closes with a concrete artifact instead of a broad cleanup claim:
  - `G49-A`: append or update a characterization matrix in
    `docs/BACKEND_FEATURE_PACKAGE_MAP.md` with one row per moved workflow slice,
    including service path, feature target, route/API shape pinned by tests,
    focused pytest command, and known unpinned edge cases. Add missing tests
    before moving any DB-writing orchestration helper.
  - `G49-B`: for every remaining oversized service, either move the named
    pure/domain helpers into `app.features.*` or mark the service-owned
    orchestration that intentionally stays in `app.services.*`. Required
    disposition targets are `evidence_service.py`, `retrieval_service.py`,
    `validation_service.py`, `agentic_research_service.py`, `guide_service.py`,
    `tool_service.py`, MCP adapters, `eval_service.py`, `eval_report_service.py`,
    `context_service.py`, and `memory_service.py`.
  - `G49-C`: maintain the DTO boundary ledger in
    `docs/BACKEND_FEATURE_PACKAGE_MAP.md`. It must list context pack,
    retrieval request/result, citation verification, guide event, tool
    outcome/proposal, eval gate/report, cache diagnostic, extraction artifact,
    memory selection, and decision recommendation payloads with old keys, new
    typed fields, conversion point, owning module, compatibility serializer,
    parity command, and the next DTO extraction step.
  - `G49-D`: remove duplication only where characterization tests already pin
    behavior. The required cleanup targets are prompt/schema repair dispatch,
    retrieval result shaping, citation/provenance metadata shaping, audit
    metadata merge/redaction, proposal/action-card creation, Markdown rendering,
    and deterministic fallback serialization.
  - `G49-E`: maintain the migration ledger in
    `docs/BACKEND_FEATURE_PACKAGE_MAP.md` before commit with old import path,
    new feature module, shim type, parity test, boundary-check result, whether
    the shim is temporary/permanent, and the follow-up needed to remove it.
- [ ] Finish Sprint 59 using these pickup-ready slices. Each slice must update
  `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, this TODO, and
  `IMPLEMENTATION_STATUS.md` with exact status before moving to the next slice:
  - `S59-1 Evidence/retrieval execution`: add tests for URL fetch failure,
    upload/PDF parsing, OCR/multimodal fallback, chunk persistence, embedding
    cache behavior, retrieval execution, cache lookup/invalidation, context
    assembly, and citation-enrichment shape. Then move only pure extraction,
    retrieval-execution, cache-key, and result-shaping helpers to
    `app.features.evidence` / `app.features.retrieval`; keep DB writes and
    transaction orchestration in services unless typed DTOs exist. Verify with
    `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py app/tests/test_feature_package_boundaries.py -q`
    and `python3 scripts/check_feature_boundaries.py`.
    Current progress: retrieval context selection helpers now live in
    `app.features.retrieval.context_selection`, with `retrieval_service.py`
    preserving aliases for existing callers:
    `assemble_context_results`, `_diversify_context_candidates`, `_mmr_order`,
    `_context_selection_reason`, `_quality_report`, `_ndcg_proxy`,
    `_combine_fallback_reasons`, `_result_domain`, `_result_competitor_id`, and
    `_estimate_tokens`. Retrieval DB execution, cache lookup/invalidation,
    citation enrichment, and route orchestration remain service-owned. Focused
    verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py::test_context_assembly_prioritizes_source_diversity app/tests/test_retrieval_quality_eval.py app/tests/test_feature_package_boundaries.py -q`.
    Retrieval result fusion now lives in
    `app.features.retrieval.result_shaping`, with `retrieval_service.py`
    preserving `_fuse_results` as a private compatibility alias. The feature
    helper dedupes duplicate subquery hits by `chunk_id`, keeps the
    highest-scoring result, adds `retrieval_match_count`, and preserves
    score/date ordering. Retrieval DB execution, cache lookup/invalidation,
    reranking, citation enrichment, and route orchestration remain
    service-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_result_fusion_dedupes_chunks_and_preserves_match_count app/tests/test_evidence.py::test_broad_evidence_retrieval_plans_reranks_and_assembles_context -q`.
	    Retrieval score math now lives in `app.features.retrieval.scoring`,
	    including semantic/keyword/hybrid weighting, keyword-overlap scoring, and
	    normalized BM25-like text scoring. `retrieval_service.py` keeps
	    `_combined_score` and `_bm25_keyword_scores` wrappers because they adapt
	    settings and ORM-backed candidate shapes; `_keyword_score` is a private
	    alias. Candidate loading, embedding similarity, SQL/vector execution, cache
	    lookup/invalidation, result serialization, citation enrichment, and route
	    orchestration remain service-owned. Focused verification:
	    `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_scoring_helpers_preserve_hybrid_keyword_and_bm25_behavior app/tests/test_evidence.py::test_note_ingestion_chunks_embeds_and_retrieves -q`.
	    Retrieval diagnostic DTO shaping now lives in
	    `app.features.retrieval.diagnostics`, including base diagnostics and
	    multi-query pipeline diagnostics for candidate-count aggregation,
	    SQL/fallback aggregation, query plan, reranker, context, quality-report,
	    and cache fields. `retrieval_service.py` preserves `_diagnostics` and
	    `_pipeline_diagnostics` aliases while timing, cache lookup/write, DB query
	    paths, result serialization, and route orchestration remain service-owned.
	    Focused verification:
	    `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_diagnostic_helpers_are_feature_owned_and_service_compatible app/tests/test_evidence.py::test_broad_evidence_retrieval_plans_reranks_and_assembles_context app/tests/test_retrieval_quality_eval.py -q`.
	    Citation de-duplication and retrieved-ID checks now live in
    `app.features.evidence.citation_verifier` as `dedupe_citations` and
    `citation_has_retrieved_id`. Opportunity brief, competitor analysis, and
    agentic research keep private `_dedupe_citations` and `_citation_is_valid`
    aliases while artifact-specific audit decisions, AI run steps, DB writes,
    and citation persistence remain service-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_citation_dedupe_helpers_are_feature_owned_and_service_compatible app/tests/test_citation_verifier.py app/tests/test_opportunity_brief.py app/tests/test_competitors.py app/tests/test_agentic_research.py -q`.
  - `S59-2 Validation/decision orchestration`: add tests for validation plan
    approval, result interpretation parse failures, and remaining proposal/audit
    metadata. Approval rejection, route contract parity, weak-evidence decision
    recommendation labels, and no-direct-mutation route behavior are implemented.
    Then move pure parse/proposal/decision helpers to
    `app.features.validation` / `app.features.decisions`; leave DB writes,
    approval persistence, and project overview refresh service-owned unless
    typed DTOs are added. Verify with
    `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_project_overview.py app/tests/test_feature_package_boundaries.py -q`.
    Current progress: validation interpretation fallback helpers now live in
    `app.features.validation.result_interpretation`, with
    `validation_service.py` preserving private aliases:
    `_fallback_validation_interpretation`, `_result_delta`, `_extract_quotes`,
    `_extract_objections`, `_fallback_current_workaround`, and
    `_assumption_status_for_outcome`. Approval persistence, memory writes, DB
    access, and route orchestration remain service-owned. Validation
    assumption-extraction and validation-plan prompt/fallback helpers now live
    in `app.features.validation.generation`, with `validation_service.py`
    preserving wrappers for `_assumption_messages`, `_validation_plan_messages`,
    `_fallback_assumption_extraction`, `_fallback_validation_plan`, and
    `_fallback_validation_plan_item`. LLM calls, AI run accounting,
    structured-output repair, approval persistence, DB writes,
    artifact/mission creation, and route orchestration remain service-owned.
    Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_validation.py::test_interpret_validation_notes_creates_pending_memory_update app/tests/test_validation.py::test_validation_interpretation_rejection_does_not_write_memory_or_confidence app/tests/test_validation.py::test_decision_coach_uses_interpreted_results_and_prefills_record app/tests/test_feature_package_boundaries.py -q`.
  - `S59-3 Research orchestration`: add tests for LangGraph state transitions,
    governed tool adapter payloads, fallback synthesis, citation audit
    outcomes, memory proposal shape, sprint status changes, and Temporal
    adapter boundaries. Then move graph/synthesis/audit/proposal helpers to
    `app.features.research`; keep Temporal activities and DB transaction
    orchestration service-owned unless the package exposes typed entrypoints.
    Verify with
    `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_research_sprints.py app/tests/test_research_discovery.py app/tests/test_temporal_research_orchestration.py app/tests/test_feature_package_boundaries.py -q`.
  - `S59-4 Guide orchestration`: add tests for context adapter output,
    grounded fallback answer, proposal creation, approval lookup behavior,
    citation verification orchestration, run accounting, streaming/non-streaming
    final parity, and guide eval fixture shape. Then move pure grounded-answer,
    proposal-routing, and fixture helpers to `app.features.guide`; keep DB run
    writes and approval creation service-owned unless typed DTOs exist. Verify
    with
    `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`.
  - `S59-5 Governance tools/MCP orchestration`: add tests for stdio bridge
    command failure, approval-required proposal tools, denied write tools,
    invalid/missing project scope, redacted audit payloads, tool schema parity,
    and JSON-RPC error/result shape. Stdio bridge command failure is now pinned
    by `test_mcp_stdio_bridge_returns_jsonrpc_error_on_http_failure`: the bridge
    forwards `--dev-role`, preserves the JSON-RPC request ID, skips blank stdin
    lines, and returns a structured `-32000` error when HTTP forwarding fails.
    Then move pure execution dispatch,
    proposal shaping, audit metadata shaping, transport serialization, and
    redaction helpers to `app.features.governance_tools` / `app.features.mcp`;
    keep auth, DB approvals, and audit writes service/adapter-owned unless
    typed DTOs exist. Verify with
    `cd apps/api && .venv/bin/pytest app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py app/tests/test_security_governance.py app/tests/test_feature_package_boundaries.py -q`.
    Current progress: governed tool registry contracts now live in
    `app.features.governance_tools.registry`, with `tool_service.py`
    preserving public/private aliases: tool
    literal types, `ToolDefinition`, role constants, `TOOL_REGISTRY`,
    `list_tool_definitions`, `_definition`, `_approval_request_type_for_tool`,
    and `_summarize_output`. Keep execution, authorization, approval writes,
    and audit writes in `tool_service.py`. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_tool_boundary.py::test_tool_registry_exposes_mcp_style_contracts app/tests/test_tool_boundary.py::test_read_tools_return_declared_output_schema_keys app/tests/test_mcp_adapter.py::test_mcp_jsonrpc_preserves_ids_and_tool_schema_parity app/tests/test_feature_package_boundaries.py -q`.
    Governed tool audit/proposal payload shaping now lives in
    `app.features.governance_tools.audit`, with `tool_service.py` preserving
    private aliases for requested/executed/status/denial audit metadata,
    approval summaries, and approval proposed-change payloads. Audit
    persistence, redaction calls, authorization, approval writes/lookups, and
    DB transaction orchestration remain service-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_governance_tool_audit_helpers_are_feature_owned_and_service_compatible app/tests/test_security_governance.py::test_tool_denial_is_audited_and_persisted_proposals_are_redacted app/tests/test_tool_boundary.py::test_research_plan_proposal_is_audited_and_approvable -q`.
    MCP metadata payload shaping now lives in `app.features.mcp.protocol`,
    including input payload wrapping, MCP audit metadata, and MCP audit summary
    helpers. `app.mcp.adapter._attach_mcp_metadata` still owns redaction, audit
    persistence, commit, refresh, and transport orchestration. Focused
    verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_mcp_protocol_helpers_are_feature_owned_and_adapter_compatible app/tests/test_mcp_adapter.py::test_mcp_jsonrpc_client_id_alias_and_redaction_are_preserved app/tests/test_mcp_adapter.py::test_mcp_read_tool_uses_existing_governance_and_audit -q`.
    Stdio bridge HTTP failure behavior is now characterized in
    `test_mcp_stdio_bridge_returns_jsonrpc_error_on_http_failure`.
    MCP approval/proposal parity is now characterized in
    `test_mcp_jsonrpc_proposal_matches_http_approval_and_audit_contracts`:
    direct MCP HTTP and JSON-RPC proposal calls expose the same
    structured-content keys, MCP-originated proposal tools appear through HTTP
    tool-invocation and approval-list routes, rejection resolves the invocation
    and approval request, denial audit metadata is written, and proposal
    `output_summary` text is redacted before persistence. Live stdio
    read/proposal smoke remains `S60-P4/G44-C` because it needs a live API
    project and running server.
  - `S59-6 Eval/report orchestration`: add or keep tests for hidden-report
    serializer shape and quality-gate cache metrics. Partial gate failure
    fallback is now pinned: failed gates with no failing metric rows surface the
    gate ID in `failed_check_ids`. Missing, malformed, and unreadable report/
    trend-read payloads plus trend-write warning payloads,
    live-provider-unavailable warning metric shaping, rerun metadata, and local
    metric export payload assembly are already pinned by focused tests. Move
    only remaining typed gate/report/
    trend/export DTO boundaries to `app.features.evals`; keep scripts as thin
    CLIs. Verify with
    `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_research_history_eval.py app/tests/test_demo_eval_workflows.py app/tests/test_feature_package_boundaries.py -q`
    and `python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
    when provider credentials are unavailable.
    Current progress: eval gate/diagnostic helpers now live in
    `app.features.evals.gate_checks`, with `eval_service.py` preserving
    private aliases: `_Check`,
    `_ResearchMetric`, and retrieval diagnostic/section-check helpers through
    `_quality_report_observed`. `_secret_redaction_check` remains service-owned
    unless sanitizer ownership moves in the same slice. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_demo_eval_workflows.py::test_seed_demo_project_runs_mvp_eval_and_exposes_workflow_events app/tests/test_research_history_eval.py::test_v1_research_eval_passes_for_completed_research_sprint app/tests/test_feature_package_boundaries.py -q`.
    Eval report writer/rendering helpers now live in
    `app.features.evals.report_writer`, with `scripts/eval_quality_gate.py`
    preserving wrappers for `_write_reports`, `_trend_record`,
    `_render_text_summary`, `_render_markdown`, `_render_html`,
    `_display_path`, and `_escape`. CLI argument parsing, subprocess gate
    execution, live API fetches, and LangSmith export side effects remain
    script-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_writer_creates_reports_latest_aliases_and_trend app/tests/test_eval_reports.py::test_eval_quality_gate_script_writes_reports -q`.
    Eval summary shaping helpers now live in
    `app.features.evals.report_summary`, with `scripts/eval_quality_gate.py`
    preserving wrappers for `_summary`, `_cache_from_live_snapshot`, and
    `as_dict`. Subprocess gate execution, live API fetching, CLI arguments,
    and LangSmith export side effects remain script-owned. Focused
    verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_summary_shapes_status_failures_and_live_cache app/tests/test_feature_package_boundaries.py::test_eval_report_summary_helpers_are_feature_owned app/tests/test_eval_reports.py::test_eval_quality_gate_script_writes_reports -q`.
    Eval gate result parsing/shaping now lives in
    `app.features.evals.gate_results`, with `scripts/eval_quality_gate.py`
    preserving `_parse_json_output`, `_run_json_gate`, `_run_command_gate`, and
    `_warning_gate` as private aliases/wrappers. JSON stdout parsing,
    JSON-command gate DTOs, plain command gate DTOs, unavailable/skipped gate
    DTOs, stdout/stderr tail projection, metrics passthrough, and rerun metadata
    are feature-owned; CLI arguments, subprocess gate execution, live API
    fetches, report writing, and LangSmith export side effects remain
    script-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_gate_result_helpers_parse_and_shape_command_results app/tests/test_feature_package_boundaries.py::test_eval_gate_result_helpers_are_feature_owned -q`; `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-gate-results LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`.
    Eval LangSmith export payload shaping now lives in
    `app.features.evals.langsmith_export`, with `scripts/eval_quality_gate.py`
    preserving `_redact` as a private alias and `_export_langsmith` as the
    side-effect wrapper. Redacted payload projection, export filename/path
    derivation, status result DTOs, and run input projection are feature-owned;
    local JSON file writes, `LANGSMITH_*` env lookup, dynamic client import,
    external upload, and best-effort exception handling remain script-owned.
    Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_langsmith_export_helpers_redact_payload_and_shape_status app/tests/test_eval_reports.py::test_eval_quality_gate_script_exports_langsmith_payload_without_upload app/tests/test_feature_package_boundaries.py::test_eval_langsmith_export_helpers_are_feature_owned_and_script_compatible -q`;
    `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-langsmith LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security --export-langsmith`.
    Shared eval metric-record construction now lives in
    `app.features.evals.metric_records`, with `scripts/eval_ai_quality.py`,
    `scripts/eval_extraction_quality.py`, `scripts/eval_mcp_contract.py`, and
    `scripts/eval_research_sprints.py` preserving private `_metric` aliases.
    Metric key/label/passed/observed/expected fields and optional warnings are
    feature-owned; static repo checks, live API fetches, extraction fixture
    setup, provider settings, process re-exec, required live API/project setup,
    and report printing remain script-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_metric_record_helper_shapes_optional_warnings app/tests/test_feature_package_boundaries.py::test_eval_metric_record_helper_is_feature_owned_and_script_compatible -q`;
    `python3 scripts/eval_ai_quality.py --json`;
    `python3 scripts/eval_extraction_quality.py --json`;
    `python3 scripts/eval_research_sprints.py --json`; and
    `python3 scripts/eval_mcp_contract.py --help`. Full MCP contract execution
    still requires a live API and project ID.
    Research eval case loading and dataset scoring now live in
    `app.features.evals.research_cases`, with `eval_service._research_eval_cases`
    and `scripts/eval_research_sprints.py` preserving compatibility wrappers
    and aliases. Dataset path resolution, raw JSON loading, Pydantic schema
    validation, required-category/field constants, and dataset coverage metrics
    are feature-owned; live project metric fetches and API route orchestration
    remain script/service-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_research_eval_case_helpers_are_feature_owned_and_script_compatible -q`;
    `python3 scripts/eval_research_sprints.py --json`; and service import
    smoke for `eval_service._research_eval_cases()`.
    Eval report failure payload shaping now lives in
    `app.features.evals.report_failures`; missing-report, malformed-report,
    unreadable-report, malformed-trend-record, unreadable-trend-file, and
    unwritable-trend-file payloads are feature-owned, while `report_files.py`
    keeps file IO and path traversal. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_endpoints_surface_missing_and_malformed_reports app/tests/test_eval_reports.py::test_eval_report_failure_helpers_shape_safe_warning_payloads app/tests/test_feature_package_boundaries.py::test_eval_report_failure_helpers_are_feature_owned -q`.
    Live-provider-unavailable warning messages and metric shaping now live in
    `app.features.evals.provider_warnings`; `scripts/eval_extraction_quality.py`
    keeps settings/env lookup and preserves a compatibility alias for the
    warning-message helper. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_provider_warning_helper_shapes_live_provider_metric app/tests/test_feature_package_boundaries.py::test_eval_metric_record_helper_is_feature_owned_and_script_compatible -q`.
  - `S59-7 Context/memory orchestration`: add tests for every
    `ContextCompiler` profile, memory filters, token budgets, compression
    policy, stale/conflict handling, proposal review, compaction policy,
    dropped-context explanations, untrusted-content wrapping, and Inspect
    serializer shape. Then move pure selection, compaction/conflict policy, and
    metadata-shaping helpers to `app.features.memory`; keep DB-backed memory
    writes and approvals service-owned unless typed DTOs exist. Verify with
    `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_feature_package_boundaries.py -q`.
    Current progress: memory selection/conflict policy helpers now live in
    `app.features.memory.selection_policy`, with `memory_service.py`
    preserving aliases for `MemorySelection`, `_memory_exclusion_reason`,
    `_excluded`, `_conflict_key`, and `_normalize_text`. The feature module
    raises `MemoryConflictMembershipError` for conflict-membership mismatches,
    and the service wrapper keeps the existing HTTP 409 behavior for
    `_ensure_conflict_member`. DB reads/writes, approvals, compaction,
    conflict-resolution orchestration, and Inspect route orchestration remain
    service-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py::test_memory_context_selection_explains_exclusions_and_conflicts app/tests/test_memory_service.py::test_memory_proposals_and_inspect_endpoint app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`.
    Memory Inspect serialization and explanation helpers now live in
    `app.features.memory.inspection`, with `memory_service.py` preserving the
    public `serialize_memory_item` alias. DB lookup, workflow memory selection,
    proposed-memory queries, approvals, compaction, conflict resolution, and
    route orchestration remain service-owned. Focused verification:
    `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_memory_inspection_helpers_are_feature_owned_and_service_compatible app/tests/test_memory_service.py::test_memory_explanation_and_duplicate_merge app/tests/test_memory_service.py::test_memory_proposals_and_inspect_endpoint -q`.
  - `S59-8 Shared common cleanup`: only after the slice-specific tests pass,
    centralize duplicated prompt/schema repair, deterministic fallback
    serialization, audit metadata merge/redaction, proposal/action-card
    creation, citation/provenance shaping, and Markdown rendering. Put shared
    code under `app.common` only when two or more features use it; otherwise
    keep it feature-owned. Verify with focused tests for the touched features,
    `cd apps/api && .venv/bin/pytest app/tests/test_ai.py app/tests/test_contract_shapes.py -q`,
    `python3 scripts/check_feature_boundaries.py`, `cd apps/api && .venv/bin/pytest -q`,
    `git diff --check`, and `rg -n "<{7}|={7}|>{7}" .`.
    Current progress: deterministic fallback `LLMCompletion` construction now
    lives in `app.ai.fallback_completion`, with service-private
    `_fallback_completion` wrappers preserving workflow-specific fallback names,
    local-fallback versus deterministic-stub provider naming, fallback
    key/reason metadata, provider-mode metadata, token/cost accounting, redacted
    error truncation, timeout/cause classification, and optional trace/run
    metadata redaction. Structured-output schema instruction assembly now lives
    in `app.ai.structured_output.schema_instruction_message`;
    `generate_structured_output` and Ask Thesys streaming share the same
    JSON-schema system prompt, while private compatibility aliases preserve
    existing call sites. Tool audit metadata and approval proposed-change
    shaping are centralized in `app.features.governance_tools.audit`; audit
    persistence and redaction still intentionally stay at service/governance
    boundaries. Retrieval result fusion is feature-owned in
    `app.features.retrieval.result_shaping` and stays behind the
    `retrieval_service._fuse_results` compatibility alias. Retrieval score math
    is feature-owned in `app.features.retrieval.scoring`, with service wrappers
    only for settings and ORM candidate adaptation. Citation de-duplication and
    retrieved-ID checks across opportunity brief, competitor analysis, and
    agentic research are now centralized in
    `app.features.evidence.citation_verifier` behind private service aliases.
    Repair dispatch, proposal/action-card creation, broader
    citation/provenance shaping, and Markdown rendering remain separate pickup
    candidates that must be covered by characterization tests before
    deduplication.
- [x] Create a target package map before moving files. Expected direction:
  feature packages for `evidence`, `retrieval`, `research`, `guide`,
  `validation`, `decisions`, `memory`, `governance/tools`, `mcp`, and `evals`;
  shared packages only for `common/ai`, `common/db`, `common/security`,
  `common/observability`, and `common/types`.
- [x] Record the package map in a temporary migration note or architecture doc
  before code movement. For each package, list owned routers, service
  entrypoints, DTOs, models touched, tests, and allowed dependencies.
- [ ] Start with the largest mixed-responsibility modules only after their
  characterization tests exist. Work in this order so each slice can be picked
  up independently:
  - `evidence_service.py` / `retrieval_service.py`: finish moving URL fetch,
    upload/PDF parsing, multimodal/OCR adapters, chunk persistence, embedding,
    retrieval planning/execution, source-quality scoring, and citation
    enrichment into `app.features.evidence` and `app.features.retrieval`.
  - `validation_service.py`: split validation plan generation, validation
    result interpretation, experiment-result parsing, approval/proposal path
    creation, and shared validation DTOs into `app.features.validation`.
  - `agentic_research_service.py`: split LangGraph graph construction, state
    transitions, governed tool adapters, retrieval orchestration, synthesis,
    citation audit, memory proposal generation, and Temporal-facing adapters
    into `app.features.research`.
  - `guide_service.py`: split intent routing, context compiler adapter,
    grounded answer generation, streaming event protocol, proposal routing,
    citation drilldown shaping, and guide eval fixtures into
    `app.features.guide`.
  - `tool_service.py` and MCP adapters: split tool definitions, permission and
    risk guards, execution dispatch, proposal application, MCP schema
    generation, transport adapters, audit events, and redaction helpers into
    `app.features.governance_tools` and `app.features.mcp`.
  - `eval_service.py` / `eval_report_service.py`: finish splitting gate
    execution, report serialization, typed eval DTOs, and optional LangSmith
    upload boundaries into `app.features.evals`. Research eval case loading/
    scoring, trend failure payloads, local metric export payloads,
    unavailable-provider warning metrics, and LangSmith export payloads are
    already feature-owned.
  - `context_service.py` / `memory_service.py`: split context-pack
    serialization, memory selection payload shaping, selected/excluded/conflict
    normalization, memory proposal/review helpers, compaction policy helpers,
    conflict-resolution helpers, and context metadata shaping into
    `app.features.memory`; keep DB writes and approval orchestration in
    services until the DTO boundaries and tests are pinned.
  - Related routers: keep route modules thin by calling package entrypoints;
    route serializers must stay schema-compatible with existing API responses.
- [ ] Define dependency rules: feature packages may depend on common packages;
  routers call feature service entrypoints; feature packages must not import
  each other through hidden module-level side effects; cross-feature behavior
  uses explicit DTOs or orchestration services.
- [x] Add or document an import-boundary check for the new package layout. At a
  minimum, run a static import scan that proves feature packages do not create
  circular imports or depend on private modules from sibling features.
- [ ] Split validation planning, validation result interpretation, decision
  recommendations, experiment result parsing, and shared validation DTOs into
  cohesive modules.
  Current progress: validation mission asset/step builders and validation plan/
  experiment markdown renderers now live in
  `app.features.validation.plan_rendering`; deterministic decision
  recommendation shaping now lives in `app.features.decisions.recommendation`,
  including context/untrusted-input serialization, recommendation value
  selection, supporting/missing-evidence/risk derivation, suggested decision
  record shaping, action cards, labels, markdown, and link dedupe. The service
  preserves private aliases. Validation interpretation fallback helpers also
  now live in `app.features.validation.result_interpretation`. Assumption and
  validation-plan prompt construction plus deterministic fallback draft shaping
  now live in `app.features.validation.generation`. Provider calls,
  structured-output repair, AI run accounting, DB writes, approvals,
  experiment-result parsing, DB-backed decision loading/persistence, context
  compilation, artifact/mission creation, and decision recommendation route
  orchestration remain service-owned for later slices.
- [ ] Split agentic research graph construction, state transitions, tool
  adapters, retrieval orchestration, synthesis, citation audit, memory proposal
  generation, and Temporal-facing adapters.
  Current progress: research memo markdown rendering and selected-evidence
  bundle serialization now live in `app.features.research.memo_rendering`, with
  `agentic_research_service.py` preserving private aliases/wrappers; source
  discovery candidate shaping, external-search result normalization into
  candidate specs, deterministic fallback candidate specs, source type/risk
  inference, URL cleanup/deduplication, discovery snapshot text, and
  evidence-ingestion metadata now live in
  `app.features.research.source_discovery`, with
  `source_discovery_service.py` preserving private aliases. LangGraph
  orchestration, source-discovery LLM calls, external-search provider calls, DB
  writes, sprint status changes, citation audit, fallback memo synthesis,
  memory proposals, evidence ingestion orchestration, and Temporal adapters
  remain service-owned for later slices.
	- [ ] Split guide intent routing, context compilation adapter, grounded answer
	  generation, streaming/event protocol, proposal routing, citation drilldowns,
	  and guide eval fixtures.
  Current progress: Ask Thesys retrieval event serialization, answer delta
  chunking, final stream metadata shaping, and partial JSON answer parsing now
  live in `app.features.guide.events`; citation drilldown shaping now lives in
  `app.features.guide.citations`, including context item IDs, selected memory
  IDs, provenance/extraction/snapshot fields, locator fields, quote offsets, and
  warning labels; deterministic intent/action routing now lives in
  `app.features.guide.routing`, including in-scope checks, proposal-tool
  selection, proposal payload/action shaping, canonical action aliases,
  support-action ordering, related entity shaping, grounded-confidence fallback,
  simple chat responses, and out-of-scope responses. `guide_service.py`
  preserves private aliases. Context compilation, grounded answer generation,
  DB-backed proposal creation, approval lookup, citation verification
  orchestration, DB/run orchestration, and guide eval fixture ownership remain
  service-owned for later slices. Guide action-card DTO shaping now lives in
  `app.features.guide.actions`, including available action dedupe, next-best
  action labels/descriptions, decision-coach action cards, support action
  cards, target modals, action types, and risk labels. `guide_service.py`
  preserves private aliases. Nudge-specific action-card route, modal, risk, and
	  `project_nudge` payload shaping now also use `app.features.guide.actions`
	  through a `nudge_service.py` private alias; nudge candidate selection,
	  persistence, dismissal, and serialization remain service-owned.
	  Grounded answer draft/response DTO shaping now lives in
	  `app.features.guide.grounding`, including `_GroundedGuideAnswerDraft`,
	  prompt evidence-context projection, cited-source filtering to retrieved
	  evidence, suggested-action resolution, unsupported-claim fallback, assumption
	  ID truncation, related entity projection, and retrieval diagnostic passthrough.
	  `guide_service.py` preserves private aliases. Retrieval execution,
	  context-pack assembly, provider calls, cache lookup/write, citation detail
	  enrichment, AI run writes, approvals, cancellation, and route orchestration
	  remain service-owned.
	  Guide eval read-model shaping now lives in `app.features.guide.evals`,
	  including stable metric keys, score/total/pass derivation, proposal/direct
	  write observed text, and direct-write failure shape. `eval_service.py`
	  remains responsible for project authorization, DB counts, eval route
	  orchestration, and any future fixture loading.
  Focused verification:
  `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_action_helpers_are_feature_owned_and_service_compatible app/tests/test_guide.py app/tests/test_nudges.py -q`.
  Stage-aware guide recommendation copy now lives in
  `app.features.guide.recommendations`, including `_StageGuideCopy`/
  `_STAGE_GUIDE_COPY` compatibility, suggested questions, fallback stage copy,
  after-that follow-up text, and readable list joining. Overview loading,
  active validation/research lookups, chat/proposal/retrieval orchestration,
  provider calls, AI run writes, approvals, and route orchestration remain
  service-owned. Focused verification:
  `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_recommendation_helpers_are_feature_owned_and_service_compatible app/tests/test_guide.py::test_guide_context_and_recommendation_are_stage_aware app/tests/test_guide.py::test_guide_action_router_uses_specific_commands_and_aliases app/tests/test_guide.py::test_guide_chat_is_project_scoped_and_rejects_generic_questions app/tests/test_guide.py::test_guide_explains_idea_story_wedge_and_next_proof -q`.
- [ ] Split evidence ingestion, URL fetching, upload parsing, readability/OCR/
  table extraction, chunking, embedding, retrieval planning, retrieval
  execution, reranking, citation verification, and source-quality scoring.
  Current progress: source provenance, text/HTML extraction helpers, citation
  verification, retrieval query planning/tokenization, and retrieval reranking
  have moved into feature packages behind compatibility shims/private aliases.
  The feature reranker now owns source-quality retrieval weighting and freshness
  scoring behavior. Retrieval context selection, MMR ordering, diversity caps,
  fallback-reason aggregation, token estimates, and retrieval-quality proxies
  now live in `app.features.retrieval.context_selection`. Ingestion
  orchestration, URL/upload parsing, multimodal/OCR extraction, chunk
  persistence, embedding, retrieval DB execution, cache lookup/invalidation,
  and citation enrichment still need later slices.
- [ ] Split memory context-pack serialization, memory selection payload shaping,
  compaction/preference/conflict policy helpers, proposal review helpers, and
  memory DTOs into cohesive modules.
  Current progress: memory context-pack item serialization, selected/excluded/
  conflict list normalization, memory-policy metadata, and local token
  estimates now live in `app.features.memory.context_pack`;
  context-pack budget application, priority ordering, max-item and token-budget
  drop reasons, prompt pack metadata, safety rule metadata, and available
  citation ID projection now live in `app.features.context.packing`;
  compacted-memory proposal summary/content/provenance shaping now lives in
  `app.features.memory.compaction`, including default/custom titles, summary
  caps, empty-summary handling, source-memory IDs/titles, source-entity refs,
  and approval-required provenance;
  memory selection/conflict policy helpers now live in
  `app.features.memory.selection_policy`; memory Inspect serialization and
  explanation helpers now live in `app.features.memory.inspection`; approved/
  rejected memory proposal provenance and audit metadata shaping now live in
  `app.features.memory.review`;
  `context_service.py` and `memory_service.py` preserve compatibility aliases.
  Context compiler orchestration, settings/profile selection, workflow-specific
  tool/memory item assembly, memory DB policy, compaction source loading,
  `upsert_memory_item`, commit/refresh, conflict resolution, proposal review,
  approval writes, audit persistence, memory browser route orchestration, and
  Inspect DB loading remain service-owned for later slices. Guide/workflow evidence result
  context-item conversion now lives in `app.features.context.evidence_items`,
  including dict/object inputs, 900-character truncation, citation ID
  construction/omission, metadata projection, priority assignment, entity
  typing, and untrusted flags; guide/research context assembly, retrieval/tool
  orchestration, workflow metadata, and route/eval orchestration remain
  service-owned.
- [ ] Split tool definitions, permission/risk guards, execution, proposal
  application, MCP schema generation, audit events, and redaction helpers.
  Current progress: tool schema/input/output/proposal/metadata/requested-by/
  research-sprint-scope guards now live in
  `app.features.governance_tools.schema_guard`, with `tool_service.py`
  preserving private aliases and the `ToolGuardViolation` public symbol. Pure
  governed tool registry contracts also now live in
  `app.features.governance_tools.registry`, including tool literal types,
  `ToolDefinition`, role constants, `TOOL_REGISTRY`,
  `list_tool_definitions`, lookup, approval-request type mapping, and output
  summaries. Pure MCP protocol constants, initialize negotiation, JSON-RPC tool
  schema serialization, client ID and argument extraction, JSON-RPC result/
  error envelopes, MCP invocation metadata, and tool-call read serialization now
  live in `app.features.mcp.protocol`, with `app.mcp.adapter` preserving
  aliases.
  MCP proposal parity is pinned across direct MCP HTTP, JSON-RPC, HTTP
  tool-invocation routes, approval-list routes, approval rejection, and denial
  audit metadata. `tool_service.py` now redacts governed-tool output summaries
  before persistence so MCP-originated proposal summaries cannot leak raw
  emails or secrets through the tool invocation surface.
  Tool execution, RBAC, approval writes/lookups, audit writes, redaction writes,
  stdio/HTTP transport orchestration, and route-facing MCP orchestration remain
  service/adapter-owned for later slices. Stdio bridge command failure is
  characterized through `scripts/mcp_stdio_server.py`; live stdio smoke remains
  a Sprint 60 docs/QA item.
- [ ] Split eval gate execution, report generation, trend persistence, metric
  export, typed eval DTOs, and optional LangSmith export.
  Current progress: feature-owned `app.features.evals.report_files` now owns
  latest-report and trend-file reading, including missing/malformed report
  handling; feature-owned `app.features.evals.observability_metrics` now owns
  OpenTelemetry-compatible local metric payload assembly, workflow/model/
  retrieval latency helpers, timeout counters, approval wait calculations,
  cache metric coercion, audit-event denial counting, and UTC normalization.
  MVP/research gate constants, lightweight check/metric records, section
  coverage, retrieval diagnostics, reranker/context assembly observation, and
  quality-report observation now live in `app.features.evals.gate_checks`.
  `eval_report_service.py` preserves public wrappers/private aliases while
  authorization, DB queries, persisted-cache lookup, report-cache fallback
  selection, gate execution, report-shape assembly, trend persistence policy,
  and LangSmith upload side effects remain service/script-owned for later
  slices.
  Eval report file writing, latest aliases, trend-record projection, Markdown
  rendering, HTML rendering, terminal summary rendering, display paths, and
  HTML escaping now live in `app.features.evals.report_writer`, with the
  quality-gate script preserving private wrapper names. Aggregate summary
  status, failed/warning IDs, token/cost projection, trace IDs, and cache
  metric projection now live in `app.features.evals.report_summary`, with the
  quality-gate script preserving private wrapper names.
  JSON stdout parsing, JSON/plain command gate DTO shaping, warning-gate DTO
  shaping, stdout/stderr tail projection, and rerun metadata now live in
  `app.features.evals.gate_results`, with subprocess execution and cwd
  selection preserved in the quality-gate script.
  Research eval case loading and dataset scoring now live in
  `app.features.evals.research_cases`; dataset path resolution, raw JSON
  loading, Pydantic schema validation, required category/field constants, and
  dataset coverage metrics are feature-owned.
  Eval LangSmith export redaction/path/result/run-input shaping now lives in
  `app.features.evals.langsmith_export`, with `_redact` preserved as a private
  script alias and `_export_langsmith` preserving file-write/env/upload side
  effects. Missing/malformed/unreadable report payloads and
  malformed/unreadable/unwritable trend payloads now live in
  `app.features.evals.report_failures`. Live-provider-unavailable warning
  messages and metric shaping now live in `app.features.evals.provider_warnings`.
  Typed eval/report boundary validation now covers
  `EvalGateResultRead`, `EvalGateMetricRecord`, `EvalReportFailureRead`,
  `EvalExportResultRead`, `EvalMetricPointRead`, `EvalReportSummaryRead`,
  `EvalReportTokenCostRead`, and `EvalCacheDiagnosticRead`. Full gate
  execution, trend persistence policy, and upload side effects remain future
  cleanup.
  Shared metric-record construction now lives in
  `app.features.evals.metric_records`, with `_metric` aliases preserved in
  `scripts/eval_ai_quality.py`, `scripts/eval_extraction_quality.py`,
  `scripts/eval_mcp_contract.py`, and `scripts/eval_research_sprints.py`.
  Research eval case loading and dataset scoring now live in
  `app.features.evals.research_cases`, with service/script compatibility
  wrappers preserved. Remaining eval/report pickup is broader gate execution,
  trend policy, upload side-effect ownership, and any typed gate-check result
  expansion needed before moving gate execution.
- [ ] Move script-adjacent eval logic out of ad hoc script helpers where it is
  shared by API routes, local reports, or tests. Keep scripts as thin CLIs over
  package-owned services.
- [x] Move toward feature packages with shared common AI, retrieval, security,
  and DB code.
- [ ] Add typed internal DTOs for cross-module boundaries and remove large
  untyped dict payloads where they cross service/package boundaries.
- [ ] Define DTOs for context packs, retrieval requests/results, citation
  verification outcomes, guide events, tool execution/proposal outcomes, eval
  gate results, cache diagnostics, and extraction artifacts before replacing the
  existing dict payloads.
- [ ] For each DTO replacement, update the DTO boundary ledger in
  `docs/BACKEND_FEATURE_PACKAGE_MAP.md` with the old dict keys, new
  dataclass/Pydantic fields, conversion boundary, owner package, compatibility
  serializer, parity command, and next pickup step. Do not remove an old key
  until route/API contract tests prove the external shape is unchanged.
- [ ] Remove meaningful duplication in prompts, structured-output repair,
  retrieval shaping, audit metadata merging, and proposal creation.
- [ ] Centralize shared prompt/schema repair behavior in one AI common module
  and keep feature prompts in feature-owned prompt modules.
- [ ] Centralize audit metadata merging and redaction in governance/common code
  so tool, MCP, workflow, eval, and cache paths do not each hand-roll it.
- [x] Keep the shim/migration ledger in
  `docs/BACKEND_FEATURE_PACKAGE_MAP.md` current before the Sprint 59 commit.
  It must list every old service path or private alias that remains as a
  compatibility shim, its new feature-owned target, tests covering parity,
  boundary-check status, temporary/permanent status, and removal follow-up.
- [x] Keep migration/model ownership clear. If DB models remain centralized,
  document that choice; if model modules move, preserve Alembic imports and
  avoid circular model imports.
- [x] Keep public API behavior and persisted schemas unchanged for completed
  Sprint 59 slices by preserving compatibility service shims and unchanged
  response schemas.
- [x] Run import-cycle checks or an equivalent static inspection after the
  package move.
- [x] Run full backend tests, web checks, evals, and targeted browser smoke if
  imports affect UI behavior. Sprint 59 is backend/package-boundary work with
  no UI behavior change, so browser QA is not required for this commit; full
  backend tests, refactor checks, and quality gates are recorded above.
- [x] Update `SPRINT_51_60_TODO.md`, `IMPLEMENTATION_STATUS.md`, README project
  navigation, and code-owner docs with the final package layout before the
  Sprint 59 commit.
- [x] Commit Sprint 59.

## Sprint 60: Architecture Docs, Deployment, and Production Readiness

Completion scope: Sprint 60 is the final carried-gap closeout. It cannot be
marked complete until every `G41-*` through `G50-*` item appears exactly once in
the final disposition table with `implemented`, `intentionally out of V1`, or
`future owner` status; a source/doc link; verification output or exact blocker;
and no README/status claim that exceeds code, tests/evals, docs, and browser or
provider verification.

- [x] Close Sprint 50 gaps: add diagrams and post-refactor developer guidance
  that reflect implemented behavior after Sprints 51-59, not aspirational
  architecture. Sprint 60 also owns final documentation/verification closure
  for carried-gap IDs `G41-*` through `G48-*`, plus `G50-*`.
- [x] Create or update the specific Sprint 60 handoff artifacts below. Each
  artifact must include source-file references, commands/evals to verify the
  behavior, and an honest status for unavailable provider/browser checks:
  - `README.md`: interviewer-facing AI engineering tour, project navigation,
    feature-to-pattern-to-technology table, current limits, and where to inspect
    advanced details without changing the main workflow.
  - `IMPLEMENTATION_STATUS.md`: final `G41-*` through `G50-*` disposition
    table with `implemented`, `intentionally out of V1`, or `future owner` status and verification
    commands.
  - `docs/CONTEXT_ENGINEERING.md`: context profiles, token budgets, context
    source inventory, compression/stale/conflict policies, dropped-context
    examples, prompt-injection boundaries, Inspect QA, and eval commands.
  - `docs/MEMORY_SYSTEM.md`: memory types, capture/proposal/approval flow,
    compaction, preferences, conflicts, supersession/archive, context-pack
    linkage, extension steps, and browser QA notes.
  - `docs/MCP_INTEGRATION.md`: JSON-RPC lifecycle, stdio and HTTP/SSE commands,
    client config, governed tool behavior, structured errors, redaction/audit
    examples, and smoke commands.
  - `docs/RETRIEVAL_AND_CITATIONS.md`: retrieval pipeline, Postgres text-rank
    and BM25-like limits, MMR/source diversity, reranker/provider extension,
    cache invalidation, citation verification ownership, and eval commands.
  - `docs/EVALS_AND_OBSERVABILITY.md`: quality-gate matrix, pass/warn/fail
    policy, report/trend artifacts, OpenTelemetry/LangSmith setup, cache/cost
    metrics, unavailable gates, and CI usage.
  - `docs/SOURCE_INTELLIGENCE.md`: parser/fallback decision, snapshot and
    screenshot storage disposition, OCR/table provenance scope, live-provider
    QA commands, provider-unavailable warnings, and provenance browser QA.
  - `docs/DEPLOYMENT_SECURITY.md`: environment profiles, auth mode table,
    JWT/OIDC/JWKS expectations, API key/service-account lifecycle, egress
    policy, dependency audits, object storage, backup/restore, and hosted smoke
    commands.
  - `docs/BACKEND_FEATURE_PACKAGE_MAP.md`: final package map, characterization
    matrix, DTO boundary ledger, migration/shim ledger, intentionally
    centralized services, and future cleanup backlog.
- [x] Finish Sprint 60 using these pickup-ready documentation and verification
  packages. Use the `S60-P#` IDs below exactly as they appear in the pickup
  queue above. Each package must update `IMPLEMENTATION_STATUS.md` with
  `implemented`, `intentionally out of V1`, or `future owner` status, exact commands run, and exact
  blockers if unavailable:
  - `S60-P1 Gap disposition table`: create the final `G41-*` through `G50-*`
    disposition table in `IMPLEMENTATION_STATUS.md`. For every carried gap ID,
    record one of `implemented`, `intentionally out of V1`, or `future owner`;
    include verification command/output summary and the source doc/code file
    that proves the status. Do not mark Sprint 60 complete while any gap only
    appears as prose in README or a sprint title.
  - `S60-P2 Context engineering docs`: create/update
    `docs/CONTEXT_ENGINEERING.md` and README navigation. Include source-file
    links for `ContextCompiler`, context schemas, context profile definitions,
    retrieval/memory inputs, token budgets, compression/stale/conflict policy,
    dropped-item examples, untrusted-content wrapping, Inspect surfaces, and
    eval commands. Close `G42-A` through `G42-D`.
  - `S60-P3 Memory management docs`: create/update
    `docs/MEMORY_SYSTEM.md` and README navigation. Include memory type
    inventory, capture/proposal/approval lifecycle, compaction thresholds,
    preference edit/archive flow, conflict group resolution, supersession,
    archive behavior, audit records, context-pack linkage, "how to add a memory
    type" steps, and browser QA notes for filters/proposals/conflicts. Close
    `G43-A` through `G43-D`.
  - `S60-P4 MCP integration docs and smoke`: create/update
    `docs/MCP_INTEGRATION.md` and README navigation. Include initialize,
    capabilities, `tools/list`, `tools/call`, stdio command, HTTP/SSE command,
    client config, auth/project scoping, approval-required proposal example,
    denied write example, invalid params example, redacted audit example, and
    known limitations. Run or explicitly block read-tool and proposal-tool
    smoke commands. Close `G44-A` through `G44-D`.
  - `S60-P5 Retrieval/citation docs`: create/update
    `docs/RETRIEVAL_AND_CITATIONS.md`. Include the pipeline diagram, Postgres
    `ts_rank`/BM25-like limitation notes, vector fallback, hybrid scoring,
    MMR/source diversity policy, source-quality weighting, reranker provider
    interface, retrieval/rerank cache invalidation, citation verifier owner
    files, artifact coverage/non-applicable cases, and eval commands. Close
    `G45-A` through `G45-D`.
  - `S60-P6 Ask Thesys streaming docs and QA`: create/update guide docs/README
    sections for event names, payload IDs, cancellation, timeout fallback,
    final-payload parity, action cards, proposal events, citation drilldown
    fields, guide eval commands, and browser QA notes. Retry
    `pnpm --filter thesys-web typecheck`, `pnpm --filter thesys-web test`, and
    IDE browser checks for streamed deltas, retrieval/tool/proposal events,
    cancellation, timeout, final parity, action cards, citations, and no main
    workflow clutter. Close `G46-A` through `G46-D`.
  - `S60-P7 Evals/observability docs and QA`: create/update
    `docs/EVALS_AND_OBSERVABILITY.md`. Include aggregate and per-gate commands,
    pass/warn/fail policy, unavailable-gate behavior, report paths, trend JSONL
    paths, rerun failed slice commands, prompt/schema/context/retrieval/memory/
    tool changelog locations, OpenTelemetry metric names, LangSmith export
    settings, redaction behavior, cache/cost examples, CI usage, and hidden
    Inspect report browser QA. Close `G47-A` through `G47-D`.
  - `S60-P8 Source intelligence disposition and QA`: create/update
    `docs/SOURCE_INTELLIGENCE.md`. Decide and document or implement maintained
    parser dependency, page/screenshot artifact storage, screenshot-region
    OCR/table provenance, live Tavily/multimodal credential QA, Project Inspect
    trust-summary QA, provider-unavailable warnings, provenance fields, and
    browser checks for Evidence/retrieval/guide/research/source-discovery
    disclosures. Close `G48-A` through `G48-E`.
  - `S60-P9 Security/deployment docs and audits`: create/update
    `docs/DEPLOYMENT_SECURITY.md`. Include environment profiles, env vars,
    dev/demo/staging/production auth posture, JWT/OIDC/JWKS expectations,
    API-key/service-account lifecycle, token/key rotation, revocation, egress
    allowlists, SSRF/provider denial behavior, dependency audit commands,
    backup/restore boundaries for Postgres/pgvector/object storage/eval
    artifacts/traces/audit logs, and hosted-demo smoke commands. Run or record
    blockers for `python3 scripts/security_check.py`,
    `python3 scripts/audit_dependencies.py`, `pip-audit`, and
    `pnpm audit --prod`. Close `G41-A` through `G41-E` and the deployment-doc
    portion of `G50-D`.
  - `S60-P10 Post-refactor navigation and code docs`: update README and
    `docs/BACKEND_FEATURE_PACKAGE_MAP.md` after Sprint 59 lands. Add source
    links for feature packages, intentionally centralized services, DTO
    boundaries, compatibility shims, and "how to add" docs for workflows,
    context profiles, memory types, MCP tools, retrieval providers, rerankers,
    extractors, eval cases, and security policy checks. Add targeted docstrings
    or comments only around public entrypoints, DTOs, approval gates, Temporal
    determinism, security boundaries, prompt-injection handling, and non-obvious
    orchestration. Close `G49-*` final disposition and `G50-A` through `G50-E`.
- [x] Add architecture diagrams for context compilation, memory lifecycle, real
  MCP lifecycle, eval gates, and deployment/security posture.
- [x] Context diagram must show workflow profile selection, context item
  sources, memory selection, retrieval results, compression, dropped/stale/
  conflict diagnostics, prompt-injection boundaries, and which service files own
  those steps.
- [x] Memory diagram must show capture, proposed memory, approval/rejection,
  active memory, compaction, preference updates, conflict groups, supersession,
  archive, audit records, and context-pack links.
- [x] MCP diagram must show client initialize, capabilities, tool list, tool
  call, RBAC/risk guard, approval-request path, denial/error path, audit event,
  redaction, and stdio versus HTTP/SSE entrypoints.
- [x] Eval diagram must show local command, individual gates, unavailable-gate
  warnings, JSON/Markdown/HTML artifacts, trend persistence, optional LangSmith
  export, hidden Inspect UI, and CI usage.
- [x] Deployment/security diagram must show frontend, FastAPI API, Temporal,
  Postgres/pgvector, object storage, provider egress, auth modes, audit logs,
  eval artifacts, backup boundaries, and secret-redaction boundaries.
- [x] Update developer navigation after Sprint 59 refactor.
- [x] Add targeted docstrings and comments for public service entrypoints,
  DTOs, invariants, security boundaries, approval gates, Temporal determinism,
  and prompt-injection boundaries.
- [x] Update README project navigation so an interviewer or new developer can
  find: AI workflow entrypoints, context profiles, memory manager, retrieval
  pipeline, source ingestion/extraction, MCP tools, eval gates/reports,
  security/auth policy, observability, and frontend Inspect surfaces.
- [x] Add a short "AI engineering tour" for interview prep that maps features to
  patterns and technologies: LangGraph agentic research, LiteLLM gateway,
  Pydantic structured outputs, pgvector/Postgres retrieval, MCP JSON-RPC,
  ContextCompiler/MemoryManager, eval gates/reports, LangSmith/OpenTelemetry
  observability, and governed tool approvals.
- [x] Build diagrams from implemented code paths, not roadmap intent. Include
  source file references near diagrams so future maintainers can verify them.
- [x] Add "how to add" docs for a new AI workflow, context profile, memory type,
  MCP tool, retrieval provider, reranker, extractor, eval case, and security
  policy check.
- [x] Add deployment documentation and environment profiles for local,
  deterministic demo, provider-backed demo, staging-like, and production-like
  modes.
- [x] For each environment profile, document required env vars, disabled
  provider paths, auth mode, egress posture, cache posture, eval/report
  behavior, object-storage expectation, and commands to verify the profile.
- [x] Add production-auth notes for JWT/OIDC/JWKS expectations, API-key service
  accounts, token/key rotation, token revocation, dev-auth isolation, and known
  remaining auth limitations.
- [x] Add production object-storage and backup/restore guidance for Postgres,
  pgvector embeddings, object storage, eval reports, AI traces, and audit logs.
- [x] Add a dependency-audit runbook covering `pip-audit`, `pnpm audit --prod`,
  non-strict local behavior, strict CI behavior, expected failure modes, and how
  warnings appear in `scripts/security_check.py` and the quality gate.
- [x] Keep workspace/team collaboration flows out of Sprint 60 because the
  portfolio demo remains focused on the single-project workflow.
- [x] Keep multi-project portfolio views out of Sprint 60 because the
  single-project workflow must stay straightforward.
- [x] Document advanced integration settings for MCP/API clients, search
  providers, model providers, OCR/multimodal providers, and egress policy in
  developer docs instead of adding new primary-workflow UI.
- [x] Keep all advanced settings behind Inspect/developer navigation. Do not add
  new homepage cards, hero sections, or primary-workflow panels for MCP,
  provider, cache, eval, or extraction internals.
- [x] Document seeded hosted-demo smoke tests for the critical path and record
  the hosted-infrastructure blocker for project load, Ask Thesys, evidence
  inspection, validation mission, decision recommendation, memory/context
  Inspect, MCP read tool, and eval report.
- [x] Retry the deferred Sprint 51 and Sprint 53 web checks: web typecheck, web
  tests, IDE browser QA for memory/context Inspect, Ask Thesys streaming,
  cancellation/timeout UI, citation drilldowns, and advanced report/settings
  surfaces.
- [x] For Sprint 51 browser QA, record the exact npm/browser blocker and future
  owner for memory filters, proposal review, conflict resolution, context-pack
  included/dropped/compressed/stale rows, and primary-workflow clutter checks.
- [x] For Sprint 53 browser QA, record the exact npm/browser blocker and future
  owner for streamed answer deltas, retrieval/tool/proposal events,
  cancellation, timeout fallback, final metadata parity with non-streaming
  response, action cards, and collapsed citation drilldowns.
- [x] Retry the deferred Sprint 56 web checks: web typecheck, web tests, and IDE
  browser QA for the hidden eval-report Inspect panel, including collapsed gate
  status, trend rows, cache/cost metrics, failing-case links, and no homepage
  clutter.
- [x] Retry Sprint 57 cache-related web checks if they were not completed at the
  Sprint 57 commit: AI status tooltip cache posture, Evidence retrieval cache
  diagnostic line, hidden eval cache metrics, stale-denial reporting, and no
  new homepage/dashboard clutter.
- [x] Retry or complete Sprint 58 document-intelligence UI checks: Evidence
  Inspect and citation drilldowns must show extraction method, confidence,
  source snapshot ID, page/section/table/region/OCR provenance, screenshot
  availability, source-quality explanation, provider-unavailable warnings,
  source-discovery provenance, retrieval-result provenance, and no new
  homepage/dashboard clutter.
- [x] Resolve every remaining Sprint 58 carry-forward explicitly before the
  Sprint 60 commit. Required dispositions:
  maintained parser dependency either added or documented as an intentional V1
  deterministic fallback; screenshot/page artifact capture either implemented
  with storage/redaction policy or moved to a named future backlog item;
  screenshot-region table/OCR provenance either implemented or marked out of
  V1 with reason; live Tavily/multimodal credential QA either run with command
  output or recorded as unavailable with rerun instructions; Project Inspect
  trust summaries browser-checked or recorded with exact blocker. Required IDs:
  `G48-A`, `G48-B`, `G48-C`, `G48-D`, and `G48-E`.
- [x] Close the Sprint 41 residuals in docs/status with concrete artifacts:
  hosted-demo/production auth mode table, JWT/OIDC/JWKS expectations,
  API-key/service-account rotation and revocation runbook, live-provider egress
  checklist, backup/restore checklist, dependency-audit command outcomes, and
  exact notes for anything still unavailable locally. Required IDs:
  `G41-A`, `G41-B`, `G41-C`, `G41-D`, and `G41-E`.
- [x] Close the Sprint 42 residuals in docs/status with concrete artifacts:
  context profile inventory, profile owner files, token budget table,
  compression/stale/conflict policy table, dropped-context explanation examples,
  eval command list, and browser QA notes for context Inspect rows. Required
  IDs: `G42-A`, `G42-B`, `G42-C`, and `G42-D`.
- [x] Close the Sprint 43 residuals in docs/status with concrete artifacts:
  memory type inventory, lifecycle diagram, write-review approval flow,
  compaction policy, preference capture/edit/archive flow, conflict resolution
  flow, extension instructions for adding memory types, and browser QA notes for
  filters/proposals/conflict actions. Required IDs: `G43-A`, `G43-B`,
  `G43-C`, and `G43-D`.
- [x] Close the Sprint 44 residuals in docs/status with concrete artifacts:
  MCP lifecycle diagram, stdio command, HTTP/SSE command, example client config,
  read-tool smoke command, proposal-tool approval smoke command, structured
  error examples, redaction/audit examples, and known client limitations.
  Required IDs: `G44-A`, `G44-B`, `G44-C`, and `G44-D`.
- [x] Close the Sprint 45 residuals in docs/status with concrete artifacts:
  retrieval pipeline diagram, Postgres text-rank/BM25 limitation notes, MMR and
  source-diversity policy, reranker provider extension steps, citation verifier
  owner files, cache invalidation notes, and retrieval/citation eval commands.
  Required IDs: `G45-A`, `G45-B`, `G45-C`, and `G45-D`.
- [x] Close the Sprint 46 residuals in docs/status with concrete artifacts:
  Ask Thesys streaming event contract, cancellation/timeout behavior, final
  payload parity notes, citation drilldown fields, guide eval command list, and
  browser QA notes for streamed events, proposal cards, and citation drilldowns.
  Required IDs: `G46-A`, `G46-B`, `G46-C`, and `G46-D`.
- [x] Close the Sprint 47 residuals in docs/status with concrete artifacts:
  quality-gate command matrix, gate pass/warn/fail policy, report artifact
  paths, trend persistence path, prompt/schema changelog location,
  OpenTelemetry/LangSmith setup notes, cache/cost metric examples, and CI usage
  instructions. Required IDs: `G47-A`, `G47-B`, `G47-C`, and `G47-D`.
- [x] Close the Sprint 49 residuals in docs/status with concrete artifacts:
  final package map, moved-module/shim ledger, dependency-boundary check output,
  DTO ownership map, characterization test matrix, known services intentionally
  left centralized, and remaining future cleanup backlog if any. Required IDs:
  `G49-A`, `G49-B`, `G49-C`, `G49-D`, and `G49-E`.
- [x] Close the Sprint 50 residuals in docs/status with concrete artifacts:
  README project navigation, AI engineering tour, source-linked diagrams,
  targeted docstrings/comments, deployment/environment profiles, hosted-demo
  smoke commands, and honest remaining-limit notes. Required IDs: `G50-A`,
  `G50-B`, `G50-C`, `G50-D`, and `G50-E`.
- [x] Run a final carried-gap audit before the Sprint 60 commit. For every
  Sprint 41-50 item in the gap coverage ledger, record one of: implemented with
  verification link, intentionally out of V1 scope with reason, or still open
  with a new backlog owner. Do not leave any carried gap only implied by a broad
  sprint title. The audit must enumerate every `G41-*` through `G50-*` ID.
- [x] Run and record strict or non-strict security/dependency checks:
  `python3 scripts/security_check.py`, `python3 scripts/audit_dependencies.py`
  where available, `pip-audit` availability, and `pnpm audit --prod` result.
  If registry access blocks a check, record the exact error and next owner.
- [x] Document remaining honest limits after Sprints 51-60, including any
  provider-only features not exercised in deterministic local mode, OIDC/JWKS
  production-auth gaps, live Tavily/multimodal credential requirements, and
  deployment assumptions.
- [x] Run docs checks and full tests/evals, and record exact web/browser
  blockers for settings or portfolio UI checks that could not run.

Final Sprint 60 closeout verification recorded for pickup:

- Final disposition audit script found `44` rows, no missing `G*` IDs, no
  duplicates, and no extra IDs in `IMPLEMENTATION_STATUS.md`.
- `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  passed (`60 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  passed (`66 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_feature_package_boundaries.py -q`
  passed (`67 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py app/tests/test_feature_package_boundaries.py -q`
  passed (`67 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  passed (`77 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_research_history_eval.py app/tests/test_demo_eval_workflows.py app/tests/test_feature_package_boundaries.py -q`
  passed (`75 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_security_governance.py app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py -q`
  passed (`37 passed, 3 warnings`).
- `python3 scripts/eval_retrieval_quality.py` passed (`7/7`).
- `python3 scripts/eval_extraction_quality.py --json` passed (`7/7`) with
  explicit warnings for missing `TAVILY_API_KEY` and deterministic multimodal
  provider mode.
- `python3 scripts/security_check.py` completed non-strict: backend
  security/governance tests passed, AI quality eval passed (`10/10`), and
  dependency audit warnings remained for missing `pip`/`pip-audit` in the API
  venv plus npm registry fetch failures.
- `python3 scripts/audit_dependencies.py` completed non-strict with the same
  dependency blockers; direct `pip-audit` returned `command not found`.
- `pnpm --filter thesys-web typecheck` and `pnpm --filter thesys-web test`
  repeatedly hit npm registry `ECONNRESET` during pnpm dependency
  status/install and were stopped with SIGINT after retries.
- `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60-final LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security`
  completed with warn status (`40/40`, no failed checks, warning gates:
  `mcp_contract`, `security_check`).
- `cd apps/api && .venv/bin/pytest -q` passed (`264 passed, 3 warnings`).
- `python3 scripts/check_feature_boundaries.py`, `cd apps/api && .venv/bin/ruff check app`,
  `cd apps/api && .venv/bin/python -m compileall app -q`, and
  `git diff --check` passed.
- Conflict-marker scan found no matches.

- [x] Commit Sprint 60.
