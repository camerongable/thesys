# AI Architecture

Thesys is an AI workflow application, not a single chat endpoint. The application persists domain state, exposes bounded tools, retrieves project evidence, and asks models to produce typed outputs that can be inspected and approved.

## High-Level Flow

```text
project state
→ context pack
→ retrieval and governed tools
→ structured LLM output
→ citation verification
→ approval gate when state would change
→ durable project memory
→ AI run and eval records
```

## Core Patterns

| Pattern | Where it appears | Technologies |
|---|---|---|
| Agentic RAG | Research sprints use a LangGraph state machine to plan, retrieve, detect gaps, synthesize, critique, and propose memory updates. | LangGraph, FastAPI, SQLAlchemy, Temporal |
| Context engineering | Prompt context is assembled into typed context packs with token budgets, provenance, dropped-item diagnostics, and untrusted-content rules. | Pydantic, `context_service.py` |
| Multiple memory types | Project memory separates semantic, episodic, procedural, preference, working, and project memory. | SQLAlchemy, Alembic, `memory_service.py` |
| Retrieval-grounded generation | Briefs, memos, guide answers, assumptions, validation plans, and decisions use retrieved evidence and citations. | pgvector, deterministic embeddings, LiteLLM-compatible embeddings |
| Structured outputs | LLM JSON is validated against Pydantic schemas and can be repaired. | Pydantic v2, LiteLLM-compatible chat completions |
| Human-in-the-loop tools | Tools are read, proposal, or write actions. Proposal/write paths are approval-gated based on risk. | Internal tool registry, approval requests, audit events |
| MCP boundary | Governed tools are exposed through an MCP-shaped adapter without bypassing auth, approval, or audit policy. | FastAPI, `app/mcp/adapter.py` |
| Observability | AI runs and steps persist prompt versions, model metadata, latency, token/cost fields, errors, and trace IDs. | SQLAlchemy, LangSmith, eval scripts |

## AI Principles And Ownership

The model is a bounded reasoning component, not the application's control
plane. These principles explain how the AI features are intended to be read and
extended.

| Principle | Meaning in Thesys | Primary implementation |
|---|---|---|
| Models propose; services decide | A model can draft analysis or a structured proposal, but deterministic code owns identity, authorization, policy, state transitions, tool execution, memory writes, and audit. | [Security Architecture](security/SECURITY_ARCHITECTURE.md), `apps/api/app/services/` |
| Ground claims in evidence | Answers and generated artifacts use project-scoped retrieval and citations; unsupported or weak evidence remains visible as uncertainty. | [Retrieval And Citations](RETRIEVAL_AND_CITATIONS.md), `apps/api/app/services/retrieval_service.py` |
| Treat retrieved text as untrusted | Evidence may inform a response but cannot override the system/task boundary or authorize an action. | [Context Engineering](CONTEXT_ENGINEERING.md), `apps/api/app/security/guardrails/` |
| Keep context bounded and inspectable | Context packs have typed items, provenance, token budgets, drop reasons, profiles, and diagnostics. | `apps/api/app/services/context_service.py` |
| Validate every model-shaped boundary | Structured output is parsed with schemas, repaired only within a budget, and checked before it affects persistent state. | `apps/api/app/ai/`, `apps/api/app/schemas/` |
| Separate memory from chat history | Memory has type, provenance, trust, status, expiry, conflict, and approval state; it is not silently promoted from a response. | [Memory System](MEMORY_SYSTEM.md), `apps/api/app/services/memory_service.py` |
| Keep agency risk-calibrated | Tools are read, proposal, or write actions with deterministic role, scope, schema, approval, budget, and audit policy. | [Governance And MCP](GOVERNANCE_AND_MCP.md), `apps/api/app/services/tool_service.py` |
| Minimize provider disclosure | Classification and egress policy decide which provider/model may receive content; redaction runs before traces and exports. | [Security Documentation Guide](security/README.md), `apps/api/app/ai/` |
| Make quality observable | AI runs record prompt/model/version/cost metadata; focused evals, CI contracts, and adversarial suites test behavior. | [Evals And Observability](EVALS_AND_OBSERVABILITY.md) |
| Preserve deterministic local operation | Stub mode gives repeatable demos and tests without paid provider credentials while retaining the same validation boundaries. | `LLM_STUB_MODE=always`, `apps/api/app/ai/` |

## What The AI Layer May Not Do

The AI layer must not grant access, select a tenant, turn untrusted text into a
policy, invoke an unregistered tool, bypass approval, persist durable memory
without policy, or claim evidence it cannot cite. Those operations remain in
the deterministic service and security boundaries. See [Security Documentation
Guide](security/README.md) for the control families and evidence model.

## LangGraph vs Temporal

```text
LangGraph:
  agent state, planning, tool selection, synthesis, critique

Temporal:
  durable execution, retries, worker restarts, long-running approval waits

FastAPI services:
  persistence, auth, governance, retrieval, ingestion, model gateway calls
```

This split keeps model reasoning separate from durable workflow mechanics and application-side state mutation.

The distributed execution mechanics, retries, approval signals, budgets, and
failure semantics are described in [Distributed Systems And Durable
Execution](DISTRIBUTED_SYSTEMS.md).

## Portfolio Discussion Points

- The AI layer is visible in the data model, not hidden behind a chat transcript.
- Retrieval records provider/model/version metadata so embedding migrations are auditable.
- Human approval is a first-class workflow state, not a UI-only confirmation.
- Local deterministic mode makes the app demoable without paid provider credentials.
- Evals check behavior that matters for AI systems: citation coverage, gap detection, governance, cost visibility, and redaction.
- AI safety is a layered system property. Prompt classifiers help, but source
  trust, retrieval filters, schemas, approvals, budgets, and deterministic
  authorization are what constrain privileged effects.
