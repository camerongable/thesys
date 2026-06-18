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

## AI Concepts Demonstrated

Thesys is built to show the difference between a thin LLM wrapper and a durable AI application. The AI layer is visible in the architecture, data model, workflow records, governance model, and UX.

| AI concept | How it is demonstrated in this repo | Technologies and libraries |
|---|---|---|
| Agentic RAG | Autonomous research sprints plan work, call bounded tools, retrieve evidence, detect gaps, synthesize a memo, critique citations, and wait for human approval before updating project memory. | LangGraph, FastAPI, SQLAlchemy, Temporal, internal tool registry |
| Retrieval-grounded generation | Opportunity briefs, competitor analysis, research memos, assumptions, and validation plans are generated from retrieved project evidence rather than prompt-only model knowledge. | PostgreSQL, pgvector, provider-backed embeddings, retrieval service, Pydantic schemas |
| Evidence ingestion and chunking | URLs, notes, discovered source snapshots, uploads, and PDFs are normalized into evidence sources and chunks with metadata, citation IDs, and embedding provenance. | httpx, pypdf, boto3, MinIO/S3-compatible storage, SQLAlchemy |
| Production embeddings | Evidence chunks record provider, model, dimension, version, timestamp, and errors; deterministic local mode stays available for tests, while LiteLLM-backed embeddings can be used in live mode and re-embedded after model changes. | LiteLLM-compatible embeddings API, pgvector, PostgreSQL, Alembic |
| Hybrid retrieval | Project-scoped retrieval combines SQL-level vector search, keyword overlap, and metadata filters for source type, freshness, competitors, assumptions, and research context, then returns diagnostics showing the path used. | pgvector HNSW/IVFFlat indexes, PostgreSQL, custom retrieval service |
| Structured LLM outputs | LLM responses are requested as JSON, validated against typed schemas, repaired when possible, and persisted as structured project objects. | Pydantic v2, LiteLLM-compatible chat completions, structured output helper |
| Model gateway and local fallback | Model and embedding calls go through configurable provider paths, while deterministic stub/embedding modes keep local demos and tests repeatable. | LiteLLM Proxy, httpx, Ollama, OpenAI-compatible APIs, Gemini |
| Persistent AI memory | The product stores thesis versions, evidence, artifacts, claims, assumptions, validation missions, decisions, AI runs, AI steps, tool calls, and approval requests instead of relying on chat history. | PostgreSQL, SQLAlchemy, Alembic |
| Human-in-the-loop agents | AI workflows can propose research plans, memory updates, validation plans, and decisions, but important state changes require approval. | Tool registry, approval requests, audit events, role-based project permissions |
| Prompt-injection boundaries | Retrieved content is treated as untrusted evidence, wrapped before synthesis, and prevented from acting as model instructions. | Shared prompt rules, cited synthesis prompts, secret redaction utilities |
| AI observability | AI runs and steps track model, prompt version, latency, token usage, cost, trace IDs, failures, and generated artifact provenance. | LangSmith, AI run/step tables, LiteLLM cost headers, eval service |
| Evaluation | Research sprint evals check citation coverage, unsupported claims, agentic traceability, gap detection, cost visibility, and secret redaction. | Custom eval scripts, JSON eval cases, pytest-compatible service checks |
| Durable orchestration | Long-running research sprints can survive retries, approval waits, and worker restarts through a durable workflow layer. | Temporal, Temporal Python SDK, FastAPI service layer |
| AI product UX | The UI exposes AI reasoning as current verdicts, next actions, evidence, assumptions, validation missions, decisions, traces, and Ask Thesys guidance. | Next.js, React, TanStack Query, project guide service |

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
`editor`, or `viewer` to exercise governance behavior.

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
- retrieve relevant evidence
- link claims to sources
- surface open questions when evidence is weak

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
APP_ENV=development
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# Database
DATABASE_URL=postgresql+psycopg://thesys:thesys@localhost:5432/thesys

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
RETRIEVAL_VECTOR_PATH=auto
RETRIEVAL_PYTHON_FALLBACK_ENABLED=true

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

To include live project metrics from a running API:

```bash
python3 scripts/eval_research_sprints.py --project-id <project-id>
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

This is a V1 proof-of-concept.

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
- provider-backed embeddings, pgvector SQL retrieval, retrieval diagnostics, and re-embedding

Planned future work:

- retrieval quality, reranking, query expansion, context compression, and retrieval-quality evals
- LLM-grounded Ask Thesys with citations and tool-governed proposals
- recurring market monitoring
- team collaboration
- multi-project portfolio dashboard
- integrations
- advanced evaluation dashboard
- consultant / product discovery / investor workflow packs

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

## MCP / Tool Boundary

Thesys exposes project capabilities through explicit tool contracts. Tools define
input/output schemas, access modes, risk levels, and approval policies.

Read tools allow agents to inspect project context. Proposal tools allow agents
to suggest changes, but final state mutation requires human approval. This
creates a safer boundary between model reasoning and application state.

The local API exposes:

```bash
curl http://localhost:8000/api/tools
curl http://localhost:8000/api/projects/<project_id>/tool-invocations
curl http://localhost:8000/api/projects/<project_id>/tool-invocations?research_sprint_id=<sprint_id>
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
