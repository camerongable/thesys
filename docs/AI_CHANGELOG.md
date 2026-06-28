# AI Engineering Changelog

This changelog tracks AI-facing behavior changes that can affect prompts,
schemas, context, memory, retrieval, tools, providers, evals, or governance.
Each entry names the evals that should catch regressions.

## Sprint 56: Observability V2 and Eval Gates

- Added `scripts/eval_quality_gate.py` as the aggregate local quality gate.
  It writes JSON, Markdown, HTML, and JSONL trend artifacts under
  `reports/evals/` by default.
  - Expected impact: reviewers can see gate status, failing case IDs,
    version metadata, and rerun commands from one report.
  - Regression coverage: `app/tests/test_eval_reports.py`,
    `python3 scripts/eval_quality_gate.py`.
- Added `scripts/eval_extraction_quality.py` for credential-free source and
  document extraction readiness checks.
  - Expected impact: the aggregate gate has an explicit extraction/provenance
    slice instead of relying only on broader backend tests.
  - Regression coverage: `python3 scripts/eval_extraction_quality.py --json`,
    `app/tests/test_eval_reports.py`.
- Added hidden eval report endpoints under
  `/api/projects/{project_id}/evals/reports/*` and
  `/api/projects/{project_id}/evals/observability-metrics`.
  - Expected impact: Inspect surfaces can show local eval status and
    OpenTelemetry-compatible project metrics without cluttering the homepage.
  - Regression coverage: `app/tests/test_eval_reports.py`.
- Added OpenTelemetry-compatible metric names for workflow, model, retrieval,
  token, cost, approval, tool-denial, provider-egress, timeout, cancellation,
  and cache signals.
  - Expected impact: local AI runs, report files, and future dashboards can use
    stable metric names.
  - Regression coverage: `app/tests/test_eval_reports.py`.
- Added optional redacted LangSmith export/upload support to the quality gate.
  Upload is disabled unless explicitly requested.
  - Expected impact: local reports can be mirrored externally without sending
    obvious secrets.
  - Regression coverage: `app/tests/test_langsmith_observability.py`,
    `app/tests/test_eval_reports.py`.

## Sprint 55: Retrieval Quality V2

- Added Postgres text-rank signals, BM25-like local scoring, MMR diversity,
  source/domain/source-type/competitor caps, and a swappable reranker adapter.
  - Expected impact: retrieval contexts should be more diverse and less
    dominated by one source.
  - Regression coverage: `scripts/eval_retrieval_quality.py`,
    `app/tests/test_retrieval_quality_eval.py`.
- Added claim-level citation outcomes: supported, weakly supported,
  unsupported, source missing, stale source, and filtered as unsafe.
  - Expected impact: generated artifacts can label weak or unsupported claims
    before they are treated as evidence-backed.
  - Regression coverage: `app/tests/test_citation_verifier.py`,
    `scripts/eval_retrieval_quality.py`.

## Sprint 54: Security and Provider Egress

- Added guarded workflow preflight checks for rate limits, concurrency,
  project token/cost budgets, and provider egress allowlists.
  - Expected impact: expensive AI and integration paths can be denied before
    provider calls begin.
  - Regression coverage: `scripts/security_check.py`,
    `app/tests/test_security_governance.py`.
- Added production auth shapes for JWT and API-key modes with stricter dev-auth
  isolation.
  - Expected impact: local demos stay easy, while production-like modes reject
    dev headers and revoked credentials.
  - Regression coverage: `app/tests/test_security_governance.py`.

## Sprint 53: Ask Thesys Streaming

- Added a stable streaming event protocol for Ask Thesys, including retrieval,
  tool, proposal, timeout, cancellation, metadata, and final events.
  - Expected impact: streamed and non-streamed answers can converge on the same
    final response shape.
  - Regression coverage: `app/tests/test_guide.py`,
    `python3 scripts/eval_ai_quality.py --json`.
- Added collapsed citation drilldowns with source, excerpt, verifier, context,
  and memory details.
  - Expected impact: users can inspect support without turning the guide into a
    trace dashboard.
  - Regression coverage: `app/tests/test_guide.py`.

## Sprint 52: MCP JSON-RPC

- Added MCP JSON-RPC lifecycle support for initialize, tools/list, tools/call,
  structured errors, project-scoped RPC, and stdio bridge usage.
  - Expected impact: external agents can exercise governed Thesys tools through
    a protocol-compatible surface.
  - Regression coverage: `app/tests/test_mcp_adapter.py`,
    `scripts/eval_mcp_contract.py`.

## Sprint 51: Context Compiler and Memory V2

- Added a shared context compiler with workflow profiles for major AI
  workflows, dropped-item explanations, untrusted-content handling, and context
  evals.
  - Expected impact: workflows assemble context through one policy layer instead
    of bespoke prompt stuffing.
  - Regression coverage: `app/tests/test_context_compiler.py`,
    `/api/projects/{project_id}/evals/context`.
- Added memory proposal review, preference memory, compaction candidates,
  conflict metadata, and memory Inspect surfaces.
  - Expected impact: durable memory changes remain inspectable and
    approval-gated.
  - Regression coverage: `app/tests/test_memory_service.py`.
