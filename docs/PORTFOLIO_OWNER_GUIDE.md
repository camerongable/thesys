# Portfolio Owner Guide

## Purpose

This is the short, owner-facing guide to Thesys. It is not a substitute for the
implementation or the detailed security documentation. It gives you a coherent
way to explain what the product does, how its important paths work, what runs in
each environment, and what remains deployment work.

Start here, then use [Repository Navigation](REPOSITORY_NAVIGATION.md) to trace
the relevant code and the focused documents for deeper detail.

## Two-Minute Explanation

Thesys is an evidence-backed idea-validation workspace for founders and
builders. A user starts with a rough business idea. Thesys plans and runs
research, discovers and ingests sources, produces a cited research memo, turns
uncertainty into ranked assumptions and validation plans, and records a
structured decision to proceed, pivot, pause, kill, or continue research.

The central product claim is that idea validation is a stateful workflow, not a
chat. The durable objects are the thesis, evidence, sources, assumptions,
experiments, decisions, approvals, and research runs. A model can reason and
propose, but deterministic application services own authorization, data access,
policy decisions, persistent state changes, memory writes, tool execution, and
audit records.

## System Map

```text
Next.js workspace
  -> FastAPI routes and authorization
    -> product services and typed schemas
      -> governed tools, retrieval, and model gateway
        -> PostgreSQL/pgvector, object storage, Temporal, model/search providers
      -> approvals, audit events, and security telemetry
```

The web application presents the project lifecycle. FastAPI owns request
validation and orchestration. Services implement product behavior. PostgreSQL
holds durable strategic state and, in hosted mode, enforces tenant isolation.
Temporal makes research work durable across retries and approval waits. External
models and search providers are treated as bounded dependencies rather than as
the authority for application state.

## Five Flows To Know

### 1. Research Sprint

```text
rough idea
  -> research plan proposal
  -> human approval
  -> source and competitor discovery
  -> secure evidence ingestion
  -> project-scoped retrieval
  -> cited synthesis and critique
  -> reviewable memory/validation/decision proposals
  -> human approval before durable strategic changes
```

The important distinction is between generation and commitment. The agent can
propose work, but high-impact strategic state changes travel through governed
tools and approval records. Start tracing this flow in
`apps/api/app/services/agentic_research_service.py`,
`apps/api/app/services/research_sprint_service.py`, and
`apps/api/app/temporal/workflows.py`.

### 2. Evidence Ingestion And Retrieval

```text
source or upload
  -> extension/MIME/content validation
  -> scan and document preflight
  -> PII classification and redaction
  -> quarantine or approved source metadata
  -> sanitized chunks and embeddings
  -> tenant-scoped retrieval, reranking, context selection, citations
```

This prevents raw or unsafe content from becoming automatically trusted context.
Evidence can be quarantined, revoked, expired, or excluded from retrieval.
Primary entry points are `apps/api/app/services/evidence_service.py`,
`apps/api/app/services/data_protection_service.py`,
`apps/api/app/services/retrieval_service.py`, and the `app/features/evidence`
and `app/features/retrieval` packages.

### 3. Ask Thesys

```text
user question
  -> authorization and project scope
  -> guardrail and provider-data policy
  -> project context plus eligible retrieved evidence
  -> structured, grounded answer with citations
  -> streamed UI response and AI-run/audit metadata
```

Ask Thesys is not a free-form global chat. Its answer is scoped to a project,
uses bounded evidence/context, and can surface uncertainty rather than inventing
support. Trace it through `apps/api/app/services/guide_service.py` and
`apps/web/src/features/projects/guide-panel.tsx`.

### 4. Memory And Approval

```text
agent or user proposes a memory change
  -> provenance, classification, and policy checks
  -> proposal/approval record for governed changes
  -> accepted durable memory with source links and expiry
  -> recall only when the item remains eligible
```

This keeps untrusted retrieved text or a model response from silently becoming a
permanent rule. Start with `apps/api/app/services/memory_service.py` and
`apps/api/app/services/tool_service.py`.

### 5. Unsafe Input Containment

```text
request, uploaded source, retrieved content, or tool description
  -> classification and trust-boundary checks
  -> block, quarantine, restrict tools/memory, or require review
  -> redacted audit/security event
  -> bounded metrics, alerts, and operator-visible status
```

Prompt injection is handled as an application-boundary problem, not a promise
that a model will never produce undesirable text. The goal is to prevent
privileged effects: cross-tenant reads, unauthorized tools, durable memory
writes, data exfiltration, and unbounded agent work. Primary entry points are
`apps/api/app/security/guardrails`, `apps/api/app/services/security_event_service.py`,
and `apps/api/app/services/workflow_budget_service.py`.

## Local, CI, And Hosted Boundaries

| Environment | What it demonstrates | What is intentionally different |
|---|---|---|
| Local development | Product workflows, deterministic AI fallbacks, focused tests, local Docker dependencies, Promptfoo, and a temporary pgvector RLS check. | Provider credentials, OIDC, cloud secrets, S3, Redis, and hosted telemetry can be disabled or replaced with local/test adapters. |
| Pull-request CI | Locked dependency installs, API/web tests, security tests, Promptfoo fast checks, static analysis, secret/dependency scanning, and SBOM generation. | It does not require a deployed Garak target or publish images. |
| Nightly/manual CI | Full deterministic Promptfoo suite, broad security tests, container/Kubernetes scans, and optionally Garak against a protected test target. | Garak requires a separate HTTPS target and is irrelevant until a safe hosted test endpoint exists. |
| Hosted deployment | Real OIDC, PostgreSQL RLS, TLS-backed Redis/Temporal/Postgres, object storage, secrets providers, OTLP, and operational controls. | These controls require deployment configuration and service credentials; source code alone cannot prove them active. |

## Evaluation Cadence

Use the evaluation path that matches the question being answered:

- During implementation, run the focused `pnpm eval:*` command for the area
  changed and inspect its report.
- For a project-specific demonstration or investigation, call the relevant
  in-app evaluation endpoint. It runs only when requested.
- On each pull request, GitHub Actions runs selected evaluation contracts and
  fast adversarial checks. This protects core behavior without imposing the
  cost of every broad evaluation on each change.
- On the scheduled/manual security workflow, GitHub Actions runs the complete
  adversarial suite, including Garak. Version tags run the release evidence
  workflow.

The exact commands, boundaries, and report locations are documented in
[Evals And Observability](EVALS_AND_OBSERVABILITY.md).

## Six-Minute Demo Narrative

1. Create or open a project and state the rough idea, target user, and problem.
2. Start a research sprint and show that it produces a structured plan rather
   than immediately mutating project state.
3. Inspect discovered evidence and citations. Explain that the product keeps
   sources, gaps, and uncertainty visible.
4. Open the memo, assumptions, and validation plan. Show how research turns into
   a testable next action rather than generic advice.
5. Record or inspect a decision with its evidence and revisit trigger.
6. Open Ask Thesys or the Security Overview. Explain grounded context, approval
   gates, and redacted operational evidence without presenting the application
   as a deployed production service.

Use deterministic local mode for a repeatable portfolio demo. Do not rely on a
paid model provider or externally fetched source being available while you are
presenting.

## Portfolio Discussion Points

| Topic | Clear explanation |
|---|---|
| Why not a chatbot? | The durable model is strategic state and workflow records, not a transcript. |
| Why RAG? | Recommendations must cite project-scoped evidence, and weak evidence should remain visible as uncertainty. |
| Why structured output? | Typed schemas let application code validate and safely persist model proposals. |
| Why human approval? | Models are useful for proposals; people retain authority over consequential state changes and tools. |
| Why deterministic local mode? | It makes tests and demos repeatable without provider credentials while preserving the same product boundaries. |
| Why durable workflows? | Research can outlive a request, retry safely, and pause for approval without losing state. |
| Why the security work? | It constrains AI capabilities at deterministic boundaries rather than treating model behavior as a security guarantee. |

## Honest Limits

- Thesys is a portfolio project, not a launched hosted service.
- Local tests validate source behavior and selected local infrastructure
  contracts; they do not prove cloud configuration, external provider behavior,
  or an organization’s incident response.
- Garak, signed-release evidence, production secrets, and branch protection are
  deployment/repository-administration work, not current portfolio-demo
  requirements.
- The implementation status is a detailed evidence ledger, not a concise
  introduction. Read [Implementation Status](../IMPLEMENTATION_STATUS.md) when
  you need exact verification history.

## How To Continue Learning The Codebase

Follow one flow at a time. Start with the route, then its service, schema/model,
tests, and UI consumer. Use the focused documents rather than reading the
implementation brief sequentially:

- [AI Architecture](AI_ARCHITECTURE.md)
- [Distributed Systems And Durable Execution](DISTRIBUTED_SYSTEMS.md)
- [Retrieval And Citations](RETRIEVAL_AND_CITATIONS.md)
- [Memory System](MEMORY_SYSTEM.md)
- [Governance And MCP](GOVERNANCE_AND_MCP.md)
- [Security Architecture](security/SECURITY_ARCHITECTURE.md)
- [Security Documentation Guide](security/README.md)
- [Dependencies And Tooling](DEPENDENCIES.md)

The goal is not to memorize every module. It is to explain the product flow,
identify the deterministic boundary that owns each consequential action, and
know where to trace that boundary in the repository.
