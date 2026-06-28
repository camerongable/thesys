# Repository Navigation

This repo is easiest to understand by following the product workflow first, then the AI service behind each step.

## Main Paths

| Path | Purpose |
|---|---|
| `apps/api/app/routers/` | FastAPI route handlers. Start here to see API contracts and auth boundaries. |
| `apps/api/app/services/` | Product and AI behavior. Most portfolio-relevant AI engineering code lives here. |
| `apps/api/app/services/common/` | Shared service utilities extracted from feature services. |
| `apps/api/app/ai/` | LiteLLM client, structured-output helper, prompt versions, and prompt-safety constants. |
| `apps/api/app/mcp/` | MCP-shaped adapter over the governed internal tool registry. |
| `apps/api/app/temporal/` | Durable workflow definitions and activities for long-running research sprints. |
| `apps/api/app/db/models/` | SQLAlchemy domain model for project memory, evidence, artifacts, tools, approvals, and AI traces. |
| `apps/api/app/schemas/` | Pydantic API contracts and structured AI payloads. |
| `apps/web/src/` | Next.js project workspace, guide panel, workflow traces, and evidence UI. |
| `scripts/` | Local eval gates and portfolio demo checks. |

## AI Codepath Index

| Feature | Primary files |
|---|---|
| Agentic research | `services/agentic_research_service.py`, `temporal/research_workflow.py` |
| Retrieval | `services/retrieval_service.py`, `services/embedding_service.py`, `schemas/evidence.py` |
| Context engineering | `services/context_service.py`, `schemas/context.py` |
| Persistent memory | `services/memory_service.py`, `db/models/memory.py`, `routers/memory.py` |
| Tool governance | `services/tool_service.py`, `services/governance_service.py`, `mcp/adapter.py` |
| Evidence ingestion | `services/evidence_service.py`, `services/source_provenance_service.py`, `services/multimodal_extraction_service.py` |
| Ask Thesys | `services/guide_service.py`, `routers/projects.py`, `apps/web/src/features/projects/guide-panel.tsx` |
| Observability and evals | `services/ai_run_service.py`, `services/eval_service.py`, `scripts/eval_ai_quality.py` |
| Security | `core/security.py`, `services/source_provenance_service.py`, `tests/test_security_governance.py` |

## Onboarding Checklist

1. Run `docker compose up -d`.
2. Run `cd apps/api && uv sync`.
3. Run `pnpm install`.
4. Start the API with `cd apps/api && uvicorn app.main:app --reload --port 8000`.
5. Start the web app with `pnpm --filter thesys-web dev`.
6. Seed a demo with `curl -X POST http://localhost:8000/api/demo/seed`.
7. Run backend checks with `cd apps/api && uv run pytest`.
8. Run eval gates with `pnpm eval:research` and `pnpm eval:ai`.
9. Inspect AI traces through project workflow details and eval endpoint output.
10. Switch to live mode by changing model, embedding, search, and multimodal provider environment variables.
