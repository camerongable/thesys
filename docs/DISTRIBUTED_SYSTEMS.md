# Distributed Systems And Durable Execution

Thesys is primarily a web application, but several workflows are distributed:
an API process, PostgreSQL, a Temporal worker, optional Redis, object storage,
and external AI/search providers do not share memory or fail together. This
guide explains the mechanisms the repository actually uses to handle that
reality. It does not claim multi-region deployment, exactly-once delivery, or
automatic disaster recovery.

## Runtime Model

```text
browser
  -> FastAPI request process
     -> PostgreSQL: durable product, approval, audit, and workflow state
     -> Temporal: long-running workflow history and signals
        -> worker activities: service-layer work and external calls
     -> optional Redis: hosted rate-limit coordination
     -> object storage / model / search providers: bounded external effects
```

The request path handles bounded, interactive work. A research sprint moves to
Temporal so it can outlive a request, wait for a human decision, and resume
after a worker restart. The application database remains the durable source of
truth for product state; Temporal coordinates workflow progress around it.

## Concepts Applied Here

| Concept | How Thesys applies it | Source of truth | Important boundary |
|---|---|---|---|
| Request correlation | Middleware accepts only a canonical UUID or creates one, returns it as `X-Request-ID`, and attaches it to telemetry and audit work. | [Request correlation middleware](../apps/api/app/core/request_correlation.py) | A correlation ID aids investigation; it is not an authorization credential. |
| Durable orchestration | Research sprints, retention cleanup, and workflow-timeout reconciliation are Temporal workflows. | [Temporal workflows](../apps/api/app/temporal/workflows.py) | The workflow engine coordinates progress; business records remain in PostgreSQL. |
| Pause and resume | Research plans and memory updates wait for approval signals instead of holding an HTTP request open. | [ResearchSprintWorkflow](../apps/api/app/temporal/workflows.py) | A signal changes workflow progress only after the corresponding deterministic approval path permits it. |
| Retried work | Activities have start-to-close timeouts and a bounded retry policy: up to three attempts with backoff from 2 to 30 seconds. | [Activity policy](../apps/api/app/temporal/workflows.py) | An activity can be retried; external effects must be designed as repeat-safe. |
| Transactional coordination | Security-budget changes lock the research-sprint row; audit-chain writes use a workspace advisory transaction lock. | [Workflow budget service](../apps/api/app/services/workflow_budget_service.py), [governance service](../apps/api/app/services/governance_service.py) | Database locks protect one database transaction, not an arbitrary external provider call. |
| Tenant propagation | Activities rebuild an authenticated workspace/user context before calling services and bind it to the database transaction. | [Temporal activities](../apps/api/app/temporal/activities.py), [tenant context](../apps/api/app/db/tenant.py) | A worker has no implicit browser request identity. Missing or inactive identity fails the activity. |
| Distributed rate limiting | Hosted configurations require Redis-backed limits; local/test configurations may use an in-memory limiter. | [application settings](../apps/api/app/core/config.py) | In-memory limits do not coordinate multiple application instances. |
| Resource budgets | A durable snapshot limits model calls, tool calls, retrieval, tokens, cost, duration, repairs, and loop patterns. | [budget contract](../apps/api/app/security/workflow_budget.py), [budget enforcement](../apps/api/app/services/workflow_budget_service.py) | A budget denial stops further governed work; it does not recover provider money already spent. |
| Reconciliation | A scheduled Temporal workflow finds runs that exceeded their durable duration and records a terminal result. | [timeout reconciliation](../apps/api/app/temporal/activities.py) | Reconciliation is a repair path for elapsed time, not a replacement for activity timeouts. |
| Audit and traces | Request, workflow, approval, policy, and security records expose redacted correlation identifiers and outcomes. | [security events](../apps/api/app/services/security_event_service.py), [audit chain](../apps/api/app/services/audit_chain_service.py) | Observability is evidence, not a mechanism that makes a failed operation succeed. |

## Research Sprint Lifecycle

```text
HTTP start request
  -> validate actor, tenant, policy, rate limit, and durable budget
  -> persist sprint and Temporal workflow ID
  -> Temporal workflow creates plan and waits for approval signal
  -> retryable activities discover, ingest, embed, and run research
  -> workflow creates memory proposals and waits for approval signal
  -> deterministic service persists only the approved/rejected result
  -> workflow records a terminal sprint status
```

This is intentionally different from a background thread. The workflow history
and activity boundaries make waits, retries, cancellation, and worker recovery
explicit. LangGraph owns the bounded reasoning sequence inside research work;
Temporal owns long-running coordination. See [AI Architecture](AI_ARCHITECTURE.md)
for that split.

## Failure Semantics

| Situation | Expected behavior | Why it matters |
|---|---|---|
| HTTP process restarts | The original request may fail, but a started Temporal workflow can continue once a worker is available. | Product work is not tied to one request process. |
| Worker activity fails transiently | Temporal retries within its policy and timeout. | Retries cover selected transient failures without unbounded work. |
| Approval is absent | The workflow remains waiting; it does not infer approval. | Human control is durable state, not a UI convention. |
| Workflow exceeds its duration budget | Reconciliation records an exhausted terminal state and prevents further work. | A stalled process cannot consume resources indefinitely. |
| Budget, policy, tenant, or provider decision is missing | The privileged action is denied. | Distributed uncertainty must not become elevated access. |
| External provider is unavailable | The feature returns a bounded failure or approved deterministic fallback, depending on the call path. | Provider availability does not authorize bypassing governance. |
| Two requests compete for a protected mutable record | The relevant service uses database row/advisory locking where implemented. | Locking preserves local data invariants under concurrency. |

## Idempotency And Side Effects

Temporal can retry activities, so code cannot assume that an activity body runs
only once. Thesys persists workflow IDs, approval state, budget usage, and
terminal sprint status, and uses database locks for selected sensitive updates.
Tool definitions also carry idempotency policy where a side effect requires it;
the governed tool boundary is [tool service](../apps/api/app/services/tool_service.py).

This is not a claim of global exactly-once execution. The repository does not
implement a general transactional outbox or a universal idempotency-key system
for every external provider. New external write integrations must specify their
retry behavior, provider idempotency mechanism, reconciliation path, and
compensating action before being enabled.

## Operational Boundaries

| Environment | Coordination posture |
|---|---|
| Local deterministic demo | Docker-backed dependencies and local/test adapters can make execution repeatable; process-local limits are acceptable for one developer. |
| Pull-request CI | Contract tests verify orchestration, budgets, policies, and state transitions without depending on a long-lived hosted topology. |
| Hosted deployment | Redis-backed limits, TLS for Temporal/state stores, managed PostgreSQL, secret management, backups, and worker operations are required operational work. |

See [Deployment And Security](DEPLOYMENT_SECURITY.md) for the configuration
requirements and [Security Architecture](security/SECURITY_ARCHITECTURE.md) for
the trust boundaries that apply to each cross-process call.

## What To Update With A New Distributed Path

When adding a worker, queue, provider call, scheduled job, or durable workflow,
document: the durable state owner; identity/tenant propagation; timeout and
retry policy; idempotency or reconciliation strategy; budget/rate-limit policy;
audit/correlation fields; and the exact local, CI, and hosted verification.

