# Architecture

Thesys is a full-stack, stateful AI workflow application. The architecture is
designed to keep model reasoning useful while keeping authority over data,
tools, memory, and decisions in deterministic services.

```text
Next.js workspace
  -> FastAPI routes and validated Principal
    -> product services and governed tools
      -> retrieval/context/model gateway
      -> PostgreSQL/pgvector, object storage, Temporal, external providers
    -> approvals, audit chain, security events, metrics, traces
```

## Runtime Responsibilities

- **Web:** presents a guided project lifecycle and uses a typed API client; it
  does not decide authorization or persist strategic state directly.
- **API:** validates requests, resolves identity and project scope, invokes
  services, and serializes public response contracts.
- **Services:** own research, ingestion, retrieval, memory, validation,
  decision, tool, and security workflows.
- **PostgreSQL/pgvector:** stores project state, evidence, approvals, AI-run
  metadata, audit records, and embeddings. Hosted deployments enforce tenant
  isolation with forced row-level security.
- **Temporal:** makes research workflows durable across retries and approval
  waits. LangGraph owns agent reasoning inside a workflow; Temporal owns durable
  lifecycle and recovery.
- **External providers:** models, embeddings, search, storage, and telemetry
  are configuration-gated and pass through application policy boundaries.

## Architectural Principles

1. Project strategy is durable structured state, not a chat transcript.
2. Retrieved or uploaded content is evidence, not trusted instruction.
3. Models can propose; deterministic application code authorizes, validates,
   persists, budgets, and audits consequential effects.
4. Important mutations are reviewable through approval records.
5. Local deterministic behavior makes tests and demos repeatable without paid
   provider credentials; hosted integrations remain explicit configuration.

For flow diagrams and portfolio explanation, see
[Portfolio Owner Guide](PORTFOLIO_OWNER_GUIDE.md). For AI-specific design, see
[AI Architecture](AI_ARCHITECTURE.md). For security trust boundaries, see
[Security Architecture](security/SECURITY_ARCHITECTURE.md).
