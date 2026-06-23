# API

Sprint 0 exposes:

```http
GET /health
```

Sprint 1 exposes authenticated local-dev identity and project APIs:

```http
GET /api/me
```

```http
GET    /api/projects
POST   /api/projects
GET    /api/projects/{project_id}
PATCH  /api/projects/{project_id}
DELETE /api/projects/{project_id}
```

Local development auth uses `AUTH_MODE=dev` and auto-provisions a user/workspace
from `X-Dev-User-Email` and `X-Dev-User-Name`.

Sprint 2 exposes a structured-output smoke test for the LiteLLM/stub
infrastructure:

```http
POST /api/ai/test-structured-output
```

The endpoint creates `ai_runs` and `ai_steps` rows, returns typed JSON, and uses
the deterministic dev stub when `LLM_STUB_MODE=always` or when
`LLM_STUB_MODE=auto` and no provider API key is configured.

Sprint 9 adds AI mode and LiteLLM health visibility:

```http
GET /api/ai/status
```

The status response reports `LLM_STUB_MODE`, the resolved mode (`stub` or
`live`), `LLM_FALLBACK_POLICY`, `LLM_STRUCTURED_OUTPUT_REPAIR_ATTEMPTS`,
configured model, LiteLLM reachability, provider-key presence as booleans only,
and the active embedding configuration. Add
`?include_structured_output_check=true` to run a small structured-output
healthcheck. The endpoint uses the same auth dependency as other `/api/*`
routes.

Structured-output validation is always strict. In live mode, invalid model JSON
is repaired up to `LLM_STRUCTURED_OUTPUT_REPAIR_ATTEMPTS` times. Workflow-level
deterministic fallback is controlled by `LLM_FALLBACK_POLICY`:
`disabled` fails after repair, `emergency` falls back only after model or
validation failure, and `always` skips model generation for deterministic local
development.

Sprint 3 exposes structured intake:

```http
POST /api/projects/{project_id}/intake/analyze
POST /api/projects/{project_id}/intake/answer
POST /api/projects/{project_id}/intake/finalize
```

Sprint 4 exposes evidence ingestion and retrieval:

```http
GET    /api/projects/{project_id}/evidence
POST   /api/projects/{project_id}/evidence/url
POST   /api/projects/{project_id}/evidence/note
POST   /api/projects/{project_id}/evidence/file
POST   /api/projects/{project_id}/evidence/retrieve
POST   /api/projects/{project_id}/evidence/reembed
GET    /api/projects/{project_id}/evidence/{source_id}
POST   /api/projects/{project_id}/evidence/{source_id}/reprocess
DELETE /api/projects/{project_id}/evidence/{source_id}
```

Retrieval supports `semantic`, `keyword`, and `hybrid` modes and returns source
IDs, chunk IDs, scores, source metadata, embedding provider/model/version
metadata, retrieval diagnostics, and trace IDs for the `ai_runs` / `ai_steps`
records. In Postgres, semantic and hybrid retrieval use SQL-level pgvector
nearest-neighbor ranking by default. Local SQLite tests and offline demos keep a
deterministic Python fallback path.

`POST /api/projects/{project_id}/evidence/reembed` supports:

```json
{
  "dry_run": true,
  "force": false,
  "scope": "project"
}
```

Use it after changing `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`,
`EMBEDDING_DIMENSION`, or `EMBEDDING_VERSION`.

Sprint 5 exposes artifact listing and opportunity brief generation:

```http
GET  /api/projects/{project_id}/artifacts
POST /api/projects/{project_id}/artifacts/opportunity-brief/generate
GET  /api/projects/{project_id}/artifacts/{artifact_id}
GET  /api/projects/{project_id}/artifacts/{artifact_id}/versions
```

Sprint 6 exposes competitor profile and landscape generation APIs:

```http
GET   /api/projects/{project_id}/competitors
POST  /api/projects/{project_id}/competitors
POST  /api/projects/{project_id}/competitors/analyze
GET   /api/projects/{project_id}/competitors/{competitor_id}
PATCH /api/projects/{project_id}/competitors/{competitor_id}
```

Competitor analysis ingests user-seeded competitor URLs when requested, links
competitor evidence chunks with `competitor_id` metadata, writes structured
competitor profiles, and saves a versioned `competitor_landscape` artifact.

Sprint 7 exposes assumption, risk, experiment, and decision APIs:

```http
GET   /api/projects/{project_id}/assumptions
POST  /api/projects/{project_id}/assumptions/extract
PATCH /api/projects/{project_id}/assumptions/{assumption_id}

GET   /api/projects/{project_id}/risks
POST  /api/projects/{project_id}/risks/extract

GET   /api/projects/{project_id}/experiments
POST  /api/projects/{project_id}/experiments/validation-plan
POST  /api/projects/{project_id}/experiments/{experiment_id}/results

GET  /api/projects/{project_id}/decisions
POST /api/projects/{project_id}/decisions
GET  /api/projects/{project_id}/decisions/{decision_id}
```

Validation-plan generation writes a versioned `validation_plan` artifact and
creates linked experiment records. Experiment results update the linked
assumption status/confidence and recalculate project confidence from assumption
scores. Decisions can link to assumptions, risks, evidence, artifacts,
competitors, and experiments after workspace-scoped target validation.

Sprint 8 exposes workflow trace, demo seed, and MVP eval APIs:

```http
GET /api/projects/{project_id}/workflows
GET /api/workflows/{run_id}
GET /api/workflows/{run_id}/events

POST /api/demo/seed

GET /api/projects/{project_id}/evals/mvp
```

The workflow events endpoint streams Server-Sent Events from persisted
`ai_runs` and `ai_steps`. The demo seed endpoint is available only in local
dev mode and creates the fitness coach scenario from the implementation brief.

Sprint 10 exposes guided strategic overview APIs:

```http
GET  /api/projects/{project_id}/overview
GET  /api/projects/{project_id}/readiness
GET  /api/projects/{project_id}/strategic-updates
POST /api/projects/{project_id}/next-action
```

These endpoints compute founder-facing project state from existing structured
records. The overview response includes current lifecycle stage, current
recommendation, one primary next best action, idea readiness, strategic
snapshot, evidence health, recent strategic updates, key assumptions, and key
risks. The next-action endpoint returns the current recommended route/action;
it does not start new V1 monitoring or agentic research work.

V1 research sprint discovery APIs:

```http
GET   /api/projects/{project_id}/research-sprints
POST  /api/projects/{project_id}/research-sprints/plan
PATCH /api/projects/{project_id}/research-plans/{plan_id}
POST  /api/projects/{project_id}/research-sprints/{sprint_id}/approve
POST  /api/projects/{project_id}/research-sprints/{sprint_id}/reject

GET  /api/projects/{project_id}/research-sprints/{sprint_id}/sources
POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover
POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/approve
POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/reject

GET   /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates
POST  /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/discover
PATCH /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}
POST  /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/approve
POST  /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/reject
```

Discovery remains approval-gated. In live mode, source and competitor discovery
call the LiteLLM structured-output path and log model, token, and cost metadata
on `ai_runs` / `ai_steps`; stub mode uses deterministic fallback candidates.
Source candidates are ranked and deduped before review; approved sources enter
the evidence pipeline by fetching the reviewed URL, extracting readable text,
chunking, embedding, and recording research-sprint provenance on the chunks.
If a reviewed URL blocks automated fetch, the API ingests the reviewed
candidate snapshot instead and records the remote fetch error in chunk metadata.
Competitor candidates can be edited before approval; approved candidates become
project competitors, ingest their URL or candidate snapshot when available, and
link ingested evidence chunks to the competitor for scoped retrieval.

V1 agentic research, research history, and research quality APIs:

```http
POST /api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run
POST /api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/approve
POST /api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/reject

GET  /api/projects/{project_id}/research-history
GET  /api/projects/{project_id}/evals/v1-research
```

The agentic RAG run writes a cited `research_memo` artifact and pauses before
major project-memory updates. Approving the memo writes research-derived
assumptions and risks into project memory; rejecting it keeps the memo while
recording that the proposed memory updates were rejected. Research history
summarizes the plan, source discovery, competitor discovery, memo generation,
memory update review, and recommendation changes for each sprint. The V1 eval
checks source/competitor discovery, citation coverage, unsupported claims,
assumption quality, validation actions, traceability, cost, latency, and the
10-case research sprint eval dataset.
