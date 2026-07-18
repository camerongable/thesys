# Security Architecture

## Control ownership

The LLM is never an authorization, policy, or execution authority. It may
produce analysis and proposals. Deterministic services authenticate actors,
scope tenants, classify data, authorize tools, enforce approvals and budgets,
validate state transitions, write memory, and emit audit records.

```text
Browser
  -> Authentication and tenant boundary
  -> Request and resource policy
  -> Input classification / guardrails
  -> Ingestion quarantine or tenant-scoped retrieval
  -> LLM safety gateway
  -> Tool policy or memory proposal gate
  -> Output validation / DLP
  -> Application state
  -> Audit, metrics, alerts, incident response
```

Sprints 61-68 progressively replace distributed best-effort controls with the
central gates in this target flow.

## Trust boundaries

| Boundary | Data crossing | Expected identity | Authorization decision | Classification | Encryption | Audit | Failure behavior | Threat scenarios |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Browser to API | Header auth token, project input, files, actions | OIDC principal or service account | Signature/claims, active user, exact workspace membership, stored role | Internal to restricted | Hosted TLS; CSP/frame denial, nosniff, no-referrer, permissions policy, production HSTS | Immutable token-free authentication outcomes plus governed actions | Reject unauthenticated, invalid, stale, oversized, or unauthorized requests; no browser credentials/cookies | Session theft, IDOR, injection, resource abuse |
| API to database | Project state, evidence metadata, vectors, memory, audit | Non-owner `thesys_api` or `thesys_worker` role plus transaction-local principal | Service workspace scope and forced RLS `USING`/`WITH CHECK` policy | Confidential/restricted | TLS target plus AES-256-GCM envelope encryption for restricted reversible fields | Mutations and denied policy decisions | Missing/stale tenant context returns no rows and rejects writes; invalid ciphertext fails authentication | Cross-tenant query, SQL injection, operator access |
| API to object storage | Uploaded files and derived artifacts | Closed-registry application credential | Resource authorization plus workspace/project/source key policy | Confidential/restricted | Required TLS plus verified AES256/KMS server-side encryption | Redacted upload, download grant/denial, and deletion metadata | Deny unsafe key, type, scope, bucket controls, URL, or credential | Object overwrite, public bucket, malicious file, stale signed URL |
| API to LiteLLM | Prompts, context, structured-output schema | Application virtual key | Provider/model/classification policy | Public to restricted | TLS | Provider, model, classification, cost; no raw secret | Deny unapproved provider or data class | Data exfiltration, model substitution, overspend |
| LiteLLM to model provider | Provider request/response | Provider-scoped credential | LiteLLM route and allowlist | Same as request payload | TLS | Provider/model/cost metadata | Fail closed or approved deterministic fallback | Credential compromise, retention, response injection |
| API to external search provider | Search query and result metadata | Search API credential | Query classification and provider policy | Public/internal by default | TLS | Provider, query hash, cost | Deny restricted query or unapproved host | Query leakage, poisoned results, cost abuse |
| API to fetched URL | URL, headers, response body | Application fetcher | Scheme, DNS/IP, port, redirect, MIME, size policy | Public input; confidential after project annotation | TLS when source supports it | Fetch target, status, denial reason | Quarantine/fail source; never follow unsafe redirect | SSRF, DNS rebinding, oversized response, poisoning |
| Uploaded file to parser | File bytes and metadata | Sandboxed parser identity target | Type, magic bytes, size, malware/classification policy | Confidential/restricted | Local protected channel | Parser, hash, classification, scan result | Quarantine on unknown/unsafe result | Parser exploit, zip bomb, hidden prompt injection |
| Retrieval layer to LLM prompt | Selected chunks, provenance, trust metadata | Authenticated workflow | Workspace, classification, trust, budget filters | Highest class among chunks | In-process/TLS to gateway | Chunk IDs, filters, scores, drops | Omit unsafe chunks; fail if grounding requirement cannot be met | Cross-tenant vector hit, RAG poisoning, indirect injection |
| LLM to tool gateway | Tool name, arguments, proposal | Model acting for attributable user/workflow | Registry, role, scope, risk, approval, budget | Internal/confidential | In-process | Request, denial, approval, result summary | Deny unknown or unauthorized tool; do not execute proposal | Excessive agency, confused deputy, argument injection |
| Tool gateway to application service | Validated command and actor context | Tool gateway plus user/workflow identity | Service-level tenant and state-transition checks | Internal/confidential/restricted | In-process | Mutation and external side effect | Transaction rollback on policy/state failure | Gateway bypass, duplicate mutation, stale approval |
| Agent to durable project memory | Proposed memory, evidence links, confidence | Attributable workflow and reviewer | Provenance, trust, conflict, approval, TTL | Confidential/restricted | In-process/database TLS | Proposal, review, supersession | Store as proposed/quarantined; never silently activate | Memory poisoning, stale fact, unsupported claim |
| API to LangSmith | Redacted trace inputs/outputs and metrics | Scoped observability credential | Trace classification, sampling, provider policy | Inherits payload; confidential default | TLS | Export outcome and trace ID | Drop unsafe fields or skip export | Secret leakage, operator access, retention mismatch |
| API to Temporal | Workflow IDs, tenant IDs, state, activity payloads | Scoped Temporal client | Workflow type, tenant, budget, approval state | Confidential | TLS/mTLS target | Start, signal, retry, cancel, failure | Reject missing budget/identity; preserve recoverable state | Workflow replay abuse, duplicate execution, state leakage |
| MCP client to MCP server | Client identity, tool discovery/calls/results | Authenticated MCP client target | Client scope, tool policy, tenant, approval | Internal to restricted | TLS/local protected transport | Session, tool call, denial, result summary | Deny unauthenticated or over-scoped calls | Malicious client/server, tool spoofing, data exfiltration |

## Fail-closed behavior

- Unknown identity, workspace, role, tool, provider, model, data class, or policy
  results in denial.
- Unclassified sources remain quarantined and non-retrievable.
- Model output failing schema, citation, or DLP validation is rejected or safely
  regenerated; it is never executed as policy.
- Approval timeout, cancellation, or mismatch leaves the proposed mutation
  unapplied.
- Security telemetry failure must not disclose payloads in fallback logs.

## Tenant model

Most project-owned tables carry `workspace_id` directly. Small child/link tables
inherit tenant scope through a required foreign key to a directly scoped parent.
`GLOBAL_TABLES`, `IDENTITY_BOOTSTRAP_TABLES`, and `INHERITED_TENANT_TABLES` make
exceptions explicit. Sprint 62 forces Postgres RLS across all 40 modeled tenant
tables and reapplies transaction-local principal settings whenever a session
starts a new transaction. An invariant test fails when a new tenant table is
not added to the RLS contract. Authentication events use a tightly limited
null-identity insert policy before attribution is possible; these records remain
invisible to tenant reads.

## Provider and data policy

The effective provider decision combines data classification, workspace policy,
provider/model allowlists, egress host policy, and purpose. Restricted data is
local-only unless an explicitly approved restricted-data provider policy exists.
The provider decision and denial reason are auditable metadata; secrets and raw
restricted payloads are not.

## Security telemetry

Every governed action should carry actor, workspace, project, workflow/run,
control decision, risk level, and outcome. Sprint 67 centralizes security event
types, budgets, anomaly rules, alerting, and incident runbooks. Sprint 68 makes
the critical controls release gates.
