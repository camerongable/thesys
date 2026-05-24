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
GET    /api/projects/{project_id}/evidence/{source_id}
POST   /api/projects/{project_id}/evidence/{source_id}/reprocess
DELETE /api/projects/{project_id}/evidence/{source_id}
```

Retrieval supports `semantic`, `keyword`, and `hybrid` modes and returns source
IDs, chunk IDs, scores, source metadata, and trace IDs for the `ai_runs` /
`ai_steps` records.

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
