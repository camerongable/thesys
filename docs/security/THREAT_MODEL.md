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
| Cross-tenant object access or retrieval | Malicious user/member | All project data | OIDC principal, workspace-scoped service queries, forced RLS, tenant-scoped object keys, authorization-before-presign test | Partial | Remaining service/security-event matrix coverage, Sprint 62 |
| Direct prompt injection | Authenticated user | Prompts, tools, memory | Structured prompts, output schemas, deterministic authorization | Partial | Central input/output gateway, Sprint 64 |
| Indirect prompt injection | Malicious document/webpage | Tools, memory, provider payloads | Untrusted-content boundaries and source-risk metadata | Partial | Central detection/quarantine policy, Sprints 63-65 |
| Jailbreak or policy bypass | Malicious user/source | Tool execution, data disclosure | Role gates, proposal tools, approvals, schema validation | Partial | Jailbreak classifier and output DLP, Sprint 64 |
| RAG corpus poisoning | Malicious member/source | Evidence, research findings | Provenance, source scoring, citation verification | Partial | Quarantine, trust thresholds, poisoning evals, Sprints 63/65 |
| Durable memory poisoning | Agent or malicious source | Project memory, decisions | Proposal status, provenance, review, conflict detection | Partial | Trust score, TTL, supersession enforcement, Sprint 65 |
| MCP/tool confused deputy | Compromised MCP client/server | Project data, side effects | Central registry, role checks, approvals, audit | Partial | MCP identity, scopes, policy-as-code, sandbox, Sprint 66 |
| Sensitive-data exfiltration to provider | User, agent, compromised credential | Restricted/confidential data | Egress host allowlist, redaction, classification contract | Partial | Payload-aware provider policy and DLP, Sprints 62-64 |
| Secrets persisted in logs or traces | Bug, dependency, operator | API/OAuth credentials | Shared redaction for audit/tool/trace/error paths | Partial | Canary-secret adversarial coverage, Sprints 64/68 |
| SSRF and unsafe parsing | Malicious URL/file | Network, parser, stored data | Network-address, redirect, MIME, magic-byte, and size guards | Partial | Quarantine, malware scan, parser isolation, Sprint 63 |
| Excessive token/tool/retrieval use | User or looping agent | Availability, provider budget | Rate/concurrency limits, budget preflight, circuit checks | Partial | Durable multi-dimensional budgets and alerts, Sprint 67 |
| Misinformation stored as fact | Model or poisoned source | Claims, memos, decisions | Citation verification, support levels, approval gates | Enforced | Adversarial citation-confusion tests expand in Sprint 68 |
| Dependency or image compromise | Supply-chain attacker | Runtime, credentials, data | Lockfiles and local dependency checks | Partial | SBOM, signatures, strict CI scanning, Sprint 68 |
| Trace/backup/operator disclosure | Infrastructure operator | Confidential/restricted data | Redaction and scoped service access | Planned | Encryption, retention, break-glass controls, Sprint 62/67 |

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
