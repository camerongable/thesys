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
