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

## Portfolio Discussion Points

- The AI layer is visible in the data model, not hidden behind a chat transcript.
- Retrieval records provider/model/version metadata so embedding migrations are auditable.
- Human approval is a first-class workflow state, not a UI-only confirmation.
- Local deterministic mode makes the app demoable without paid provider credentials.
- Evals check behavior that matters for AI systems: citation coverage, gap detection, governance, cost visibility, and redaction.
