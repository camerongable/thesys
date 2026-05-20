# Architecture

Sprint 0 establishes the service boundaries from `IMPLEMENTATION_BRIEF.md`:

- Next.js web app in `apps/web`
- FastAPI API gateway in `apps/api`
- PostgreSQL with `pgvector`
- Redis for future async workflow support
- MinIO for local S3-compatible object storage
- LiteLLM proxy for future model routing

The MVP product architecture should keep structured project state in Postgres
and use markdown artifacts only as display/export views over structured records.
