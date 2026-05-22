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
