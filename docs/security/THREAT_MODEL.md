# Thesys Threat Model

## Scope and status

This threat model covers the browser, FastAPI API, Postgres/pgvector, object
storage, LiteLLM and model providers, search and URL ingestion, LangSmith,
Temporal, the governed tool registry, and MCP clients. It is the security
contract for V1 Sprints 61-68.

Controls are described as:

- `enforced`: implemented and covered by a regression test.
- `partial`: useful controls exist, with a named residual gap.
- `planned`: the control owner is a later security sprint.

The code-owned invariant and classification registries live in
`apps/api/app/security/contracts.py`. The control matrix names the test and
future sprint responsible for every partial or planned control.

## Security principles

Models may reason and propose. Deterministic services own identity, tenant
isolation, authorization, approvals, state transitions, memory writes, tool
execution, budgets, audit, and incident containment.

The application fails closed when identity, tenant scope, data classification,
provider policy, tool authorization, output validation, or approval cannot be
established.

## Threat actors

| Actor | Capability and motivation | Primary surfaces |
| --- | --- | --- |
| Anonymous external user | Probe public endpoints, exhaust resources, exploit parsers | API, auth, uploads, URL ingestion |
| Authenticated malicious user | Abuse valid access, discover tenant-boundary defects | API, retrieval, tools, exports |
| Compromised user account | Operate with a victim's valid session and role | Projects, evidence, decisions, approvals |
| Malicious workspace member | Exfiltrate or poison shared project data | Evidence, memory, validation, decisions |
| Malicious uploaded document | Exploit parsing or inject agent instructions | Upload, parser, retrieval, prompts |
| Malicious external webpage | Trigger SSRF, redirect abuse, poisoning, or prompt injection | URL fetch, extraction, retrieval |
| Malicious or compromised MCP server | Misrepresent tools, escalate scope, leak data | MCP registration, tool calls, approvals |
| Compromised package or container dependency | Execute code or tamper with builds | Python/npm dependencies, images, CI |
| Compromised model-provider credential | Spend funds, inspect traffic, impersonate the app | LiteLLM and provider APIs |
| Curious infrastructure operator | Inspect databases, object storage, traces, or backups | Data stores, telemetry, deployment |
| Buggy or over-permissioned autonomous agent | Call unsafe tools, loop, overspend, or corrupt memory | LLM gateway, tools, Temporal, memory |

## Protected assets

| Asset group | Assets | Security objective |
| --- | --- | --- |
| Identity and tenancy | User identity, workspace membership, roles, API/OAuth credentials | Authentication, least privilege, tenant isolation |
| Project strategy | Projects, theses, memory, research, validation results, decisions | Confidentiality, integrity, provenance |
| Evidence | Uploaded files, raw extracted text, sanitized searchable text, embeddings | Quarantine, classification, isolation, deletion |
| AI control plane | System prompts, tool schemas, MCP registrations, provider requests/responses | Integrity, non-disclosure, deterministic policy |
| Operations | Audit logs, LangSmith traces, Temporal state | Attribution, redaction, tamper evidence, retention |

## Primary threat scenarios

| Threat | Actor | Assets | Current controls | Status | Residual risk / owner |
| --- | --- | --- | --- | --- | --- |
| Cross-tenant object access or retrieval | Malicious user/member | All project data | OIDC principal, workspace-scoped service queries, forced RLS, tenant-scoped object keys, authorization-before-presign, and cross-tenant regression coverage | Enforced | Live Postgres RLS execution remains an environment-gated CI/deployment check |
| Credential replay or identity/membership denial | External attacker or stale identity | Accounts, workspace data, and audit trail | Immutable credential-free authentication outcomes, OIDC claim validation, active membership checks, hashed `sid`/`jti` revocation, RLS, and non-enumerating denial audit events | Partial | New direct-resource routes must preserve denial emitters |
| Direct prompt injection | Authenticated user | Prompts, tools, memory | Central guardrail gateway, attack classifiers, structured prompts/output, output DLP, and deterministic authorization | Enforced | Novel attacks and classifier variance require ongoing adversarial evaluation |
| Indirect prompt injection | Malicious document/webpage | Tools, memory, provider payloads | Untrusted-content boundaries, source-risk scoring, quarantine, secure retrieval, and guardrail restrictions | Enforced | Novel instruction formats require corpus and detector updates |
| Jailbreak or policy bypass | Malicious user/source | Tool execution, data disclosure | Jailbreak classifier, output DLP, role/policy gates, proposal tools, approvals, and schemas | Enforced | Policy coverage must expand with new tools and prompts |
| RAG corpus poisoning | Malicious member/source | Evidence, research findings | Provenance, source scoring, duplicate/instruction-density detection, quarantine, secure ranking, and citation verification | Enforced | Approved but misleading sources still require human evidence review |
| Durable memory poisoning | Agent or malicious source | Project memory, decisions | Proposal status, provenance, policy, review, conflict detection, trust score, TTL, supersession, and source invalidation | Enforced | Trusted-looking evidence can still influence a reviewable proposal |
| MCP/tool confused deputy | Compromised MCP client/server | Project data, side effects | Reviewed registry, TLS/fingerprint/version/schema checks, scoped credentials, OPA policy, approvals, audit, and budgets | Enforced | Hosted identity-provider and remote-server operations require deployment verification |
| Sensitive-data exfiltration to provider | User, agent, compromised credential | Restricted/confidential data | Classification/provider policy, redaction, scoped credentials, and egress allowlists | Enforced | Detection is bounded by supported PII and secret patterns |
| Secrets persisted in logs or traces | Bug, dependency, operator | API/OAuth credentials | Shared audit/tool/trace/provider redaction, closed secret registry, output DLP, and adversarial secret cases | Enforced | Novel secret formats may evade best-effort patterns |
| SSRF and unsafe parsing | Malicious URL/file | Network, parser, stored data | Network-address/redirect/MIME/size guards, malware scan, PDF/image preflight, extraction limits, and quarantine | Enforced | DNS rebinding and parser zero-days remain deployment and dependency risks |
| Excessive token/tool/retrieval use | User or looping agent | Availability, provider budget | Redis-backed rate limits, durable multi-dimensional budgets, loop detection, alerts, and kill switches | Enforced | Hosted Redis availability is a fail-closed deployment dependency |
| Misinformation stored as fact | Model or poisoned source | Claims, memos, decisions | Citation verification, support levels, approval gates | Enforced | Adversarial citation-confusion tests expand in Sprint 68 |
| Dependency or image compromise | Supply-chain attacker | Runtime, credentials, data | Locked dependencies, pinned actions/base images, SBOM/provenance, scans, signatures, and fail-closed release reporting | Enforced | GitHub branch protection and required-review settings are repository-administration controls |
| Trace/backup/operator disclosure | Infrastructure operator | Confidential/restricted data | Redaction, scoped service access, envelope encryption for reversible restricted fields, and tenant-scoped retention cleanup | Partial | External backups and fields outside the explicit encryption set require deployment governance |

## Security invariants

The twelve normative invariants are maintained in
`apps/api/app/security/contracts.py` and verified by
`apps/api/app/tests/security/test_security_invariants.py`. An invariant may only
move from `planned` or `partial` to `enforced` when its control and regression
test both exist.

## Assumptions

- V1 is a single-region portfolio deployment unless a later deployment profile
  states otherwise.
- External model/search providers are untrusted processors and receive only
  policy-approved data.
- Retrieved content, uploaded content, model output, and MCP output are untrusted.
- Local developer access is trusted only in an explicitly local environment.

## Review triggers

Update this model when a change adds a trust boundary, provider, durable memory
path, tool, external side effect, data class, auth mode, tenant-sharing behavior,
or deployment topology. Pull requests use `.github/pull_request_template.md` to
surface those triggers.
