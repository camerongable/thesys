# Architecture

Sprint 0 establishes the service boundaries from `IMPLEMENTATION_BRIEF.md`:

- Next.js web app in `apps/web`
- FastAPI API gateway in `apps/api`
- PostgreSQL with `pgvector`
- Redis for future async workflow support
- MinIO for local S3-compatible object storage
- LiteLLM proxy for model routing
- AI run/step tables for workflow observability, token usage, and cost tracking

The MVP product architecture should keep structured project state in Postgres
and use markdown artifacts only as display/export views over structured records.

Sprint 2 adds a local deterministic LLM stub path. The API uses it by default
when provider keys are absent, while preserving the same structured-output and
AI-run logging path used by real LiteLLM calls.

Sprint 4 adds the first RAG foundation:

- Evidence sources are ingested through URL, note, and file endpoints.
- Uploaded files are stored through the object storage boundary. Docker uses
  MinIO/S3 mode; tests and local non-Docker runs can use local filesystem mode.
- Parsed text is normalized, summarized, classified, chunked, embedded, and
  stored in Postgres/pgvector.
- Retrieval is project/workspace-scoped and supports semantic, keyword, and
  hybrid scoring.
- Evidence ingestion and retrieval create `ai_runs` and `ai_steps` traces so
  generated artifacts in later sprints can expose the retrieval context they
  used.

Sprint 10 adds a computed project overview layer. `ProjectOverviewService`
derives founder-facing guidance from existing records instead of adding new
persistence: project lifecycle stage, recommendation, next best action, idea
readiness, strategic snapshot, evidence health, and recent strategic updates.
This keeps the overview aligned with the project graph while leaving workflow
execution, RAG, and artifact generation unchanged.
