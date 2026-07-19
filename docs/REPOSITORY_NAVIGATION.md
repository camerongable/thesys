# Repository Navigation

## Start Here

Read [Portfolio Owner Guide](PORTFOLIO_OWNER_GUIDE.md) first for the product
story, runtime flows, demo narrative, and honest limits. This document is the
source map for tracing those flows into code. It is intentionally shorter than
the implementation brief and status ledger.

## Product And Runtime Map

| Area | Primary path | What it owns |
|---|---|---|
| Web workspace | `apps/web/src/` | Next.js screens, project workflow UX, evidence views, guide panel, and typed API client. |
| HTTP/API boundary | `apps/api/app/routers/`, `apps/api/app/main.py` | FastAPI route contracts, request lifecycle, authorization dependencies, and response serialization. |
| Product services | `apps/api/app/services/` | Research, evidence, retrieval, memory, guide, validation, decisions, tool governance, and security orchestration. |
| Feature packages | `apps/api/app/features/` | Feature-owned pure shaping, prompt/context construction, policy helpers, protocol serialization, and evaluation support behind service compatibility shims. |
| AI boundary | `apps/api/app/ai/` | LiteLLM gateway, structured-output repair, deterministic fallback, and prompt version helpers. |
| Security boundary | `apps/api/app/security/`, `apps/api/app/core/auth.py` | Guardrails, encryption, secret providers, approved model/prompt registries, OIDC/JWT handling, and security contracts. |
| Persistence | `apps/api/app/db/`, `apps/api/alembic/` | SQLAlchemy models, tenant context, PostgreSQL/pgvector migrations, RLS policies, and application database roles. |
| Durable execution | `apps/api/app/temporal/` | Temporal workflows and activities for research sprints, retention, and approval waits. |
| Governed tools/MCP | `apps/api/app/mcp/`, `apps/api/app/features/governance_tools/` | MCP protocol adaptation, schema validation, policy checks, risk, approval, and audit boundaries. |
| Infrastructure | `docker-compose.yml`, `infra/`, `apps/*/Dockerfile` | Local dependencies, container build stages, PostgreSQL bootstrap, and Kubernetes baseline. |
| Tests and evaluation | `apps/api/app/tests/`, `apps/web/tests/`, `security/redteam/`, `scripts/` | Product/security contracts, web behavior, deterministic adversarial cases, and quality/report tooling. |

## Core Flows And First Files

| Flow | Start with | Then trace |
|---|---|---|
| Research sprint | `services/agentic_research_service.py` | `services/research_sprint_service.py`, `temporal/workflows.py`, `features/research/` |
| Evidence ingestion | `services/evidence_service.py` | `services/data_protection_service.py`, secure parser/image services, `features/evidence/` |
| Retrieval and citations | `services/retrieval_service.py` | `services/embedding_service.py`, `features/retrieval/`, `features/evidence/citation_verifier.py` |
| Ask Thesys | `services/guide_service.py` | `features/guide/`, `routers/projects.py`, `apps/web/src/features/projects/guide-panel.tsx` |
| Memory and approval | `services/memory_service.py` | `features/memory/`, `services/tool_service.py`, governance routes/models |
| Tool/MCP execution | `services/tool_service.py` | `features/governance_tools/`, `mcp/adapter.py`, `services/remote_mcp_*` |
| Authorization and RLS | `core/auth.py` | `db/tenant.py`, `alembic/versions/0029_tenant_rls.py`, security tests |
| Guardrails and security events | `security/guardrails/` | `services/security_event_service.py`, `services/security_policy_service.py` |
| Workflow budgets | `services/workflow_budget_service.py` | `apps/api/app/security/workflow_budget.py`, research/tool/retrieval call sites |

## Documentation Map

| Need | Read |
|---|---|
| Explain the project or give a demo | [Portfolio Owner Guide](PORTFOLIO_OWNER_GUIDE.md) |
| Understand the product and local setup | [README](../README.md) |
| Explain major packages and tools | [Dependencies And Tooling](DEPENDENCIES.md) |
| Understand the AI design and principles | [AI Architecture](AI_ARCHITECTURE.md), [Context Engineering](CONTEXT_ENGINEERING.md), [Retrieval And Citations](RETRIEVAL_AND_CITATIONS.md), [Memory System](MEMORY_SYSTEM.md) |
| Understand durable workflows and distributed behavior | [Distributed Systems And Durable Execution](DISTRIBUTED_SYSTEMS.md), [Deployment And Security](DEPLOYMENT_SECURITY.md) |
| Understand tools and integrations | [Governance And MCP](GOVERNANCE_AND_MCP.md), [MCP Integration](MCP_INTEGRATION.md), [Source Intelligence](SOURCE_INTELLIGENCE.md) |
| Understand security controls or find a runbook | [Security Documentation Guide](security/README.md), [Security Overview](security.md), [Security Architecture](security/SECURITY_ARCHITECTURE.md), [Threat Model](security/THREAT_MODEL.md), [Control Matrix](security/CONTROL_MATRIX.md), [Abuse Cases](security/ABUSE_CASES.md) |
| Understand deployments and verification | [Deployment And Security](DEPLOYMENT_SECURITY.md), [Evals And Observability](EVALS_AND_OBSERVABILITY.md), [Security And Evals](SECURITY_AND_EVALS.md) |
| Understand exact delivered scope | [Implementation Brief](../IMPLEMENTATION_BRIEF.md), [Implementation Status](../IMPLEMENTATION_STATUS.md) |
| Understand old refactor/package boundaries | [Backend Feature Package Map](BACKEND_FEATURE_PACKAGE_MAP.md) |

## Documentation Maintenance Rule

When a change affects behavior, a public/runtime boundary, a direct dependency,
or a verification command, update the closest focused document in the same
change. Update the README or this navigation map when discoverability changes.
Treat the implementation brief as planned scope and the implementation status as
verified evidence; neither should replace an owner-facing explanation.

Run the documentation link check before merging documentation changes:

```bash
python3 scripts/check_documentation_links.py
```
