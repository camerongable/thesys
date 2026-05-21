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
