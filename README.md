# Thesys

**Agentic RAG platform for evidence-backed idea validation.**

Thesys helps founders and builders turn rough business ideas into structured validation decisions. Given a rough idea, the system can run an autonomous research sprint, discover sources and competitors, ingest evidence, generate a cited research memo, identify risky assumptions, create validation plans, and guide build / pivot / pause / kill decisions.

This is currently a **portfolio project**, not a launched commercial product. It is intentionally built to demonstrate production-style AI software engineering patterns: **agentic RAG**, **retrieval-grounded generation**, **structured LLM outputs**, **persistent project memory**, **human-in-the-loop workflows**, **source traceability**, **AI observability**, and **decision-oriented AI UX**.

---

## Why Thesys Exists

Most AI idea tools generate advice in a single conversation.

Thesys is built around a different premise:

> Idea validation is not a chat. It is a stateful workflow.

A founder does not just need “startup advice.” They need to know:

- Is this idea worth pursuing?
- Who or what am I really competing against?
- What evidence supports or weakens the thesis?
- What assumptions must be true?
- What should I validate before building?
- Should I proceed, pivot, pause, or kill the idea?

Thesys turns that process into a structured AI-native workflow.

---

## Core Product Flow

```text
Rough idea
→ autonomous research sprint
→ source and competitor discovery
→ evidence ingestion
→ cited research memo
→ competitor / substitute map
→ ranked assumptions
→ validation plan
→ experiment results
→ decision recommendation
```

The goal is not to replace founder judgment. The goal is to make founder judgment more evidence-backed, structured, and repeatable.

---

## What Makes This Different From a Chatbot

Thesys does not store a loose chat transcript as the primary product object.

It stores structured strategic state:

- project thesis
- target customer
- primary problem
- evidence sources
- cited findings
- open questions
- competitors and substitutes
- assumptions
- risks
- validation plans
- experiment results
- recommendations
- decisions
- strategic updates

This allows the system to reason over a project over time instead of answering disconnected prompts.

---

## Key Features

### Guided Strategic Workspace

Each project has a lifecycle:

```text
Idea → Research → Evidence → Assumptions → Validation → Decision
```

The UI keeps the user focused on:

- current verdict
- next best action
- project stage
- risk level
- confidence level
- evidence health
- riskiest assumption

---

### Autonomous Research Sprints

A user can start with a rough idea and run a research sprint.

The system:

1. creates a research plan
2. discovers relevant sources
3. identifies competitors and substitutes
4. ingests evidence
5. retrieves relevant context
6. generates a cited research memo
7. identifies gaps and assumptions
8. recommends what to validate next

---

### Source and Competitor Discovery

Thesys can discover and classify:

- direct competitors
- indirect competitors
- substitute behaviors
- incumbent platforms
- adjacent solutions
- manual workarounds

The system emphasizes that the real competitor is often not another startup. It may be ChatGPT, Notion, spreadsheets, Reddit, YouTube, or an existing manual workflow.

---

### Evidence-Backed Findings

Research output is grounded in ingested sources.

The Evidence page separates:

- supported findings
- open questions
- source records
- evidence gaps

The app is designed to make uncertainty visible instead of hiding it behind confident AI prose.

---

### Assumption Ranking

Thesys turns research into operational validation priorities.

Each assumption can be ranked by:

- risk
- confidence
- evidence strength
- validation status
- recommended validation method

This helps the user identify the assumption most likely to kill the idea if false.

---

### Validation Planning

For the riskiest assumptions, Thesys can generate validation assets:

- customer interview scripts
- screener questions
- survey questions
- landing page copy
- outreach messages
- success criteria
- failure criteria
- results rubric

The goal is to move from “interesting research” to “what should I test next?”

---

### Decision Workflow

Thesys supports structured decisions:

- proceed
- pivot
- pause
- kill
- continue research

Decisions can include:

- rationale
- supporting evidence
- unresolved risks
- revisit triggers
- experiment results

---

## AI Engineering Portfolio Showcase

Thesys is built to show the difference between a thin LLM wrapper and a durable AI application. The AI layer is visible in the architecture, data model, workflow records, governance model, and UX.

| AI concept | How it is demonstrated in this repo | Technologies and libraries |
|---|---|---|
| Agentic RAG | Autonomous research sprints plan work, call bounded tools, retrieve evidence, detect gaps, run follow-up retrieval, synthesize a memo, critique citations, and wait for human approval before updating project memory. | LangGraph, FastAPI, SQLAlchemy, Temporal, internal tool registry |
| Multi-stage retrieval | Project-scoped retrieval plans broad strategic questions, decomposes subqueries, fuses results, combines semantic and text ranking, reranks candidates, applies MMR diversity controls, assembles a bounded context pack, and returns quality diagnostics. | PostgreSQL, pgvector, Postgres `ts_rank_cd`, BM25-like local scoring, deterministic/LiteLLM/no-op reranker adapters, custom retrieval service |
| Production embeddings | Evidence chunks record provider, model, dimension, version, timestamp, and errors. Local deterministic embeddings stay available for tests, while LiteLLM-backed embeddings support live mode and re-embedding after model changes. | LiteLLM-compatible embeddings API, pgvector, PostgreSQL, Alembic |
| Retrieval-grounded generation | Opportunity briefs, competitor analysis, research memos, Ask Thesys answers, assumptions, and validation plans are generated from project state and retrieved evidence rather than model memory alone. | Retrieval service, Pydantic schemas, LiteLLM, SQLAlchemy |
| Structured LLM outputs | LLM responses are requested as JSON, validated against typed schemas, repaired when possible, and persisted as structured project objects. | Pydantic v2, LiteLLM-compatible chat completions, structured output helper |
| Model gateway and deterministic fallback | Chat, embedding, reranking, and multimodal extraction paths are configurable. Local demos and tests can run without provider credentials. | LiteLLM Proxy, httpx, Ollama, OpenAI-compatible APIs, Gemini, deterministic stubs |
| Persistent project memory | The product stores thesis versions, evidence, artifacts, claims, assumptions, validation missions, decisions, AI runs, AI steps, tool calls, approvals, and audit events instead of relying on chat history. | PostgreSQL, SQLAlchemy, Alembic |
| Unified context engineering | Major AI workflows compile typed context packs with domain state, retrieval results, selected memory, untrusted inputs, tool output metadata, token budgets, dropped-item reasons, and workflow-specific context profiles. | ContextCompiler, Pydantic context schemas, FastAPI services, SQLAlchemy-backed memory |
| Tool governance and MCP adapter | Project capabilities are exposed through explicit tool contracts with schemas, risk levels, access modes, approval policy, audit logging, legacy MCP-shaped HTTP routes, and project-scoped MCP JSON-RPC. | Internal tool registry, MCP JSON-RPC adapter, approval requests, RBAC, audit events |
| Human-in-the-loop agents | AI workflows can propose research plans, memory updates, validation plans, and decisions, but important strategic state changes require user approval. | Tool registry, approval requests, Temporal signals, role-based project permissions |
| Prompt-injection and ingestion safety | Retrieved content is treated as untrusted evidence, URL fetches are SSRF-guarded, uploads are validated, fetched-page injection markers are recorded, and secrets are redacted from traces. | Shared prompt rules, SSRF guards, upload validation, cited synthesis prompts, secret redaction utilities |
| External research connectors | Source discovery can use deterministic local results or live Tavily search. Approved ingestion preserves canonical URLs, content hashes, provider/query/rank provenance, fetch timestamps, and source quality signals. | Tavily API, httpx, source discovery service, source provenance service |
| Source and document intelligence | URL, PDF, text, image, and discovered-source evidence preserve parser/provider metadata, source snapshots, page/section/table/OCR quote provenance, source-quality factors, and collapsed citation drilldowns. Local deterministic OCR/table fixtures keep evals credential-free while live providers remain egress-gated. | Python `html.parser`, pypdf, LiteLLM multimodal chat, source provenance service, citation verifier, Next.js Inspect surfaces |
| Durable orchestration | Long-running research sprints can survive retries, approval waits, and worker restarts through a durable workflow layer. | Temporal, Temporal Python SDK, FastAPI service layer |
| AI observability | AI runs and steps track model, prompt version, latency, token usage, cost, trace IDs, failures, retrieval diagnostics, and generated artifact provenance. | LangSmith, AI run/step tables, LiteLLM cost headers, workflow trace UI |
| Evaluation | Research, guide, AI, context, retrieval, cache, and extraction evals check citation coverage, unsupported claims, agentic traceability, gap detection, retrieval quality, source/document provenance, OCR/table fixtures, live-provider-unavailable warnings, cost visibility, context inclusion, stale-memory exclusion, poisoned-instruction isolation, dropped-context explanations, prompt-injection markers, and secret redaction. | Custom eval scripts, JSON eval cases, pytest-compatible service checks |
| AI product UX | The UI exposes verdicts, next actions, evidence, unsupported gaps, assumptions, validation missions, decisions, citations, and traces while keeping implementation details hidden by default. | Next.js, React, TanStack Query, project guide service |

### Feature-by-Feature AI Engineering Map

**Research Sprint**

- Uses LangGraph for the agent reasoning graph and Temporal for durable business workflow execution.
- Calls governed read/proposal tools instead of letting the model mutate project state directly.
- Produces cited research memos with selected evidence, retrieval diagnostics, unsupported claims, memory-update proposals, and approval gates.

**Evidence and Retrieval**

- Ingests URLs, source-discovery snapshots, notes, PDFs, text files, Markdown, and images.
- Canonicalizes URLs, detects URL/content-hash duplicates, records fetch failure categories, page lineage, source quality signals, and prompt-injection markers.
- Embeds chunks with deterministic or provider-backed embeddings and stores provenance on each chunk.
- Runs SQL-level pgvector retrieval when available, with Python fallback for local/dev resilience.
- Assembles context with token budgets, source diversity, dedupe, rerank scores, and citation IDs.

**Ask Thesys**

- Acts as a bounded project guide, not a general chatbot.
- Retrieves project evidence through the governed `search_project_evidence` tool, generates structured answers in live mode, filters citations to retrieved source IDs, streams guide responses through an SSE endpoint, and falls back to deterministic guidance if generation fails.
- Keeps action cards and UI routing separate from state mutation.
- Creates approval-gated tool proposals for research plans, validation plans, memory updates, and decisions instead of directly mutating strategic state.

**Context and Memory**

- Builds typed context packs for assumption extraction, Ask Thesys, agentic research, opportunity briefs, competitor analysis, validation planning, validation-result interpretation, and decision recommendation.
- Uses explicit workflow profiles so each path has an inspectable token budget, expected context item types, selected memory, dropped-context explanations, citation IDs, and untrusted-content rules.
- Stores typed memory items for semantic, episodic, procedural, preference, working, and project memory.
- Selects memory by workflow so each AI path receives relevant context without turning the whole database into a prompt.
- Supports approval-gated preference memory, compacted memory proposals, stale/archive behavior, conflict detection/resolution, and recommendation-to-memory provenance links.
- Exposes hidden-by-default memory and context diagnostics in Inspect, plus `/evals/context` and `scripts/eval_ai_quality.py --json` checks.

**Tool Governance and MCP**

- Defines read, proposal, and write tools with schemas, risk levels, and approval policies.
- Exposes the same governed tool boundary through MCP JSON-RPC at `/api/mcp/rpc` and `/api/mcp/projects/{project_id}/rpc`.
- Keeps compatibility routes at `/api/mcp/tools` and `/api/mcp/projects/{project_id}/tools/{tool_name}/call`.
- Logs MCP-originated tool calls and preserves approval gates for proposal tools.

**Source and Competitor Discovery**

- Turns research plans into source and competitor candidates.
- Uses deterministic discovery by default, optional Tavily search for live source discovery, candidate review before ingestion, and competitor merge workflows.
- Stores search provider, query, rank, retrieval time, source type, and risk metadata for inspection.

**Validation and Decision Support**

- Extracts assumptions and risks, creates validation assets, interprets validation results, and suggests proceed / pivot / pause / kill / continue-research decisions.
- Uses structured outputs where judgment is needed and deterministic decision rules where reproducible product behavior is more important than open-ended generation.

**Observability, Safety, and UX**

- Stores local AI runs and steps even when LangSmith is disabled.
- Exposes cost, tokens, model provider, trace IDs, retrieval context summaries, and quality proxies in workflow details and inspect surfaces.
- Keeps the homepage and main project workflow focused on "what should I do next?" while allowing deeper traces and diagnostics through details panels.

---

## Security and Governance

Thesys uses a project role model to keep autonomous research bounded:
`owner`, `admin`, `editor`, and `viewer`.

- View project: owner, admin, editor, viewer
- Run research: owner, admin, editor
- Approve memory updates: owner, admin, editor
- Approve high-risk tools: owner, admin
- Record decisions: owner, admin, editor
- Delete project: owner only

Tool calls are classified as read, proposal, or write actions with low, medium,
or high risk. High-risk proposals and project memory updates require human
approval before project state is accepted. Denied tool actions fail closed and
are written to the audit log.

Tool schemas are enforced at runtime. Guard checks validate the requesting
actor, accepted input fields, bounded payload sizes, output shape, and
research-sprint scope before any tool logic runs.

Sprint 54 adds a production-security shape around expensive AI workflows:
per-user and per-workspace rate limits, max concurrent workflow guards, pre-call
token/cost budget checks, provider-egress allowlists, JWT/API-key auth modes,
stricter dev-auth isolation, URL fetch domain/port/content-type policy, and
formal threat-model documentation.

The API persists governance events and generic approval requests for research
plans, memory updates, tool invocations, validation plans, and decisions. The
project workspace includes a governance approval queue with pending summaries,
risk level, proposed state changes, approve/reject actions, and recent audit
events.

All retrieved content in agent prompts is treated as untrusted evidence, not
instruction. Retrieved evidence is wrapped in
`<untrusted_retrieved_content>` blocks before synthesis prompts consume it.
Audit logs, tool payloads, workflow records, LangSmith metadata, and UI-facing
errors pass through secret redaction for API keys, bearer tokens, JWT-like
tokens, sensitive key names, secret values, and emails.

In local dev auth, `X-Dev-User-Role` can be set to one of `owner`, `admin`,
`editor`, or `viewer` to exercise governance behavior. Dev auth is rejected
outside `APP_ENV=local`. `AUTH_MODE=oidc` verifies asymmetric bearer tokens
against a fixed algorithm allowlist and JWKS, then resolves a pre-provisioned
active user, exact workspace membership, and stored role into a `Principal`.
`AUTH_MODE=jwt` remains a shared-secret demo path, and `AUTH_MODE=api_key`
verifies hashed service-account API keys for integration-style access. JWT key
IDs, revoked JWT IDs, and revoked API-key
hashes are configurable to model rotation and revocation behavior.

Authenticated principals are also bound to transaction-local Postgres settings.
Forced row-level security covers every currently modeled tenant table, including
child/link tables that inherit workspace scope. The API, Temporal worker,
migration process, and readonly access use separate non-superuser database roles;
application-level workspace predicates remain in place as defense in depth.

Secret access is environment-gated: local development uses the environment
provider, while staging and production require Vault or a cloud secret manager.
Application credential consumers resolve closed, named secrets at the point of
use. Restricted reversible fields can use AES-256-GCM envelope encryption with
a random per-workspace data key; only the externally wrapped data key is stored,
and its table is protected by the same forced RLS boundary.

Evidence objects use workspace/project/source-scoped keys. Hosted deployments
must use HTTPS S3-compatible storage and verify private access, bucket-owner
enforcement, server-side AES256/KMS encryption, retention, and an insecure-
transport deny policy before completing storage operations. Downloads are
authorized before short-lived presigning and use explicit safe response headers;
object writes, download grants/denials, and deletions are audited without
persisting signed URLs or raw storage keys.

The API is stateless and uses authorization headers rather than browser cookies.
Its CORS policy therefore does not enable browser credentials. API responses
carry a restrictive CSP with frame denial, `nosniff`, no-referrer and permissions
policies, and production HSTS. A future cookie-based session flow must add
secure/HttpOnly/SameSite settings, rotation, revocation, and CSRF protection.

---

## Architecture Overview

```text
Frontend
  ↓
API Layer
  ↓
Project Memory / Domain Model
  ↓
Research Sprint Orchestrator
  ↓
Source Discovery / Competitor Discovery
  ↓
Evidence Ingestion Pipeline
  ↓
Retrieval Layer
  ↓
LLM Gateway / Model Abstraction
  ↓
Cited Synthesis / Critique / Memory Update
```

---

## Core System Layers

### 1. Web UI

The frontend provides a guided project workspace with tabs for:

- Overview
- Research
- Evidence
- Competitors
- Assumptions
- Validation
- Decisions

The UX is verdict-first: users see the current recommendation and next best action before digging into evidence or process details.

---

### 2. API Layer

The backend exposes project and workflow APIs for:

- project lifecycle state
- research sprint execution
- source discovery
- competitor discovery
- evidence ingestion
- artifact generation
- assumption scoring
- validation planning
- decision recording

---

### 3. Agentic Research Workflow

The research workflow is designed as a multi-step agentic RAG process.

```text
Research Planner
→ Source Discovery
→ Competitor Discovery
→ Evidence Ingestion
→ Retrieval
→ Gap Detection
→ Synthesis
→ Critique
→ Human Approval
→ Project Memory Update
```

The system does not blindly update strategic state. Major updates can be reviewed before being committed to project memory.

---

### 4. Retrieval Layer

The retrieval system supports evidence-grounded generation.

Core responsibilities:

- ingest source content
- extract text
- chunk documents
- generate embeddings
- store source metadata
- plan retrieval queries and subqueries
- retrieve relevant evidence with semantic, keyword, metadata, freshness, and credibility signals
- rerank candidates with deterministic local behavior or optional LiteLLM mode
- assemble bounded context with dedupe, source diversity, score thresholds, and citation IDs
- link claims to sources
- surface open questions when evidence is weak
- expose retrieval quality diagnostics in Inspect and workflow trace views

---

### 5. Persistent Strategic Memory

The app models strategy as durable state, not chat history.

Key entities include:

```text
Project
Thesis
EvidenceSource
EvidenceChunk
Finding
OpenQuestion
Competitor
Assumption
ValidationPlan
ExperimentResult
Decision
StrategicUpdate
ResearchSprint
ResearchMemo
```

---

## How to Navigate the Project

The repository is a monorepo. The fastest way to understand it is to start with
the domain workflow, then follow the AI services behind each step.

| Area | Path | What to look for |
|---|---|---|
| API entrypoints | `apps/api/app/routers/` | FastAPI routes for projects, evidence, research sprints, guide chat, tools, workflows, evals, and governance. |
| Feature packages | `apps/api/app/features/` | Sprint 59 feature-owned modules. Evidence extraction/provenance/citations, retrieval planning/reranking/context selection, validation generation/result interpretation, research planning/memo rendering/prompting/citation-audit/source-discovery shaping, guide routing/streaming/citations/context projection/prompt assembly, memory context-pack/Inspect serialization, decision recommendation shaping, governed tool guards, MCP protocol serialization, eval report file readers/writers/summary/failure-payload shaping, research eval case loading/scoring, shared eval metric-record helpers, and eval observability metric assembly live here behind compatibility shims. |
| Shared backend utilities | `apps/api/app/common/` | Cross-feature helpers that are not owned by the service layer, such as metadata merging. |
| AI service layer | `apps/api/app/services/` | The main AI/product behavior: retrieval, embeddings, source discovery, agentic research, guide chat, validation, governance, and observability. |
| LLM helpers | `apps/api/app/ai/` | LiteLLM client, structured-output validation/repair, prompt versions, fallback policy, deterministic fallback completion metadata, and shared prompt-safety rules. |
| Domain models | `apps/api/app/db/models/` | SQLAlchemy models for project memory, evidence, artifacts, claims, tools, approvals, AI runs, and research workflow state. |
| Schemas | `apps/api/app/schemas/` | Pydantic request/response contracts and structured AI output shapes. |
| Durable workflows | `apps/api/app/temporal/` | Temporal workflow and activities for long-running research sprints. |
| Web app | `apps/web/src/` | Next.js app shell, project workspace screens, guide panel, evidence UI, workflow traces, and typed API client. |
| Implementation docs | `IMPLEMENTATION_BRIEF.md` | Product/engineering sprint plan and implementation notes. |
| Status docs | `IMPLEMENTATION_STATUS.md` | What has been implemented and verified so far. |

Useful codepaths for AI reviewers:

- Agentic research graph: `apps/api/app/services/agentic_research_service.py`
- Research sprint planning prompts/fallbacks: `apps/api/app/features/research/planning.py`
- Research memo rendering: `apps/api/app/features/research/memo_rendering.py`
- Research memo prompt assembly: `apps/api/app/features/research/memo_prompting.py`
- Research citation audit shaping: `apps/api/app/features/research/citation_audit.py`
- Retrieval pipeline: `apps/api/app/services/retrieval_service.py`
- Embedding provider boundary: `apps/api/app/services/embedding_service.py`
- Context packs: `apps/api/app/services/context_service.py`
- Typed memory: `apps/api/app/services/memory_service.py`
- Memory Inspect serialization: `apps/api/app/features/memory/inspection.py`
- Ask Thesys grounded guide: `apps/api/app/services/guide_service.py`
- Ask Thesys intent/action routing: `apps/api/app/features/guide/routing.py`
- Ask Thesys stage recommendations: `apps/api/app/features/guide/recommendations.py`
- Ask Thesys streaming events: `apps/api/app/features/guide/events.py`
- Ask Thesys citation drilldowns: `apps/api/app/features/guide/citations.py`
- Ask Thesys grounded answer shaping: `apps/api/app/features/guide/grounding.py`
- Ask Thesys guide eval shaping: `apps/api/app/features/guide/evals.py`
- Validation generation prompts/fallbacks:
  `apps/api/app/features/validation/generation.py`
- Validation plan rendering: `apps/api/app/features/validation/plan_rendering.py`
- Decision recommendation shaping: `apps/api/app/features/decisions/recommendation.py`
- Tool governance boundary: `apps/api/app/services/tool_service.py`
- Tool schema guards: `apps/api/app/features/governance_tools/schema_guard.py`
- MCP adapter: `apps/api/app/mcp/adapter.py`
- Source discovery and external search: `apps/api/app/services/source_discovery_service.py`
  and `apps/api/app/services/external_search_service.py`
- Evidence feature package map: `docs/BACKEND_FEATURE_PACKAGE_MAP.md`
- Source provenance and extraction:
  `apps/api/app/features/evidence/source_provenance.py` and
  `apps/api/app/features/evidence/extraction.py`
- Multimodal extraction: `apps/api/app/services/multimodal_extraction_service.py`
- Citation verification: `apps/api/app/features/evidence/citation_verifier.py`
- Retrieval planning and reranking:
  `apps/api/app/features/retrieval/planning.py` and
  `apps/api/app/features/retrieval/reranker.py`
- Retrieval diagnostics: `apps/api/app/features/retrieval/diagnostics.py`
- Eval report file readers: `apps/api/app/features/evals/report_files.py`
- Eval report writer/renderers: `apps/api/app/features/evals/report_writer.py`
- Eval report summary shaping: `apps/api/app/features/evals/report_summary.py`
- Observability/evals: `apps/api/app/services/langsmith_observability_service.py`
  and `apps/api/app/services/eval_service.py`
- Shared service utilities: `apps/api/app/services/common/`

Developer docs:

- [Repository navigation](docs/REPOSITORY_NAVIGATION.md)
- [Security contract](docs/security/THREAT_MODEL.md)
- [Data classification](docs/security/DATA_CLASSIFICATION.md)
- [Security control matrix](docs/security/CONTROL_MATRIX.md)
- [Security architecture](docs/security/SECURITY_ARCHITECTURE.md)
- [Security abuse cases](docs/security/ABUSE_CASES.md)
- [AI architecture](docs/AI_ARCHITECTURE.md)
- [Context engineering](docs/CONTEXT_ENGINEERING.md)
- [Memory system](docs/MEMORY_SYSTEM.md)
- [MCP integration](docs/MCP_INTEGRATION.md)
- [Retrieval and citations](docs/RETRIEVAL_AND_CITATIONS.md)
- [Ask Thesys streaming](docs/ASK_THESYS_STREAMING.md)
- [Evals and observability](docs/EVALS_AND_OBSERVABILITY.md)
- [Source intelligence](docs/SOURCE_INTELLIGENCE.md)
- [Deployment and security](docs/DEPLOYMENT_SECURITY.md)
- [Retrieval pipeline](docs/RETRIEVAL_PIPELINE.md)
- [Governance and MCP](docs/GOVERNANCE_AND_MCP.md)
- [Memory model](docs/MEMORY_MODEL.md)
- [Security and evals](docs/SECURITY_AND_EVALS.md)

---

## Example Agentic Research Sprint

Given this idea:

```text
An AI assistant for independent fitness coaches that helps them manage client programming, check-ins, and workout adjustments.
```

Thesys can produce:

```text
Verdict:
Do not build a generic fitness AI assistant yet. Validate whether independent coaches will pay for workflow automation around check-ins and client adherence.

Best wedge:
Client check-in summarization and program adjustment support for solo online coaches.

Top competitors/substitutes:
Trainerize, TrueCoach, Google Sheets, manual WhatsApp/Instagram check-ins, ChatGPT.

Riskiest assumption:
Independent coaches will pay for a dedicated AI workflow instead of continuing manual client management.

First validation test:
Interview 5–10 independent coaches and test willingness to pay for automated check-in summarization.
```

---

## Tech Stack

### Frontend

- Next.js
- TypeScript
- Tailwind CSS or equivalent styling system

### Backend

- FastAPI
- Python
- PostgreSQL
- pgvector

### AI / Orchestration

- LangGraph stateful workflow orchestration
- LiteLLM Proxy model gateway
- Pydantic structured outputs
- LangSmith tracing
- Temporal durable workflows
- pgvector-backed evidence storage
- deterministic local embeddings for tests/offline demos
- provider-backed embeddings and pgvector SQL retrieval for live mode

### Infrastructure

- Docker
- Docker Compose
- Environment-based configuration

---

## Local Development

### Prerequisites

- Node.js
- Python 3.11+
- Docker
- Docker Compose
- PostgreSQL with pgvector support
- Optional LLM provider API key for live mode

---

### 1. Clone the Repository

```bash
git clone <github-url>
cd thesys
```

---

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Example environment variables:

```bash
# Application
APP_ENV=local
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# Database
DATABASE_RUNTIME_ROLE=api
DATABASE_URL=postgresql+psycopg://thesys_api:thesys-api-local@localhost:5432/thesys
MIGRATION_DATABASE_URL=postgresql+psycopg://thesys_migration:thesys-migration-local@localhost:5432/thesys

# LLM / Model Gateway
LLM_STUB_MODE=always
LITELLM_MODEL=dev-local-qwen
LITELLM_API_KEY=sk-local-dev
OPENAI_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=

# Embeddings
EMBEDDING_PROVIDER=deterministic
EMBEDDING_MODEL=deterministic-hash-embedding-1536
EMBEDDING_DIMENSION=1536
EMBEDDING_VERSION=v1
AI_EMBEDDING_CACHE_ENABLED=true
AI_RETRIEVAL_CACHE_ENABLED=true
AI_RERANK_CACHE_ENABLED=true
AI_SEMANTIC_ANSWER_CACHE_ENABLED=false
AI_SEMANTIC_ANSWER_CACHE_LIVE_ENABLED=false
RETRIEVAL_VECTOR_PATH=auto
RETRIEVAL_PYTHON_FALLBACK_ENABLED=true
RETRIEVAL_RERANKING_ENABLED=true
RETRIEVAL_RERANKER_PROVIDER=deterministic
RETRIEVAL_CONTEXT_TOKEN_BUDGET=3500
RETRIEVAL_MAX_CHUNKS_PER_SOURCE=2
RETRIEVAL_MIN_CONTEXT_SCORE=0.15

# External search and multimodal extraction
EXTERNAL_SEARCH_ENABLED=false
EXTERNAL_SEARCH_PROVIDER=deterministic
TAVILY_API_KEY=
MULTIMODAL_EXTRACTION_PROVIDER=deterministic
MULTIMODAL_EXTRACTION_MODEL=dev-gpt-4o-mini
MULTIMODAL_PDF_FALLBACK_ENABLED=false

# Optional LangSmith observability
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=thesys-local
LANGSMITH_PUBLIC_URL_BASE=https://smith.langchain.com
```

---

For live provider-backed embeddings through LiteLLM, set:

```bash
EMBEDDING_PROVIDER=litellm
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
EMBEDDING_VERSION=openai-text-embedding-3-small-v1
OPENAI_API_KEY=<real provider key>
```

After changing embedding provider, model, dimension, or version, re-embed existing project evidence:

```bash
curl -X POST http://localhost:8000/api/projects/<project_id>/evidence/reembed \
  -H "Content-Type: application/json" \
  -d '{"dry_run":true,"scope":"project"}'

curl -X POST http://localhost:8000/api/projects/<project_id>/evidence/reembed \
  -H "Content-Type: application/json" \
  -d '{"dry_run":false,"scope":"project"}'
```

Retrieval diagnostics are returned by evidence search and stored in workflow
steps or artifact structured content for brief generation and agentic research.
They include the query plan, subquery count, reranker status, context token
budget and selected chunk count, dedupe and drop counts, citation coverage,
precision and recall proxies, latency, and reranker usage. These details are
intended for Inspect and trace views so the main project UI stays compact.

External source discovery is also deterministic by default. To use live Tavily
search, set `EXTERNAL_SEARCH_ENABLED=true`, `EXTERNAL_SEARCH_PROVIDER=tavily`,
and `TAVILY_API_KEY`. Search results become review candidates with provenance;
they are not ingested into evidence until a user approves them.

Image uploads and low-text PDF fallback use the multimodal extraction provider.
Local tests and demos use `MULTIMODAL_EXTRACTION_PROVIDER=deterministic`; live
extraction uses LiteLLM by setting `MULTIMODAL_EXTRACTION_PROVIDER=litellm` and
choosing a multimodal-capable `MULTIMODAL_EXTRACTION_MODEL`.

### 3. Start Infrastructure

```bash
docker compose up -d
```

---

### 4. Install Backend Dependencies

```bash
cd apps/api
uv sync
```

If you are not using `uv`, create a virtual environment and install from the
project metadata:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

### 5. Run Backend

```bash
cd apps/api
uvicorn app.main:app --reload --port 8000
```

---

### 6. Install Frontend Dependencies

```bash
pnpm install
```

---

### 7. Run Frontend

```bash
pnpm --filter thesys-web dev
```

Open:

```text
http://localhost:3000
```

---

## Observability and Evals

Thesys stores local trace IDs for research sprints, AI runs, workflow steps, and
major generated artifact versions even when external tracing is disabled. To
send traces to LangSmith, set:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=thesys-local
```

The research workflow records spans for planning, source discovery, competitor
discovery, retrieval, synthesis, critique, memo generation, assumption updates,
and validation-plan generation. Trace links are exposed in workflow details,
research history, memo review, and research quality checks.

Run the local research eval dataset checks from the repo root:

```bash
pnpm eval:research
```

Run the broader AI quality, safety, provenance, and cost gate:

```bash
pnpm eval:ai
```

Run the aggregate quality gate and local eval report generator:

```bash
pnpm eval:quality
```

This writes local JSON, Markdown, HTML, and JSONL trend artifacts under
`reports/evals/` and powers the hidden Inspect quality report surface.

To include live project metrics from a running API:

```bash
python3 scripts/eval_research_sprints.py --project-id <project-id>
python3 scripts/eval_ai_quality.py --project-id <project-id>
```

---

## Suggested Demo Flow

Use the guided demo for the fastest review path:

1. Start the local stack and open `http://localhost:3000/projects`.
2. Choose `Load guided demo`.
3. Review the Current Step first. The seeded project opens directly at
   `#current-step`.
4. Use Ask Thesys and the inspect panels to move through Thesis, Test,
   Decision, and History.
5. Inspect the seeded Thesis Canvas, recommended wedge, validation mission,
   interpreted result, Decision Coach recommendation, and thesis evolution log.

The guided demo can also be seeded through the API:

```bash
curl -X POST http://localhost:8000/api/demo/seed
```

Use this longer flow when reviewing the full workflow from scratch:

1. Create a project from a rough idea.
2. Run an autonomous research sprint.
3. Review the research result.
4. Inspect discovered sources and competitors.
5. Review supported findings and open questions.
6. Open the assumption matrix.
7. Create a validation plan for the riskiest assumption.
8. Log experiment results.
9. Record a proceed / pivot / pause / kill decision.

---

## Product Design Principles

### Verdict First

The app should answer:

```text
What should I do next?
```

before showing the user the machinery behind the recommendation.

---

### Evidence With Receipts

Every important factual finding should link back to evidence or be marked as an open question.

---

### Strategic State Over Chat

The system should model durable strategic objects rather than relying on a chat transcript.

---

### Human-in-the-Loop

The app should assist with research and synthesis, but users remain responsible for approving major strategic updates and decisions.

---

### Validate Before Building

The core workflow is designed to prevent premature building by identifying the most important assumptions to test first.

---

## Current Status

This is a V1 portfolio proof-of-concept. Sprint 41-50 established the first AI
engineering upgrade baseline; they are not treated as fully complete
production-grade work. Sprints 51-60 are the explicit gap-closure track, and the
current branch has implemented Sprints 51-60. Sprint 60 closes the carried-gap
ledger by documenting implemented work, exact verification blockers, future
owners, and V1 out-of-scope decisions for every `G41-*` through `G50-*` item.

Implemented or demonstrated:

- project lifecycle workflow
- autonomous research sprint
- source discovery
- competitor/substitute discovery
- evidence ingestion
- cited research memo generation
- assumption ranking
- validation planning
- decision recommendation
- guided UI around next best action
- provider-backed embeddings, pgvector SQL retrieval, multi-stage retrieval,
  Postgres text-search ranking, BM25-like local fallback scoring, swappable
  reranking, MMR diversity selection, retrieval-quality diagnostics, golden
  retrieval evals, and re-embedding
- LLM-grounded Ask Thesys with citations, retrieval diagnostics, bounded recent
  turns, action-card routing, true streaming events, provider answer deltas when
  supported, timeout/cancellation handling, approval-gated proposals, guide
  evals, and deterministic fallback
- optional Tavily-backed source discovery with provenance
- multimodal image extraction and low-text PDF fallback through a LiteLLM
  multimodal provider boundary, with deterministic OCR fallback metadata
- URL/upload security guards, fetched-page prompt-injection markers, source
  quality factors/explanations, canonical URL/content-hash dedupe, page/section
  quote provenance, snapshot metadata, PDF page lineage, and table extraction
- JWT/API-key production-auth shape, dev-auth isolation, expensive-workflow
  rate/concurrency limits, pre-call AI budget enforcement, live-provider egress
  allowlists, dependency/security check scripts, and a formal threat model
- unified context compiler, workflow context profiles, typed context packs,
  multiple memory types, memory proposal review, context diagnostics, and
  workflow-aware memory selection
- MCP JSON-RPC adapter and stdio bridge over the governed tool registry
- DB-backed semantic caching for embeddings, retrieval plans, rerank results, and
  optional non-streaming Ask Thesys answers with hashed keys, versioned
  invalidation, stale-cache denials, and saved token/cost/latency metrics
- AI cost accounting, provider-failure circuit checks, OpenTelemetry-compatible
  local metrics, aggregate quality gates, file-backed eval reports/trends,
  cache-quality gates, fixture-backed extraction quality checks, redacted
  optional LangSmith eval export, and hidden Inspect quality reporting
- shared service utilities, source provenance utilities, developer docs, and
  code navigation guides

Gap-closure roadmap:

`SPRINT_51_60_TODO.md` now contains the execution-level gap ledger for every
unfinished Sprint 41-50 item. It uses stable `G41-*` through `G50-*` work-item
IDs and pickup-ready Sprint 59/60 artifacts so each gap can close with
verification, be marked intentionally out of V1 scope, or receive a named future
owner. It also includes residual routing for completed Sprints 51-58, a
per-sprint residual handoff checklist directly under each completed Sprint
51-58 section, a file-level Sprint 59 cleanup punch list, and step-by-step
Sprint 60 pickup notes. The TODO now also includes an audit gap crosswalk, a
per-sprint completion-gate table, and a per-ID pickup checklist for each
`G41-*` through `G50-*` gap so future work has exact edit targets, behavioral
expectations, verification commands, blocker-recording rules, and
status-disposition requirements. It also defines a required disposition row
format covering status, owner sprint item, source/doc links, exact verification
or blocker text, future owner, and portfolio-claim impact. The audit crosswalk
is the "did we capture it?"
check: every unfinished Sprint 41-50 objective maps to a `G*` ID, a Sprint 59
or Sprint 60 pickup item, and concrete file-level directions. The list below is
the reader-friendly summary.

The TODO now also has a `Gap Capture Control` rule plus closure checklists for
Sprint 59 and Sprint 60. Those checklists spell out the exact service
entrypoints, feature-module targets, service-owned side effects, docs, README
links, status rows, verification commands, and blocker text required before a
future engineer can mark each remaining gap complete.

It also has a `Gap-Patching Rule for Completed Sprints`: Sprints 51-58 are
code-landed only. Their original Sprint 41-50 gaps stay open until the owning
`S60-P*` package patches the named doc/source artifacts, records exact commands
or blockers, updates README/navigation language when needed, and writes final
`IMPLEMENTATION_STATUS.md` rows for every related `G*` ID.

It also now includes an `Original Sprint 41-50 Gap Patch Manifest`. That
manifest is the first pickup surface for remaining work: for each partially
complete original sprint, it names the owning `S59-R*` or `S60-P*` item, first
files to open, exact docs/code artifacts to patch, commands to run, blocker text
to capture, and `IMPLEMENTATION_STATUS.md` rows required before closure.

For pickup, use the `No-Ambiguity Sprint Pickup Contract` near the top of
`SPRINT_51_60_TODO.md`. It maps each follow-up sprint to the exact original
`G41-*` through `G50-*` gaps, first files to open, required docs/code targets,
verification commands or blocker rules, and the `IMPLEMENTATION_STATUS.md`
disposition rows that must exist before a sprint can be called complete.

Completion semantics: a checked Sprint 51-58 implementation item means code has
landed, not that the original Sprint 41-50 gap is fully closed. The `G41-*`
through `G50-*` items in `SPRINT_51_60_TODO.md` are the authoritative ledger,
and each one must receive an `implemented`, `intentionally out of V1`, or
`future owner` disposition in `IMPLEMENTATION_STATUS.md` before the roadmap can
claim complete gap closure. The TODO now uses **code-landed** versus
**gap-closed** terminology and avoids checked "close gap" items for Sprints
51-58 unless the related docs, QA, provider/audit checks, blocker records, and
final status dispositions also exist.

- Sprint 53 is implemented on this branch: Ask Thesys now has incremental
  answer deltas/provider streaming support, live retrieval/tool/proposal events,
  cancellation persistence, timeouts, and collapsed citation drilldowns.
- Sprint 54 is implemented on this branch: rate limits, workflow concurrency
  limits, pre-call token/cost budget enforcement, dependency audit commands,
  JWT/API-key production auth, SSRF hardening, provider-egress controls, and
  threat modeling are in place.
- Sprint 55 is implemented on this branch: retrieval now includes Postgres text
  rank signals, BM25-like local scoring, MMR/source-domain-type-competitor caps,
  a no-op/deterministic/LiteLLM reranker adapter, claim-level citation outcomes,
  and a credential-free golden retrieval eval command.
- Sprint 56 is implemented on this branch: it closes the observability gap with
  OpenTelemetry-compatible workflow,
  model, retrieval, tool, approval, cost, cache, timeout, and egress metrics;
  one CI-ready quality-gate command; Markdown/HTML eval reports; local trend
  persistence; prompt/schema/context/retrieval/memory/tool changelogs; optional
  redacted LangSmith export; and a hidden-by-default quality report surface.
- Sprint 57 is implemented on this branch: it adds semantic caching and cost
  optimization for embeddings, retrieval plans, reranking, and optional
  non-streaming guide answers with strict project/workspace isolation, versioned
  invalidation, stale-cache denial records, and saved-token/cost/latency metrics.
- Sprint 58 is implemented on this branch: source ingestion now records
  readability/parser metadata, raw/page/screenshot snapshot metadata, OCR
  confidence/page metadata, deterministic table artifacts, normalized quote
  provenance, source-quality explanations/factors, retrieval quality weighting,
  enriched citation DTOs, collapsed Evidence/retrieval/guide/research
  provenance surfaces, and fixture-backed extraction evals with explicit
  live-provider-unavailable warnings. Remaining carry-forwards are tracked in
  `SPRINT_51_60_TODO.md`: maintained parser dependency versus deterministic
  fallback, true screenshot/page artifact storage, screenshot-region OCR/table
  provenance, live-provider credential QA, web/browser provenance QA, and
  Project Inspect trust-summary QA.
- Sprint 59 is implemented on this branch: it closes the architecture cleanup
  gap with characterization coverage, feature-owned packages, typed boundary
  ledgers, compatibility shims, duplication disposition, import-boundary checks,
  and preserved public API behavior. The pickup artifacts are concrete:
  `docs/BACKEND_FEATURE_PACKAGE_MAP.md` now contains the target package map,
  implemented characterization matrix, DTO boundary ledger, shim/migration
  ledger, implemented function-level slices for retrieval context selection and
  retrieval result fusion/scoring, validation generation/result interpretation
  fallback, citation de-duplication/retrieved-ID checks, governed tool registry
  contracts, eval gate diagnostics, command-gate result parsing/shaping, shared
  eval metric records for the AI/extraction scripts, LangSmith export
  payload/result shaping, memory selection/conflict policy, and deterministic
  fallback completion metadata. Shared eval metric records now cover the AI
  quality, extraction quality, MCP contract, and research sprint eval scripts,
  research eval case loading/scoring is feature-owned, and missing/malformed/
  unreadable report plus malformed/unreadable/unwritable trend payloads and
  live-provider-unavailable warning metrics, rerun metadata, and local metric
  export payloads are feature-owned. Typed eval boundary validation now covers
  gate results, shared metric records, report failures, LangSmith export
  results, OpenTelemetry metric points, eval-run summaries, token/cost summaries,
  and cache diagnostics; full gate execution, trend persistence, and upload
  side-effect ownership remain future cleanup. Fallback completion metadata now
  also records provider mode, fallback reason, redacted provider failure
  details, timeout/cause classification, token/cost defaults, and redacted
  trace/run metadata. Decision recommendation and decision-coach responses now
  expose typed weak-evidence labels without mutating decision state. Validation
  result interpretation now also has feature-owned mission-context projection,
  prompt payload construction, and approval proposed-update payload shaping in
  `app.features.validation.result_interpretation`; provider calls, approval
  persistence, memory writes, confidence mutation, audit persistence, DB
  commits, and route orchestration remain service-owned. Research graph step
  output serialization now lives in `app.features.research.graph_state` behind
  service aliases, deterministic research strategy helpers now live in
  `app.features.research.strategy`, and final memo prompt assembly now lives in
  `app.features.research.memo_prompting` with trusted/untrusted context
  splitting and untrusted retrieved-content wrapping. Memo citation-audit
  shaping now lives in `app.features.research.citation_audit` with claim
  support downgrades, finding-level citation filtering, citation enrichment,
  and citation de-duplication. Research sprint planning prompt/fallback shaping
  now lives in `app.features.research.planning`, source-discovery prompt
  payloads now live in `app.features.research.source_discovery` alongside
  candidate specs and provenance shaping, and research memo proposal payloads
  now live in `app.features.research.proposals`; LangGraph execution,
  context-pack construction, tracing, persistence, tool/retrieval execution,
  provider calls, structured-output parsing, external-search execution, tool
  proposal/approval writes, claim/artifact/plan/sprint writes, evidence
  ingestion, Temporal signaling, and DB writes remain service-owned.
  Ask Thesys guide context projection and grounded prompt assembly now live in
  `app.features.guide.context_projection` and `app.features.guide.prompting`,
  covering recent-turn bounding, risk/unknown projection, overview-to-context
  shaping, trusted/untrusted context splitting, and untrusted retrieved-content
  wrapping; active workflow lookup, retrieval execution, context-pack
  construction, provider generation, cache, run accounting, proposals, nudge
  persistence, approvals, and routes remain service-owned.
  `SPRINT_51_60_TODO.md` still calls out Sprint 59 must-not-miss edge cases so
  broad refactor work cannot hide unverified behavior. MCP/stdout/HTTP approval
  parity is now pinned for automated routes, including direct MCP HTTP,
  JSON-RPC, tool-invocation reads, approval-list reads, rejection transitions,
  denial audit metadata, and redacted persisted summaries; only live stdio
  read/proposal smoke remains in Sprint 60. Approval rejection/audit payloads,
  context compression/conflict/Inspect serialization, and route contract parity
  are now pinned by focused tests, with memory review metadata shaped in
  `app.features.memory.review`. Evidence extraction metadata ownership now also
  covers direct URL response metadata, file identity metadata, image upload
  metadata, text upload metadata, PDF parser metadata, and OCR fallback
  metadata in `app.features.evidence.extraction`, while fetch/storage/parser/
  provider/embedding/audit/transaction orchestration remains service-owned.
- Sprint 60 is implemented on this branch: it closes the documentation/readiness
  gap with source-linked architecture docs, post-refactor navigation, targeted
  guide-stream docstrings, deployment/security docs, object-storage and
  backup/restore guidance, advanced integration documentation, explicit
  provider/browser/audit blockers, a final carried-gap disposition table, and
  honest portfolio limits. Deferred work is not hidden: hosted smokes, live
  MCP client smokes, strict dependency audits, browser QA, live Tavily/multimodal
  QA, and screenshot/page artifact productization are marked as future-owner or
  out-of-V1 rows in `IMPLEMENTATION_STATUS.md`.

---

## Roadmap

### V1: Autonomous Research and Validation Copilot (current)

Core promise:

> Give me a rough idea, and I’ll investigate the market, identify competitors, gather evidence, and tell me what to validate next.

Key capabilities:

- autonomous research sprint
- source discovery
- competitor discovery
- evidence ingestion
- agentic RAG synthesis
- assumption extraction
- validation plan generation
- decision recommendations

---

### V2: Living Strategic Intelligence Platform

Core promise:

> Continuously track strategic evidence, monitor changes, help teams make decisions, and manage portfolios of opportunities over time.

Potential capabilities:

- recurring watchlists
- market monitoring
- strategic alerts
- team workspaces
- collaboration
- portfolio comparison
- integrations
- advanced evals
- workflow packs for consultants, PMs, investors, and innovation teams

---

## Tool Boundary and MCP Adapter

Thesys exposes project capabilities through explicit tool contracts. Tools define
input/output schemas, access modes, risk levels, and approval policies.

Read tools allow agents to inspect project context. Proposal tools allow agents
to suggest changes, but final state mutation requires human approval. This
creates a safer boundary between model reasoning and application state.

The MCP adapter wraps the same governed tools through project-scoped JSON-RPC so
external developer agents can inspect project state and propose changes without
bypassing project permissions, approval gates, or audit logging. Legacy
HTTP-shaped MCP routes remain available for simple local clients.

The local API exposes:

```bash
curl http://localhost:8000/api/tools
curl http://localhost:8000/api/mcp/tools
curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"tools","method":"tools/list","params":{"includeProposals":false}}'
curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"call","method":"tools/call","params":{"name":"get_project_summary","arguments":{},"_meta":{"client_id":"local-agent"}}}'
curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/tools/search_project_evidence/call \
  -H "Content-Type: application/json" \
  -d '{"client_id":"local-agent","arguments":{"query":"pricing risk","mode":"hybrid","top_k":5}}'
curl http://localhost:8000/api/projects/<project_id>/tool-invocations
curl http://localhost:8000/api/projects/<project_id>/tool-invocations?research_sprint_id=<sprint_id>
```

For local stdio-based clients, run:

```bash
python3 scripts/mcp_stdio_server.py --api-base http://localhost:8000 --project-id <project_id>
```

The live MCP contract harness is:

```bash
python3 scripts/eval_mcp_contract.py --project-id <project_id> --json
```

Project pages also include a secondary Tool Activity panel in the evidence
review workspace.

## Durable Workflow Orchestration

Thesys uses Temporal to coordinate long-running research sprints. Temporal owns
durable execution, retries, timeouts, failure recovery, and approval waits.

LangGraph remains responsible for agent reasoning and synthesis. External side
effects such as source fetching, embeddings, LLM calls, eval checks, and
persistence are modeled as Temporal Activities.

The local stack includes:

- `temporal`: Temporal server
- `temporal-worker`: research sprint workflow worker
- `api`: starts or signals durable workflows through project endpoints

Useful local checks:

```bash
docker compose ps temporal temporal-worker api
curl http://localhost:8000/api/projects/<project_id>/research-sprints/<sprint_id>/durable/status
curl -X POST http://localhost:8000/api/projects/<project_id>/research-sprints/<sprint_id>/durable/start
curl -X POST http://localhost:8000/api/projects/<project_id>/research-sprints/<sprint_id>/durable/retry
curl -X POST http://localhost:8000/api/projects/<project_id>/research-sprints/<sprint_id>/durable/cancel
```

---

## Lessons Learned

This project explores several product and engineering lessons:

1. **AI product value comes from workflow, not just generation.**
   A generic AI answer is easy to produce. A persistent, stateful workflow is harder and more valuable.

2. **RAG needs UX.**
   It is not enough to retrieve sources. Users need to understand what the evidence supports, what remains uncertain, and what action follows.

3. **Agentic systems need constraints.**
   Human approval, inspectable steps, and source traceability are essential for trust.

4. **Strategic products need opinionated outputs.**
   Users do not only need summaries. They need judgment, tradeoffs, and next actions.

5. **Memory should be domain-specific.**
   Long-lived state should model the real workflow: thesis, evidence, assumptions, experiments, and decisions.

---

## Portfolio Notes

This project was built to demonstrate AI systems and product engineering skills relevant to modern AI software roles:

- full-stack AI application architecture
- agentic RAG workflow design
- retrieval-grounded generation
- persistent memory modeling
- human-in-the-loop AI workflows
- evidence-backed UX
- product-oriented AI system design
- workflow orchestration
- stateful decision support

---

## License

This project is currently provided for portfolio and educational purposes.

---

## Author

Built by Cameron Gable.

- GitHub: https://github.com/camerongable
- LinkedIn: https://www.linkedin.com/in/cameron-gable
