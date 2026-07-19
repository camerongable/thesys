# Evals And Observability

Thesys treats AI quality as a versioned product surface. Local eval scripts,
quality gates, persisted AI run records, and optional LangSmith export make
model behavior inspectable without requiring live provider credentials.

## When Evals Run

Thesys uses several evaluation paths. They do not all run automatically, and
they answer different questions.

| Trigger | What runs | Purpose |
| --- | --- | --- |
| On-demand project action | The API evaluation endpoints in `apps/api/app/routers/evals.py` | Evaluate a specific project or workflow when a user requests it. |
| Manual local command | `pnpm eval:research`, `pnpm eval:ai`, `pnpm eval:extraction`, or `pnpm eval:quality` | Produce focused, explainable quality evidence while developing or preparing a demo. |
| Pull request | Selected evaluation contracts, security tests, fast Promptfoo, and OSV comparison against the base branch in the [Security workflow](../.github/workflows/security.yml) | Catch behavior regressions and newly introduced dependency vulnerabilities before merge without making existing dependency debt hide all PR results. |
| Scheduled or manually dispatched workflow | The full security suite, full Promptfoo suite, and full OSV dependency baseline in the [Security workflow](../.github/workflows/security.yml); scheduled runs also execute Garak. | Run broader adversarial and dependency checks without slowing every pull request. Manual runs can opt into Garak only when a protected target is configured. |
| Version tag | The full release evidence workflow, including image scanning and provenance work, in [Release Security](../.github/workflows/release-security.yml) | Capture a release-oriented security record when a version is published. |

The quality-report commands are intentionally manual: they produce artifacts
for review rather than an automatic merge gate. Pull requests still exercise
their underlying evaluation contracts, but do not run every report-generation
script or the full scheduled adversarial suite. To run the broader suite against
a pull-request branch, use **Actions -> Security -> Run workflow**, select the
branch, and leave `run_garak` disabled unless the protected Garak target secrets
are intentionally configured for that run.

## Quality Gate Commands

Aggregate local gate:

```bash
THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60 LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json
```

Common focused gates:

```bash
python3 scripts/eval_ai_quality.py --json
python3 scripts/eval_retrieval_quality.py
python3 scripts/eval_extraction_quality.py --json
python3 scripts/eval_research_sprints.py --json
python3 scripts/eval_mcp_contract.py --help
```

Live MCP contract, when a running API and project exist:

```bash
python3 scripts/eval_mcp_contract.py --project-id <project_id> --json
```

## Gate Policy

| Status | Meaning |
|---|---|
| `pass` | Required checks passed. |
| `warn` | Core checks passed but one or more gates were skipped, unavailable, or environment-bound. |
| `fail` | At least one required check failed. |

Unavailable provider, browser, audit, or live-project gates must be recorded as
warnings with exact rerun commands. They should not be hidden as completed work.

## Reports And Trends

The quality gate can write:

- JSON report
- Markdown report
- HTML report
- latest-report aliases
- JSONL trend rows
- optional redacted LangSmith export payloads

Feature owners:

| Concern | Source |
|---|---|
| Gate result shaping | `apps/api/app/features/evals/gate_results.py` |
| Report file reading | `apps/api/app/features/evals/report_files.py` |
| Report writing and rendering | `apps/api/app/features/evals/report_writer.py` |
| Aggregate summary | `apps/api/app/features/evals/report_summary.py` |
| Report/trend failure payloads | `apps/api/app/features/evals/report_failures.py` |
| Metric records | `apps/api/app/features/evals/metric_records.py` |
| Local observability metrics | `apps/api/app/features/evals/observability_metrics.py` |
| LangSmith export shaping | `apps/api/app/features/evals/langsmith_export.py` |

## Metrics

Local OpenTelemetry-compatible metric payloads include:

- workflow latency
- model latency
- retrieval latency
- timeout counts
- approval wait time
- provider egress attributes
- cache hit/miss/stale denial counts
- saved tokens
- saved cost
- saved latency
- budget denial metrics

AI run and step records persist model, prompt version, latency, token/cost,
trace, and error metadata. Redaction is applied before audit, trace, tool, and
LangSmith export payloads leave local boundaries.

## Prompt And Schema Changelog

Prompt/schema/context/retrieval/memory/tool changes are tracked in:

```text
docs/AI_CHANGELOG.md
docs/BACKEND_FEATURE_PACKAGE_MAP.md
```

When adding a new workflow or model call, update the changelog, add a focused
eval or route test, and record prompt/schema version metadata in AI run fields.

## Verification

```bash
cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_research_history_eval.py app/tests/test_demo_eval_workflows.py app/tests/test_feature_package_boundaries.py -q
THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60 LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json
```

Sprint 60 hidden report browser QA should cover collapsed gate details, trend
rows, failing-case links, budget/cache/cost metrics, and no dashboard clutter.

## Current Limits

- Full MCP contract execution needs a live API and project ID.
- Security dependency audits depend on local tool and registry availability.
- LangSmith upload is optional; local redacted export payloads are covered
  without uploading.
- Full gate execution, trend persistence policy, and upload side-effect
  ownership remain future cleanup for the feature-package refactor.
