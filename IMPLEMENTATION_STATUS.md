# Implementation Status

## Current Phase

V1 Sprints 51-60 closed the ordered AI engineering gap track. Sprint 61
established the formal security contract for the V1 security-hardening phase:
code-owned data classifications and security invariants, explicit tenant and
memory-write paths, a threat model, trust-boundary architecture, control matrix,
abuse cases, automated invariant checks, and a pull-request security checklist.
Sprint 62 production identity work is now underway: OIDC/JWKS verification,
principal-backed authorization context, strict active membership resolution,
the production dev-auth startup guard, forced Postgres RLS, and scoped database
roles are implemented. Production secret providers, the workspace envelope
encryption foundation, and tenant-scoped private object storage are also
implemented. Sprints 62-68 own the remaining session/auth-audit hardening,
secure ingestion, centralized guardrails, secure RAG/memory, MCP/tool policy,
monitoring/incident response, and adversarial CI controls identified as partial
or planned by that contract.

Thesys now demonstrates a stronger production-style AI architecture for a
portfolio project:

- provider-backed embeddings with deterministic local fallback and re-embedding
  support
- SQL-level pgvector retrieval with Python fallback
- multi-stage retrieval with query planning, subquery decomposition, reranking,
  context assembly, citation-preserving result metadata, and retrieval-quality
  diagnostics
- LLM-grounded Ask Thesys answers with citations, bounded recent-turn context,
  retrieval diagnostics, action-card routing, approval-gated proposals, guide
  evals, SSE-shaped response delivery, and deterministic fallback
- governed external source discovery with deterministic and Tavily providers
- multimodal evidence extraction for image uploads and low-text PDF fallback
- URL/upload security guards, source provenance metadata, canonical
  URL/content-hash dedupe, fetched-page prompt-injection markers, source quality
  signals, and PDF page lineage
- typed context packs, workflow-aware memory selection, and multiple memory
  types
- MCP-shaped adapter over the governed internal tool registry
- AI cost accounting, budget/circuit checks, guide evals, and local AI quality
  gates
- Temporal-backed durable research sprint orchestration
- LangGraph-backed agentic research synthesis
- LangSmith-compatible trace metadata, local AI run/step records, and custom eval
  checks
- shared service utilities for metadata merging and workflow finalization
- developer docs and README navigation for AI architecture review

The simplified project experience is preserved: retrieval, search, extraction,
cost, trace, and quality details stay in Inspect, Evidence, workflow trace,
artifact structured content, and eval/check surfaces rather than new main
dashboard cards. The homepage and main project workflow should remain focused on
current verdict, next action, evidence health, validation, and decision state.

## Sprint 61 Scope

- [x] Add the code-owned `DataClassification` and provider-policy registry.
- [x] Represent all twelve security invariants with status, owner sprint,
  enforcement, test reference, and residual risk.
- [x] Declare global and inherited tenant-table paths so new unscoped tables fail
  an invariant check.
- [x] Declare proposal, trusted-user, approved-projection, and trusted-service
  memory mutation paths.
- [x] Add the required threat model, data-classification guide, control matrix,
  security architecture, and abuse-case documents under `docs/security/`.
- [x] Add automated checks for the security registry, required documents and
  trust boundaries, tenant paths, governed tools, memory writes, and audit paths.
- [x] Keep production-auth, ingestion-classification, centralized-guardrail, and
  complete durable-budget gaps visible as strict expected failures owned by
  Sprints 62, 63, 64, and 67.
- [x] Add the pull-request security-impact checklist and README/docs navigation.

## Sprint 61 Verification

- [x] `apps/api/.venv/bin/ruff check apps/api/app/security apps/api/app/tests/security`
  passed.
- [x] `apps/api/.venv/bin/python -m compileall apps/api/app/security apps/api/app/tests/security -q`
  passed.
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/security/test_security_invariants.py -q`
  passed (`8 passed, 4 xfailed`; expected gaps: Sprints 62, 63, 64, and 67).
- [x] `cd apps/api && .venv/bin/pytest app/tests/security/test_security_invariants.py app/tests/test_security_governance.py app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py -q`
  passed (`45 passed, 4 xfailed, 3 warnings`).
- [x] `git diff --check` passed.

## Sprint 62 Progress

- [x] Add `APP_ENV`-aware configuration and reject `AUTH_MODE=dev` outside
  local development.
- [x] Add OIDC/JWKS authentication with a configured asymmetric algorithm
  allowlist, signature and standard-claim validation, authorized-party checks,
  and bounded JWKS caching/timeouts.
- [x] Add the validated `Principal` model and route authorization identity
  through it, including Temporal activity reconstruction.
- [x] Require pre-provisioned, active OIDC users, exact workspace membership,
  and agreement with the database role; never provision from token claims.
- [x] Add persistent user status and migration `0028_production_identity`.
- [x] Bind validated principals to transaction-local Postgres workspace/user
  settings and reapply them after every session transaction boundary.
- [x] Enable and force RLS across all 41 currently modeled tenant tables:
  migration `0029_tenant_rls` covers the original 38, migration
  `0030_workspace_data_keys` covers the restricted key table, migration
  `0031_authentication_events` covers immutable authentication outcomes,
  `0032_session_revocations` covers hashed session invalidation, and five
  child/link tables use inherited parent policies.
- [x] Separate migration, API, Temporal worker, and readonly database roles;
  hosted startup rejects a bootstrap or mismatched runtime username.
- [x] Add direct wrong-tenant Postgres ORM coverage for projects, evidence,
  chunks/vector retrieval, memory, approvals, tools, decisions, and
  research/trace/workflow metadata. The test is environment-gated locally.
- [ ] Complete service-boundary cross-tenant coverage as more authorization and
  security-event surfaces land. Wrong-workspace signed-object URL requests are
  now covered and cannot reach the presigner. There are no standalone
  `validation_plans` or broad `security_events` tables in the current schema;
  the scoped `authentication_events` table now covers current identity outcomes.
  New tenant tables fail the RLS invariant until registered and migrated.
- [x] Add environment, Vault KV v2, and AWS Secrets Manager providers; reject
  environment-backed application secrets in staging and production, and route
  all current API credential consumers through the closed secret-name registry.
- [x] Add AES-256-GCM envelope encryption with random per-workspace DEKs,
  versioned external wrapping keys, authenticated workspace/purpose context,
  wrapping-key re-encryption, and forced RLS on `workspace_data_keys` via
  migration `0030_workspace_data_keys`.
- [x] Redact secret-shaped values at the durable project-memory write boundary;
  audit, tool, trace, and public-error paths retain their existing shared
  redaction controls. No current domain model stores OAuth refresh tokens,
  connector credentials, reversible PII maps, or user provider credentials, so
  those future fields must use `EncryptedValue` when introduced.
- [x] Harden object storage with tenant/project/source key scopes, private-bucket
  verification, public ACL denial, explicit content type and safe download
  disposition, AES256/KMS server-side encryption, short presign lifetimes,
  authorization before presign, TLS enforcement, retention policy checks, and
  durable upload/download/deletion audit metadata without URLs or raw keys.
- [x] Add global browser security headers: strict API CSP with frame denial,
  `nosniff`, no-referrer policy, denied sensitive browser capabilities, legacy
  frame denial, and production HSTS. The API is explicitly stateless and
  header-authenticated, so CORS does not enable browser credentials or cookies.
- [x] Add immutable, credential-free authentication events with forced RLS for
  tenant-attributable events and a null-identity insert policy only for
  pre-authentication failures. Successful authentication, missing/invalid
  credentials, rejected bearer tokens, and denied OIDC identity/membership
  resolution now emit durable `login_success`, `login_failure`,
  `token_validation_failure`, or `workspace_access_denied` records.
- [x] Add self-service session revocation for OIDC `sid` or JWT `jti` identities:
  revocation stores only a tenant/user-scoped SHA-256 digest, emits
  `session_revoked`, and rejects subsequent use before it reaches a route.
- [x] Add owner-only workspace member role changes with last-owner protection;
  successful changes emit an attributable `role_change` authentication event
  plus a target-membership governance event.
- [x] Return a non-enumerating 404 and emit a credential-free,
  tenant-attributable `cross_tenant_access_attempt` when an owner addresses a
  member belonging only to another workspace.
- [x] Emit a credential-free, tenant-attributable
  `cross_tenant_access_attempt` from the shared project lookup on a scoped
  project denial. Forced RLS deliberately keeps unknown and out-of-workspace
  UUIDs indistinguishable, and the event stores neither requested UUID.
- [x] Emit credential-free, tenant-attributable cross-tenant-attempt events
  from direct decision retrieval and tool-invocation approval lookups, with
  fixed reason codes and no persisted project, decision, or invocation IDs.
- [x] Emit a credential-free, tenant-attributable cross-tenant-attempt event
  from the standalone workflow-run lookup, protecting AI execution and trace
  metadata without persisting the requested run ID.
- [x] Emit credential-free, tenant-attributable cross-tenant-attempt events
  from direct research-plan editing and research-sprint approval lookups, with
  fixed reason codes and no persisted project, plan, or sprint IDs.
- [ ] Add broader authorization-denial emitters as their corresponding
  direct-resource mutation/read flows are introduced or identified.

## Sprint 62 Identity Verification

- [x] Focused OIDC and invariant tests passed (`29 passed, 3 xfailed`; expected
  remaining gaps: Sprints 63, 64, and 67).
- [x] The full backend test suite passed (`293 passed, 3 xfailed, 3 warnings`).
- [x] Focused ruff, compileall, and production startup-guard checks passed.
- [x] The non-strict local security gate passed (`38 passed`; AI quality
  `10/10`). `pip-audit`, Docker inventory, and the npm registry audit were
  unavailable and remained explicit non-strict warnings.

## Sprint 62 Tenant Isolation Verification

- [x] Focused tenant-context, RLS migration/role contract, and direct-Postgres
  tests passed (`16 passed, 1 skipped, 3 xfailed, 1 warning`). The skip is the
  live Postgres policy test; expected xfails remain owned by Sprints 63, 64,
  and 67.
- [x] The security plus project/evidence/memory/tool/MCP/Temporal checkpoint
  passed (`101 passed, 1 skipped, 3 xfailed, 3 warnings`).
- [x] `alembic upgrade 0028_production_identity:0029_tenant_rls --sql`
  rendered all 38 forced RLS policies and scoped role grants with PostgreSQL
  dialect output; `alembic heads` reports `0029_tenant_rls`.
- [x] Focused ruff, compileall, lockfile synchronization, diff checks, and
  conflict-marker checks passed.
- [ ] Run `RLS_TEST_DATABASE_URL=<thesys_api-url> .venv/bin/pytest
  app/tests/security/test_postgres_rls.py -q` on a migrated Postgres instance.
  This workstation has no Postgres binaries, Docker, or Podman, so direct policy
  execution could not run in this cycle. The test fails if the connection is a
  superuser/BYPASSRLS role, any policy is not forced, cross-tenant reads become
  visible, or wrong-tenant writes succeed.

## Sprint 62 Secrets and Encryption Verification

- [x] Focused provider-policy, Vault/cloud adapter, leakage, AES-GCM
  round-trip/tamper/workspace/purpose, wrapping-key rotation, RLS invariant,
  identity, tenant-context, and memory tests passed (`54 passed, 3 xfailed`).
- [x] All current API credential reads were checked to route through
  `app.security.secrets`; local settings/provider representations exclude raw
  secret values.
- [x] The full backend regression suite passed (`312 passed, 1 skipped,
  3 xfailed, 3 warnings`).
- [ ] Validate migrations `0030_workspace_data_keys` and
  `0031_authentication_events` against live Postgres as part of the existing
  `RLS_TEST_DATABASE_URL` CI checkpoint.

## Sprint 62 Object Storage Verification

- [x] Focused object-storage, evidence, project, OIDC, tenant-context, and
  secret-provider tests passed (`61 passed, 1 warning`).
- [x] The full backend regression suite passed (`323 passed, 1 skipped,
  3 xfailed, 3 warnings`).
- [x] Wrong-workspace download tests prove authorization occurs before presign;
  source and project deletion tests prove tenant-scoped object removal and
  deletion-audit persistence.
- [x] Hosted configuration fails closed unless S3 mode, HTTPS, disabled runtime
  bucket creation, and live bucket-control verification are configured.
- [ ] Run the S3 security contract against a production-equivalent bucket and
  the local auto-configuration path against MinIO. This workstation does not
  have Docker, Podman, or cloud object-storage credentials, so those live checks
  remain deployment-owner verification.

## Sprint 62 Browser Security Verification

- [x] Browser-security and identity tests passed (`23 passed, 1 warning`),
  including local API headers, CORS preflight without credentials, and
  production HSTS behavior.
- [x] The current API does not issue browser cookies. Any future cookie-based
  session flow must add secure/HttpOnly/SameSite cookies, short lifetime,
  rotation, logout invalidation, and CSRF protection before it is enabled.

## Sprint 62 Authentication Audit Verification

- [x] Auth-audit, OIDC, and invariant tests passed (`39 passed, 3 xfailed,
  1 warning`). Tests cover successful attribution, token-validation failure,
  OIDC workspace denial, the absence of credential storage columns, and the
  forced-RLS pre-auth insertion contract.
- [x] OIDC session revocation tests passed (`42 passed, 3 xfailed`), covering
  endpoint behavior, hashed-only persistence, audit
  attribution, and denial on token reuse.
- [x] Workspace member administration tests passed (`30 passed, 1 warning`
  across focused auth-audit, OIDC, and role-administration coverage), including
  owner-only role changes, last-owner protection, dual audit attribution, and
  non-enumerating cross-tenant attempts.
- [x] The full backend regression suite passed after role-administration audit
  coverage (`338 passed, 1 skipped, 3 xfailed, 3 warnings`).
- [x] Shared project-scope audit coverage passed with the full backend suite
  (`339 passed, 1 skipped, 3 xfailed, 3 warnings`).
- [x] Direct decision and tool-invocation scope-audit coverage passed with the
  full backend suite (`340 passed, 1 skipped, 3 xfailed, 3 warnings`).
- [x] Standalone workflow-run scope-audit coverage passed with the full backend
  suite (`341 passed, 1 skipped, 3 xfailed, 3 warnings`).
- [x] Direct research-plan and research-sprint scope-audit coverage passed with
  the full backend suite (`342 passed, 1 skipped, 3 xfailed, 3 warnings`).
- [ ] Run migration `0031_authentication_events` and its policy checks against
  the existing live-Postgres CI checkpoint. Local SQLite tests prove the model
  and offline migration contract but not a PostgreSQL RLS execution.
- [x] The full backend regression suite passed (`331 passed, 1 skipped,
  3 xfailed, 3 warnings`). `alembic heads` reports
  `0031_authentication_events`; offline PostgreSQL SQL renders its checks,
  forced RLS, pre-auth insert policy, and scoped runtime grants.

## Sprint 62 Session Revocation Verification

- [x] The full backend regression suite passed (`334 passed, 1 skipped,
  3 xfailed, 3 warnings`). `alembic heads` reports
  `0032_session_revocations`; offline PostgreSQL SQL renders the table, digest
  uniqueness, forced RLS, and insert/select-only runtime grants.
- [ ] Run migration `0032_session_revocations` and its tenant policy against the
  live-Postgres CI checkpoint. Local tests prove the application behavior and
  offline migration contract but not live PostgreSQL RLS enforcement.

## Sprint 63 Progress

- [x] Add a deterministic `DataProtectionService` that identifies emails, phone
  numbers, credit-card-like values, credential-bearing URLs, API keys/access
  tokens, and person names; assigns an internal/confidential/restricted data
  classification; and produces tokenized or redacted searchable text.
- [x] Ensure note text is never committed to `EvidenceSource.raw_text` before
  protection. Source titles, persisted searchable text, summaries, chunk text,
  and embedding inputs now use the sanitized representation.
- [x] Attach source and chunk security metadata, including data classification,
  PII status/entity types, approval state, sanitization version, and vector
  retrieval eligibility. Preserve sanitized line layout for deterministic PDF
  table provenance while using normalized sanitized text for chunks.
- [x] Require approved source classification/security metadata and approved chunk
  eligibility in both retrieval and re-embedding paths. Missing metadata fails
  closed rather than being treated as legacy content.
- [x] Add a ClamAV-compatible streaming scanner adapter and require it in hosted
  configuration. Disabled, unavailable, and infected scanner outcomes create a
  metadata-only quarantined source plus a high-risk audit event before object
  storage, parsing, chunking, or embedding.
- [x] Add deterministic LiteLLM provider policy that classifies each outbound
  chat payload and sends a redacted/tokenized representation when it contains
  PII or restricted values. Trace payloads and errors now redact the same PII
  classes, secrets, and sensitive keys before LangSmith export.
- [x] Add encrypted project-local reidentification mappings under migration
  `0034_pii_token_mappings`. Each mapping uses the workspace envelope key with a
  project-specific authenticated purpose; identical identifiers receive an
  independent token map per project, and only workspace owners can reverse a
  token through an attributable high-risk audit event.
- [x] Propagate source deletion through private object removal, chunks and
  embeddings, evidence links, discovery/candidate references, unsupported
  claims, and memory derived from invalidated artifact versions. The transaction
  verifies no chunk survives, thereby revoking retrieval eligibility, and emits
  a redacted high-risk propagation audit event.
- [x] Define all Sprint 63 retention classes in a central configurable policy
  registry: raw objects, sanitized text, embeddings, PII maps, model prompts and
  outputs, LangSmith traces, audit/security events, and Temporal history. Source
  and chunk metadata now retain per-representation expiry, migration `0035`
  makes PII-map expiry durable, and workspace-scoped cleanup removes expired PII
  maps and routes expired evidence through full deletion propagation.
- [x] Integrate Presidio analyzer and anonymizer rule recognizers with the
  deterministic credential/identifier scanner. Extended identifiers such as
  SSNs, IBANs, bank accounts, passports, and IP addresses now contribute to
  classification and redaction without an implicit NLP-model download.
- [x] Persist a validated secure-ingestion lifecycle in source metadata across
  note, URL, discovery, and file paths: uploaded, malware scanning,
  extraction, classification, optional PII review, embedding, and retrieval.
  The history preserves reprocessing attempts and records terminal quarantined
  or failed outcomes; invalid terminal transitions are rejected.
- [x] Parse PDFs in a spawned, isolated worker before object storage. The worker
  enforces configured timeout, page, extracted-character, and Linux address-space
  limits; malformed, resource-limited, encrypted, or active-content PDFs fail
  closed before persistence. macOS development workers retain the timeout and
  character bounds because its Python address-space reservation is incompatible
  with `RLIMIT_AS`.
- [x] Reject ZIP and other unsupported archive content before malware scanning,
  storage, or parsing through the strict upload extension/MIME allowlist.
- [x] Enforce a configurable PDF stream decompression-ratio limit inside the
  isolated parser worker. Every reachable encoded stream is checked before page
  text extraction, and an over-limit stream is rejected before object storage.
- [x] Decode allowed PNG/JPEG/WebP uploads through Pillow before storage,
  reject animated, oversized, over-expanded, or malformed images, and re-encode
  the safe pixel content without EXIF or ancillary metadata. The sanitized bytes
  are the only image representation stored or sent to multimodal extraction.
- [x] Require extension, declared MIME, and independently detected content MIME
  to agree before any upload reaches malware scanning, storage, or parsing.
  `python-magic` is the primary detector; an unavailable binding falls back to
  the local `file` utility and rejects the upload when neither detector works.
- [x] Preflight clean PDFs before object storage or extraction. Password-protected
  files, active-content action trees, malformed inspection graphs, and files
  exceeding the configurable page limit are rejected with a security audit event.
- [x] Add a tenant-scoped Temporal maintenance activity for local retention. It
  redacts expired AI prompts, outputs, errors, and local LangSmith references
  while preserving run accounting, and deletes expired workspace-attributable
  audit/security events without deleting active session revocations.
- [x] Register and reconcile the worker-owned `retention-cleanup-v1` Temporal
  schedule. Its global sweep chooses one active principal per workspace and
  fans out to the tenant-bound activity, so every destructive operation remains
  subject to that workspace's RLS context.
- [x] Reconcile Temporal namespace history TTL to the configured policy before
  worker startup, and require LangSmith deployments to attest that the external
  project retention exactly matches the configured trace-retention policy before
  tracing can be enabled.
- [x] Purge expired unscoped pre-authentication failures through a migration
  role-owned, worker-only PostgreSQL `SECURITY DEFINER` function. The scheduled
  retention workflow invokes it separately from tenant-bound cleanup, and it
  cannot delete active session-revocation controls.
- [x] Extend purpose-aware classification routing to non-chat providers.
  LiteLLM embeddings and Tavily searches send only their redacted text
  representation, while live multimodal uploads deny files whose locally
  inspectable bytes require redaction before raw provider transit.

## Sprint 63 Verification

- [x] Focused PII sanitization plus evidence ingestion tests passed (`16
  passed, 1 warning`), including an assertion that raw names, emails, and API
  keys reach neither persisted chunks nor embedding inputs.
- [x] Source discovery and upload-security checkpoint passed (`47 passed,
  3 warnings`), including PDF table-extraction regression coverage.
- [x] Retrieval/re-embedding security-gate checkpoint passed (`28 passed,
  1 warning`), covering blocked source and chunk metadata plus normal approved
  retrieval.
- [x] Upload quarantine checkpoint passed (`36 passed, 5 warnings`), covering
  unavailable and infected scanners, no object/chunk persistence, and existing
  clean upload behavior.
- [x] Provider/trace sanitization checkpoint passed (`35 passed, 1 warning`),
  including a captured LiteLLM HTTP request with PII and API keys removed.
- [x] Encrypted project-local pseudonymization checkpoint passed (`13 passed,
  1 warning`), covering encrypted stored values, project-local token scopes,
  owner-only reidentification, no PII in audit metadata, and existing ingestion
  plus envelope-encryption behavior.
- [x] RLS/migration pseudonymization checkpoint passed (`20 passed, 1 skipped,
  2 xfailed, 1 warning`); migration `0034_pii_token_mappings` rendered offline
  and is the only Alembic head.
- [x] Full backend regression passed (`355 passed, 1 skipped, 2 xfailed,
  5 warnings`) with repository-wide lint, compile, and whitespace checks clean.
- [x] Source-deletion propagation checkpoint passed (`128 passed, 1 skipped,
  2 xfailed, 3 warnings`), covering private object deletion, zero surviving
  retrievable chunks, claim invalidation, memory staleness, and audit metadata.
- [x] Retention-policy checkpoint passed (`125 passed, 1 skipped, 2 xfailed,
  3 warnings`), including policy completeness, expiry metadata, scoped PII-map
  cleanup, expired-source propagation, and offline migration SQL for `0035`.
- [x] Non-chat provider-routing checkpoint passed (`52 passed, 2 xfailed, 1
  warning`), capturing outbound LiteLLM embedding and Tavily payloads after
  redaction and proving detected sensitive multimodal bytes never create an
  HTTP client.
- [x] Content-based upload MIME checkpoint passed (`156 passed, 1 skipped, 2
  xfailed, 6 warnings`), covering mismatch rejection before scanner/storage,
  detector unavailability, scanner quarantine, evidence ingestion, and source
  security metadata.
- [x] Presidio-backed PII checkpoint passed (`134 passed, 1 skipped, 2 xfailed,
  3 warnings`), covering rule-based extended identifiers, deterministic secret
  handling, redaction before embeddings and providers, and secure evidence
  ingestion.
- [x] PDF preflight checkpoint passed (`137 passed, 1 skipped, 2 xfailed, 6
  warnings`), covering encrypted and active-content PDF denial before storage,
  configurable page limits, malware quarantine, and normal PDF extraction.
- [x] Secure-ingestion lifecycle checkpoint passed (`150 passed, 1 skipped, 2
  xfailed, 9 warnings`), covering complete source histories, reprocessing,
  failed URL ingestion, scanner quarantine, PDF preflight, and rejected invalid
  terminal transitions.
- [x] Bounded PDF parser checkpoint passed (`152 passed, 1 skipped, 2 xfailed,
  10 warnings`), covering isolated valid parsing, resource-limit rejection before
  storage, PDF security preflight, ingestion, and broader security boundaries.
- [x] PDF decompression-ratio checkpoint passed (`153 passed, 1 skipped, 2
  xfailed, 11 warnings`), covering an over-limit compressed stream rejected
  before storage alongside the evidence and security boundary suite.
- [x] Image sanitization checkpoint passed (`156 passed, 1 skipped, 2 xfailed,
  12 warnings`), covering metadata removal before storage/provider transit,
  compressed-image rejection, evidence ingestion, and security boundaries.
- [x] Sprint 63 acceptance audit and output-boundary checkpoint passed (`139
  passed, 1 skipped, 2 xfailed, 9 warnings`), covering generated-summary
  redaction in durable workflow state, provider-produced image captions and
  metadata, pre-fetch URL-title sanitization, access-token detection, PII inside
  Markdown and `.log` uploads, and exclusion of PDF document metadata from
  searchable source metadata.

## Sprint 64 Progress

- [x] Add a central `app.security.guardrails` package with deterministic Unicode
  normalization, invisible-character and encoded-payload inspection, direct and
  indirect injection classification, jailbreak, prompt-extraction, tool-
  manipulation, and exfiltration detection, plus explicit block/restriction
  decisions that disable tools and memory writes.
- [x] Route LiteLLM normal and streaming chat completions through the gateway.
  Prompts now receive a non-secret trusted system boundary before provider
  policy/redaction, high-risk prompts fail before HTTP client creation, and
  unsafe model output is rejected before it reaches callers.
- [x] Add common retrieved-content XML wrapping, conservative Markdown/HTML/link
  sanitization, and citation membership validation primitives for subsequent
  retrieval and rendering integrations.
- [x] Evaluate Ask Thesys messages before proposal tools, retrieval, memory
  context, or model processing. Actionable detections now create redacted,
  attributable guardrail audit events and record decision-only evidence in the
  AI step; restricted guide requests receive a safe response without tools.
- [x] Evaluate each retrieved Ask Thesys evidence item at its provenance
  boundary, emit decision-only audit/AI-step metadata, XML-escape allowed
  source wrappers, and quarantine blocked sources before prompt construction,
  cache payload generation, response context, or citation verification in both
  regular and SSE flows.
- [x] Enforce an HTTPS-only browser URL policy in the shared Markdown renderer.
  Rendered Markdown now turns unsafe destinations and all image destinations
  into inert text, while approved links use `noopener noreferrer`.
- [x] Apply the same browser URL policy to every direct project metadata,
  citation, candidate, competitor, and trace anchor. Invalid URLs retain their
  text but never render as anchors; the final scan leaves no raw new-window
  external-data anchors outside the shared policy components.
- [x] Route every current LiteLLM text-generation boundary through the gateway:
  normal and streaming chat calls use `LiteLLMClient`, while direct multimodal
  extraction now adds the trusted prompt boundary, file-content screening, and
  output checks before JSON parsing or evidence persistence. The former Sprint
  64 all-LLM-call invariant is now enforced rather than expected to fail.
- [x] Require grounded guide citations to name an exact retrieved chunk and copy
  an exact supporting quote from it. The server retains a citation as
  `supported` only when that quote occurs in the cited chunk and shares at least
  two substantive terms with the answer; invalid, stale source-ID-only, or
  weakly related citations are withheld and surfaced as missing support. Mere
  retrieval drilldowns are explicitly `weak`, and the guide prompt/cache version
  is bumped to prevent legacy source-ID-only outputs from being replayed.
- [x] Make the prompt-attack detector runtime posture explicit with a central
  `GUARDRAIL_ATTACK_DETECTOR` selector for the deterministic baseline or one
  opt-in Prompt Guard, NeMo Guardrails, or Llama Guard adapter. An unavailable
  selected adapter cannot silently allow side effects: it disables tools and
  memory writes, records redacted detector-only metadata, and emits
  `guardrail_service_unavailable` before the guide can invoke proposals or
  retrieval.
- [x] Explicitly scope LiteLLM embeddings as a non-generative provider boundary.
  Embedding transit uses a dedicated `embedding` policy helper for
  classification and PII/secret redaction, then credential, egress, and vector
  dimension controls; it does not receive a synthetic prompt or output guard
  because it returns only vectors and cannot create a claim, tool call, memory
  write, or authorization decision. The security invariant enumerates the
  distinct chat and embedding HTTP boundaries to prevent policy drift.
- [x] Complete the Sprint 64 acceptance audit: all generative model boundaries
  use `GuardrailGateway`, while the documented, tested embedding exception uses
  the non-generative provider policy contract.

## Sprint 64 Verification

- [x] Gateway, LiteLLM data-protection, guide, validation, source-discovery, and
  full backend checkpoints passed (`399 passed, 1 skipped, 2 xfailed, 12
  warnings`); repository-wide lint, compile, lock, and whitespace checks are
  clean.
- [x] Guide workflow guardrail and audit-event checkpoint passed (`401 passed,
  1 skipped, 2 xfailed, 12 warnings`), including regular and SSE requests that
  confirm direct injections create `prompt_injection_detected` events and cannot
  invoke proposal or retrieval tools.
- [x] Retrieved-content guardrail checkpoint passed (`404 passed, 1 skipped, 2
  xfailed, 12 warnings`), including regular and SSE indirect-injection tests
  that verify quarantined source text cannot reach a provider prompt or become
  a citation, response-context item, or cache input.
- [x] Shared Markdown rendering policy test passed (`2 passed`), executing the
  checked-in URL policy against permitted HTTPS and blocked `http`,
  `javascript`, `data`, `file`, and `mailto` destinations. The broader web test
  command remains unavailable because npm registry resets prevented dependency
  installation and the two existing TypeScript-dependent tests cannot resolve
  `typescript`.
- [x] Direct external-anchor regression suite passed (`3 passed`), verifying the
  safe-link wrapper and every project metadata/citation/trace surface. The same
  npm dependency-fetch limitation prevents broader web type and integration
  checks in this environment.
- [x] Multimodal and all-model-call checkpoint passed (`409 passed, 1 skipped,
  1 xfailed, 12 warnings`), including direct multimodal input/output blocking
  tests and the now-enforced Sprint 64 provider-boundary invariant.
- [x] Citation semantic-support checkpoint passed (`409 passed, 1 skipped, 1
  xfailed, 12 warnings`), including exact source/chunk/quote verification for
  normal and streamed guide responses, plus rejected unrelated or missing-chunk
  citations.
- [x] Detector-unavailability checkpoint passed: the selected optional adapter
  restricts tools and memory writes, guide proposal/retrieval is withheld, and
  `guardrail_service_unavailable` is recorded without request content.
- [x] Embedding-provider scope checkpoint passed: non-generating provider policy
  coverage, PII/secret-redaction coverage, and the static chat-versus-embedding
  boundary invariant passed.

## Sprint 65 Progress

- [x] Establish a shared `RetrievalSecurityPolicy` for evidence candidates.
  The pgvector SQL and Python fallback paths now apply the same workspace and
  project scope, approved source/classification state, chunk retrieval flag,
  role-derived data-classification clearance, and configurable source-trust
  threshold before ranking. The fallback path rechecks each returned candidate
  defensively, and retrieval caches are role-scoped and versioned by the policy
  and trust threshold.
- [x] Add a versioned `source_trust` record at the pre-embedding evidence
  boundary. It records provenance type, trust/injection/poisoning scores,
  approval timestamps, security status, and non-sensitive risk signals.
  Instruction-heavy, system-message/policy/tool-schema, and hidden-Unicode
  content is quarantined before vector creation, emits an attributed audit
  event, and cannot pass the shared retrieval policy even if stale chunks exist.
- [x] Preserve extracted-media provenance for poisoning detections. Instruction
  text from image or PDF extraction now records an explicit non-content signal,
  is quarantined before embeddings persist, and carries that signal into the
  source-trust audit trail for review.
- [x] Treat repeated identical source bodies as a duplicate-flooding signal.
  Repeated submissions are quarantined before vector creation; eligible results
  pass a shared secure-ranking stage before SQL/Python candidate truncation and
  reranking. It drops explicitly unsafe metadata and records source-risk and
  cross-source duplicate penalties, preventing a small duplicate cluster from
  dominating synthesis context.
- [x] Normalize every memory write with a versioned secure-memory record:
  origin, source IDs, content hash, trust/security status, approval state,
  contradiction references, and verification time. Evidence-derived agent
  memory cannot become active directly; it is proposed for approval. Memory
  recall is fail-closed for missing security metadata and returns only active,
  approved, sufficiently trusted records with an Inspect-visible exclusion
  reason for every rejected item.
- [x] Make approval mandatory for every agent-origin durable-memory write,
  independent of a caller-selected direct write policy or forged approval and
  trusted-projection fields. Agent proposals stay out of workflow recall until
  the controlled approval path records review metadata.
- [x] Reserve procedural memory for versioned system code/config only. The
  durable-memory boundary rejects retrieved or agent instructions before
  persistence; an active procedure must carry system origin, a code/config
  source reference, a non-empty procedure version, and a read-only policy.
- [x] Preserve the active memory version when a proposed update for the same
  entity has a different content hash. The active and proposed versions receive
  reciprocal conflict links and a shared conflict group; Inspect exposes both
  versions for review. Approval is the only path that supersedes the active
  version, preserving its history and recording the reviewer and resolution
  time.
- [x] Extend source-deletion invalidation to the normalized secure-memory
  `source_ids` provenance path as well as explicit source and artifact links.
  A deleted source removes its retrieval chunks, invalidates dependent memory,
  records `requires_reverification`, and includes every stale memory item in
  the attributed deletion-propagation audit event.
- [x] Preserve a tenant-scoped non-content tombstone whenever evidence is
  deleted. It records the original source ID/type, content hash, security and
  trust state, deletion actor/time, and derivative impact while source text,
  previews, object keys, and chunks remain deleted and non-retrievable.
- [x] Enforce an eight-hour maximum TTL for working memory, persist the canonical
  expiry in secure-memory provenance, and normalize timestamp comparisons at
  the recall boundary. Expired memory cannot enter workflow context and remains
  Inspect-visible with an `expired` exclusion reason.
- [x] Bind working memory to a hashed authenticated session/token scope. Writes
  without a session fail closed; list, selection, Inspect, and direct lookup
  never expose another session's working items, preventing temporary context
  from becoming project-wide durable memory.
- [x] Restrict working memory to the transient write policy. Session context
  cannot be written with direct, approval, or derived durable-memory modes;
  combined with its bounded expiry and session scope, it remains temporary
  workflow state rather than a project-memory mutation path.
- [x] Enforce episodic-memory event integrity. Writes require attributable
  source provenance and a timezone-aware event timestamp; the timestamp is
  normalized to UTC and each episodic item receives a capped 30-day expiry so
  workflow events cannot become unbounded project memory.
- [x] Enforce semantic-memory conclusion integrity. Writes require attributable
  source provenance and confidence in the inclusive zero-to-one range; compacted
  semantic proposals retain their source-memory reference and conservatively
  use the lowest source confidence, treating missing confidence as zero.
- [x] Restrict trusted derived-memory projections to the code-owned artifact-version
  and validation-interpretation helpers. The generic writer ignores
  caller-declared projection flags, including for an otherwise permitted source
  type; only the private helper capability can mark a derived projection trusted.
  Risk projections provide explicit zero confidence because risk likelihood is
  not evidence confidence.
- [x] Enforce memory data-classification boundaries. Memory writes now persist a
  conservative classification, elevated when PII or secrets are detected; list,
  workflow selection, Inspect, direct lookup, compaction, conflicts, and
  updates reuse role clearances from `RetrievalSecurityPolicy`, with denied
  records non-enumerating and redacted in Inspect exclusions.
- [x] Enforce explicit preference confirmation. Durable preference memory now
  requires the authenticated user's confirmation, identity, and timestamp;
  the preference endpoint records attributable confirmation provenance and unconfirmed
  agent-inferred preferences are rejected instead of becoming proposals.
- [x] Gate low-trust memory at write time. A durable write below the same minimum
  trust threshold used by recall is proposal-only, so an unverified item cannot
  become active project memory merely by claiming an approved security status.
- [x] Apply secure memory-recall predicates before ordering and limits. Active,
  unexpired, approved, trusted, classification-cleared, approval-complete, and
  session-scoped candidates are now SQL-filtered before list/workflow/context
  selection, while the Python policy remains a defensive recheck with Inspect
  exclusion reasons.
- [x] Detect anomalous embedding clusters before evidence chunks are persisted.
  A distinct source whose candidate vectors nearly match two approved,
  different-content project sources receives an inspectable source-trust signal
  and is quarantined with a completed ingestion audit trail.
- [x] Add structured retrieval-sufficiency diagnostics for relevant approved
  sources, source diversity, average relevance, trusted-source ratio, and
  planned-subquestion coverage. Evidence-seeking Ask Thesys requests now
  abstain with explicit hypothesis labeling and retrieval reasons when that
  assessment is insufficient; the same fail-closed response prevents provider
  invocation after insufficient or guardrail-filtered evidence in regular and
  streamed flows.
- [x] Detect a research decision reversal that is supported by exactly one
  source added after the prior recorded decision. The controlling source now
  receives a high-risk recommendation-shift trust signal, is moved from
  retrievable to quarantined with its chunks removed, and produces an
  attributable audit event. The affected memory and decision proposals replace
  the reversal with an explicit independent-corroboration requirement.
- [x] Detect a conflicting research claim introduced by exactly one newly added
  source. The guard requires opposite polarity and strong topical overlap with
  prior supported evidence, so ordinary disagreement and multi-source claims do
  not trigger it. A detected source is quarantined and de-chunked before the
  memo version persists; its claim is retained only as unsupported without
  citations, and memory/decision proposals require independent corroboration.
- [x] Propagate evidence deletion into recorded decision dependencies. Removed
  evidence links now bring the affected decision review date forward, preserving
  its history while ensuring recommendation guidance is recalculated without the
  deleted support. The deletion audit records the invalidated links and decisions
  requiring review alongside stale claims and memory.
- [x] Treat source quarantine as dependency invalidation, not just chunk removal.
  When a previously usable source is blocked for a trust signal, linked claims,
  decisions, and durable memory follow the same invalidation path as deletion;
  memory becomes stale with an explicit quarantine/reverification record and the
  source-quarantine audit records its derivative impact.
- [x] Revalidate retrieval-plan cache hits against the current shared retrieval
  policy before evidence enters context. A source quarantined, revoked, or no
  longer eligible after caching cannot be replayed; cache-hit context, quality,
  and sufficiency diagnostics are recomputed from the surviving evidence.
- [x] Apply shared retrieval eligibility to evidence source content surfaces.
  Ineligible sources retain operational metadata for review, but list/detail
  responses withhold summaries, previews, and object keys; downloads are denied
  and attributed until the source becomes eligible again.
- [x] Apply the same source-content eligibility to governed project-source tools.
  Agent and MCP source listings keep source identity and security status but
  suppress summaries from quarantined or otherwise ineligible sources.
- [x] Route LangGraph source-reader retrieval through a policy-backed recent
  evidence path. It applies the shared SQL filters before ordering and repeats
  the Python eligibility check, preventing quarantined, low-trust, restricted,
  or retrieval-disabled chunks from entering research context.
- [x] Apply current shared retrieval eligibility when serializing workflow
  trace/replay output. Detail, project-list, and SSE trace surfaces now remove
  results and ingestion-step output from revoked sources, and suppress an
  associated run summary rather than replaying evidence that has since become
  quarantined or otherwise ineligible.
- [x] Apply the same workflow-trace policy to project overview activity. Recent
  strategic updates now serialize workflow summaries through the current
  eligibility check, so a source quarantined after ingestion cannot replay its
  text through the project homepage or its updates endpoint.

## Sprint 65 Verification

- [x] Focused policy, invariant, and evidence regression coverage passed (`37
  passed, 1 xfailed, 1 warning`), including SQL/Python eligibility parity for
  approved, restricted, low-trust, and retrieval-blocked sources.
- [x] Repository-wide backend lint passed and the complete backend suite passed
  (`415 passed, 1 skipped, 1 xfailed, 12 warnings`).
- [x] Source-trust/quarantine checkpoint passed (`48 passed, 1 xfailed, 1
  warning`); repository-wide lint and the full backend suite passed (`417
  passed, 1 skipped, 1 xfailed, 12 warnings`).
- [x] Duplicate-flooding and secure-ranking checkpoint passed (`55 passed, 1
  warning`); repository-wide lint and the full backend suite passed (`419
  passed, 1 skipped, 1 xfailed, 12 warnings`).
- [x] Secure-memory write/recall checkpoint passed (`91 passed, 1 xfailed, 1
  warning`); repository-wide lint and the full backend suite passed (`422
  passed, 1 skipped, 1 xfailed, 12 warnings`).
- [x] Conflict-safe memory-version checkpoint passed (`92 passed, 1 xfailed, 1
  warning`); repository-wide lint and the full backend suite passed (`423
  passed, 1 skipped, 1 xfailed, 12 warnings`).
- [x] Secure-memory source-invalidation checkpoint passed (`32 passed, 1
  xfailed, 1 warning`); repository-wide lint and the full backend suite passed
  (`423 passed, 1 skipped, 1 xfailed, 12 warnings`).
- [x] Secure-memory expiry checkpoint passed (`93 passed, 1 xfailed, 1
  warning`); repository-wide lint and the full backend suite passed (`424
  passed, 1 skipped, 1 xfailed, 12 warnings`).
- [x] Anomalous embedding-cluster checkpoint passed (`28 passed, 1 xfailed, 1
  warning`); repository-wide lint and the full backend suite passed (`425
  passed, 1 skipped, 1 xfailed, 12 warnings`).
- [x] Retrieval-sufficiency and Guide abstention checkpoint passed (`90 passed,
  1 warning`), covering the structured assessment, normal Guide abstention,
  SSE abstention, and the stronger provider-free response after indirect
  injection removes all usable evidence.
- [x] Application lint and compile checks passed, and the full backend suite
  passed (`428 passed, 1 skipped, 1 xfailed, 12 warnings`). Repository-root
  lint remains limited by 12 pre-existing line-length violations in historical
  Alembic migrations outside this sprint slice.
- [x] One-source recommendation-shift checkpoint passed (`97 passed, 4
  warnings`), covering source-trust scoring, secure ingestion lifecycle
  transition, agentic-research decision-proposal abstention, and the existing
  evidence, governance, and feature-boundary regressions.
- [x] Application lint and compile checks passed, and the full backend suite
  passed (`430 passed, 1 skipped, 1 xfailed, 12 warnings`). Repository-root
  lint remains limited by 12 pre-existing line-length violations in historical
  Alembic migrations outside this sprint slice.
- [x] Single-source conflicting-claim checkpoint passed (`11 passed, 1
  warning`) across source-trust and agentic-research regressions. Application
  lint and compile checks passed, and the full backend suite passed (`432
  passed, 1 skipped, 1 xfailed, 12 warnings`). Repository-root lint remains
  limited by 12 pre-existing line-length violations in historical Alembic
  migrations outside this sprint slice.
- [x] Source-deletion decision-dependency checkpoint passed (`27 passed, 1
  warning`) across source deletion, evidence, and decision regressions, with
  changed-file lint and compile checks clean.
- [x] Retrieval-cache policy-recheck checkpoint passed (`18 passed, 1 warning`)
  across policy, retrieval, and secure-ranking regressions, with changed-file
  lint and compile checks clean.
- [x] Source-content eligibility checkpoint passed (`32 passed, 1 warning`) across
  source trust, evidence, and object-storage regressions, with changed-file lint
  and compile checks clean.
- [x] Governed-tool/MCP source-listing checkpoint passed (`26 passed, 1 warning`)
  across tool-boundary, JSON-RPC adapter, and source-trust regressions, with
  changed-file lint and compile checks clean.
- [x] LangGraph source-reader policy checkpoint passed (`9 passed, 1 warning`)
  across retrieval-policy, agentic-research, and secure-ranking regressions,
  with changed-file lint and compile checks clean.
- [x] Workflow trace/replay policy checkpoint passed (`26 passed, 1 warning`)
  across evidence, workflow-event, retrieval-policy, and workflow-scope
  regressions; changed-file compile checks and repository application lint
  passed.
- [x] Source-quarantine dependency-invalidation checkpoint passed (`10 passed,
  1 warning`) across source-trust, real agentic-research quarantine, and source
  deletion-propagation regressions; changed-file compile checks and repository
  application lint passed.
- [x] Agent-memory approval-bypass checkpoint passed (`63 passed, 1 warning`)
  across memory-service and feature-boundary coverage; changed-file compile
  checks and repository application lint passed.
- [x] Code-owned procedural-memory checkpoint passed (`64 passed, 1 warning`)
  across memory-service and feature-boundary coverage; changed-file compile
  checks and repository application lint passed.
- [x] Project-overview trace replay checkpoint passed (`24 passed, 1 warning`)
  across project-overview, evidence, and workflow-event coverage; changed-file
  compile checks and repository application lint passed.
- [x] Session-scoped working-memory checkpoint passed (`75 passed, 1 warning`)
  across memory-service, context-compiler, and feature-boundary coverage;
  changed-file compile checks and repository application lint passed.
- [x] Episodic-memory integrity checkpoint passed (`76 passed, 1 warning`)
  across memory-service, context-compiler, and feature-boundary coverage;
  focused policy coverage, changed-file compile checks, and repository
  application lint passed.
- [x] Semantic-memory integrity checkpoint passed (`77 passed, 1 warning`)
  across memory-service, context-compiler, and feature-boundary coverage;
  changed-file compile checks and repository application lint passed.
- [x] Memory-classification checkpoint passed (`82 passed, 1 warning`) across
  memory-service, context-compiler, feature-boundary, and retrieval-policy
  coverage; changed-file compile checks and repository application lint passed.
- [x] Preference-confirmation checkpoint passed (`89 passed, 1 warning`) across
  memory-service, context-compiler, feature-boundary, route-contract, and
  cache coverage; changed-file compile checks and repository application lint
  passed.
- [x] Working-memory write-policy checkpoint passed (`79 passed, 1 warning`)
  across memory-service, context-compiler, and feature-boundary coverage;
  changed-file compile checks and repository application lint passed.
- [x] Low-trust memory checkpoint passed (`80 passed, 1 warning`) across
  memory-service, context-compiler, and feature-boundary coverage; changed-file
  compile checks and repository application lint passed.
- [x] Embedded-media poisoning checkpoint passed (`80 passed, 2 warnings`)
  across source-trust, image-upload, evidence-ingestion, and feature-boundary
  coverage; changed-file compile checks and repository application lint passed.
- [x] Source-deletion tombstone checkpoint passed (`93 passed, 1 xfailed, 1
  warning`) across deletion propagation, security invariants, evidence, and
  feature-boundary coverage; changed-file compile checks and repository
  application lint passed.
- [x] Pre-limit memory-recall checkpoint passed (`81 passed, 1 warning`) across
  memory-service, context-compiler, and feature-boundary coverage; changed-file
  compile checks and repository application lint passed.
- [x] Trusted derived-projection checkpoint passed (`99 passed, 1 warning`) across
  memory-service, context-compiler, feature-boundary, agentic-research, and
  validation coverage; changed-file lint and compile checks passed.
- [x] Code-owned trusted-projection capability checkpoint passed (`99 passed, 1
  warning`) across memory-service, context-compiler, feature-boundary,
  agentic-research, and validation coverage; changed-file lint and compile
  checks passed.

## Sprint 66 Progress

- [x] Establish the OPA policy-as-code foundation: the repository now has the
  required default-deny tool-access, memory-write, model-routing, data-access,
  approval, and egress policy packages; local compose runs the OPA sidecar. A
  typed HTTP evaluator validates every response shape and maps unavailable or
  malformed policy decisions to a fail-closed privileged-operation denial.
- [x] Route governed tool execution and persisted proposal creation through the
  OPA `tool_access` decision after tenant, role, and schema validation and
  before a `ToolInvocation` is stored. Denials and accepted decisions are
  audited with the typed policy result; unavailable OPA and unimplemented
  approval-required execution paths deny before side effects. MCP proposal
  calls pass their request settings through the same boundary. Local Compose
  enables the boundary by default, while staging and production enforce it even
  without the local switch.
- [x] Route durable-memory creation and content updates through the OPA
  `memory_write` decision before persistence. The typed policy input carries
  principal, project, memory type/write policy, origin, source, and data
  classification; denials and unavailable OPA fail closed with an audit event,
  while approval-required decisions force pending proposal status. Trusted
  derived projections and versioned code/config procedural memory retain their
  existing narrowly-scoped paths through explicit policy rules.
- [x] Route memory lifecycle mutations (approval, rejection, stale/archive,
  merge, and conflict resolution) through the same OPA decision. Lifecycle
  operations declare their affected-record count; OPA limits multi-item
  approval, merge, and conflict resolution before mutations, and every allowed
  or denied lifecycle action is attributable to the reviewing user in audit
  metadata.
- [x] Make the local registry the secure tool-manifest authority. Every tool
  now declares a version, required scopes, data classifications, egress
  destinations, timeout, output/record limits, reversibility, and owner;
  malformed manifests fail closed before discovery or invocation. Shared input
  and output guards enforce manifest record and byte limits, OPA receives the
  same manifest fields, and API/MCP discovery exposes the approved contract.
- [x] Establish owner-reviewed external MCP server registrations as tenant-scoped
  RLS records. Normal users cannot register servers; registrations require a
  configured HTTPS host, no embedded credentials or nonstandard port, a pinned
  SHA-256 server fingerprint, and locally approved tool names with snapshots.
  They are persisted disabled by default and emit a high-risk audit event.
- [x] Establish a durable workspace emergency-control plane for all six required
  kill switches. Owners can change a tenant-scoped RLS record at runtime, every
  effective state is available through the owner/admin security endpoint, and
  each material change emits a high-risk audit event. Deployment environment
  variables remain visible global fail-closed overrides.
- [x] Enforce the model-provider and external-egress kill switches in the shared
  expensive-workflow boundary before rate, budget, or provider work starts.
  The control recognizes the configured LiteLLM target plus any non-loopback
  provider endpoint, emits the existing attributed policy-denial audit event,
  and returns a generic 403 without creating an AI run.
- [x] Enforce the source-fetching kill switch before URL and discovered-source
  ingestion can create source state, before source discovery can create an AI
  run, and within the external-search adapter itself. Each denial returns a
  generic 403 and records the attributable policy-denial event; existing ready
  sources remain readable without a network request.
- [x] Enforce the memory-write kill switch at the central durable-memory
  boundary, covering content upserts and all lifecycle mutations before they
  persist. Each denial returns a generic 403 and emits an attributable
  policy-denial event; conflict inspection remains read-only while disabled.
- [x] Enforce the all-agent-writes kill switch at the governed tool boundary.
  Agent-originated proposal and write-capability invocations now deny before
  schema, OPA, invocation, or approval persistence, with a generic 403 and
  attributable policy-denial audit. Agent read tools and human-originated
  proposal review remain available.
- [x] Enforce the external-MCP kill switch at the remote registration boundary.
  New remote server registrations now deny with a generic 403 and attributable
  policy-denial audit; existing registrations remain disabled by default. There
  is no outbound remote-MCP execution path yet, and any later invocation work
  must apply the same guard before it can open a connection.
- [x] Add owner-reviewed streamable-HTTP remote-MCP enablement. A fresh review
  verifies the pinned TLS certificate fingerprint, approved server version,
  and complete compatible `tools/list` manifest before setting a registration
  enabled; any unavailable, identity, version, or schema drift leaves it
  disabled and records an attributable high-risk audit event. OAuth
  client-credentials registrations remain disabled until their secure token
  exchange is configured; SSE registrations remain disabled until their
  transport implementation exists.
- [x] Add encrypted, per-server MCP credential isolation. Owner-only endpoints
  store either short-lived user-delegated access/refresh tokens or a
  client-credentials secret under workspace envelope encryption bound to the
  exact registration; issuer and audience must match the reviewed server,
  metadata never returns secret material, and audited revocation deletes the
  credential and disables the server.
- [x] Use the registration-scoped, user-delegated access token during live
  remote-MCP enablement. The review client sends it only to that server for its
  TLS-pinned `initialize` and `tools/list` preflight; no token reaches another
  registration, audit event, or API response. Token refresh remains disabled
  until its validated OAuth lifecycle is added.
- [x] Add the protocol-level outbound remote-MCP invocation client. It refuses
  disabled registrations and unapproved tool names, validates the approved
  input schema before egress, then uses one TLS-pinned MCP session for fresh
  `initialize`, `tools/list`, and `tools/call` checks. Only schema-valid
  `structuredContent` matching the reviewed output contract is returned; this
  internal client has no public route until it is integrated with project RBAC,
  OPA, approvals, redaction, and audit.
- [x] Integrate reviewed remote MCP read tools into the governed project-tool
  pipeline. Each remote read now performs tenant/project/RBAC/schema/OPA checks
  and size limits before the call, uses only its registration-scoped credential,
  redacts and persists the returned output through the normal invocation path,
  and records both the standard outcome and a high-risk remote-server audit.
  The MCP and general external-egress emergency switches deny before invocation
  persistence; any remote review or invocation failure disables the server.
  Remote proposal and write tools remain disabled until their approved-execution
  lifecycle is implemented.
- [x] Cryptographically validate user-delegated remote-MCP access tokens before
  they can reach a remote server. The verifier only fetches discovery/JWKS data
  from the reviewed issuer host, requires an asymmetric signed JWT with a known
  key, exact issuer/audience/scopes, subject, and at-most-one-hour lifetime.
  Enablement and runtime use only this validated registration-scoped token;
  opaque, symmetric, overlong, malformed, mismatched, and untrusted-JWKS tokens
  fail closed without leaking token material.
- [x] Add a client-credentials token exchange for reviewed remote MCP servers.
  OAuth discovery and the token endpoint must remain on the reviewed issuer
  host; the exchange uses HTTP Basic authentication, accepts only a bounded
  bearer response, persists no access token, and cryptographically validates
  the resulting registration-scoped JWT before use.
- [x] Add user-delegated refresh-token rotation for reviewed remote MCP servers.
  Credentials now bind a public OAuth client ID; after access expiry the app
  sends only that registration's refresh grant to the reviewed issuer-host token
  endpoint, validates the returned JWT, rotates encrypted access/refresh
  material when provided, updates expiry, and emits a credential-free high-risk
  audit event.
- [x] Add initial user-delegated OAuth 2.1 authorization-code-with-PKCE
  acquisition. Owner-only start and completion endpoints bind a static HTTPS
  redirect URI, public client ID, reviewed issuer/audience, and least-privilege
  scopes to an encrypted, tenant- and user-scoped, 10-minute transaction. The
  database stores only a state digest and envelope-encrypted verifier; completion
  consumes the transaction before issuer exchange, validates the returned JWT
  and refresh token, persists credentials through the existing per-server
  boundary, and rejects replay. Both steps honor external MCP/egress switches
  and emit credential-free high-risk audits.
- [x] Enable reviewed remote MCP proposal previews. Locally approved proposal
  manifests are now allowed through the same tenant, policy, egress, fresh
  schema review, scoped-credential, output-redaction, and audit boundary as
  remote reads; their returned preview is stored as a pending human approval.
  Direct remote write manifests remain denied before persistence or egress.
- [x] Execute approved remote MCP writes through a separate, terminal lifecycle.
  A write first stores a redacted consequence preview, reviewed server ID, and
  per-invocation idempotency key with a pending approval; it cannot reach the
  server until a qualified user approves. Approval rechecks policy and kill
  switches, commits the approval before exactly one reviewed remote dispatch,
  sends the key in MCP metadata, validates/redacts output, and records
  before/after audits. Ambiguous failures become terminal and cannot be
  approved or automatically dispatched again.
- [x] Add the reviewed legacy HTTP+SSE MCP transport. A registration-scoped
  authenticated SSE session must first receive an `endpoint` event; the
  advertised POST URL is constrained to the registered HTTPS origin before any
  credential can be sent. Each MCP JSON-RPC request then receives an exact,
  bounded SSE `message` response, while notifications are harmlessly ignored.
  The existing TLS pinning, fresh `initialize`/`tools/list` review, approved
  schema checks, idempotency metadata, output validation, and fail-closed error
  behavior apply unchanged.
- [x] Validate the mounted OPA policy bundle with the Compose-pinned OPA 0.67.0
  runtime. Strict Rego parsing and bundle construction pass, and a local
  `opa run --server` instance returns the complete typed allow and default-deny
  decisions for all six mounted packages. This found and removed an unmatched
  brace that would otherwise have prevented the policy sidecar from starting.

## Sprint 66 Verification

- [x] OPA policy-client, tool-boundary, and security-governance checkpoint
  passed (`61 passed, 1 xfailed, 4 warnings`); changed-file lint, compile
  checks, and `git diff --check` passed.
- [x] Memory-policy, typed-memory, and feature-boundary checkpoint passed
  (`104 passed, 1 xfailed, 1 warning`); changed-file lint, compile checks, and
  `git diff --check` passed.
- [x] Memory lifecycle OPA checkpoint passed (`66 passed, 1 xfailed, 1
  warning`); changed-file lint, compile checks, and `git diff --check` passed.
- [x] Secure-manifest, MCP, tool-boundary, and security-invariant checkpoint
  passed (`105 passed, 1 xfailed, 1 warning`); application lint and
  `git diff --check` passed.
- [x] MCP registration, adapter, tool-boundary, and security-invariant
  checkpoint passed (`57 passed, 1 xfailed, 1 warning`); application lint,
  Alembic single-head verification, and `git diff --check` passed. Alembic
  autogeneration comparison remains unavailable because local Postgres runtime
  credentials are rejected.
- [x] Kill-switch control-plane, MCP registration, and security-invariant
  checkpoint passed (`29 passed, 1 xfailed, 1 warning`); focused lint, Alembic
  single-head and offline SQL rendering verification, and `git diff --check`
  passed. Alembic autogeneration comparison remains unavailable because local
  Postgres runtime credentials are rejected.
- [x] Shared-workflow kill-switch checkpoint passed (`67 passed, 1 xfailed, 4
  warnings`) across security governance, control-plane, tool, MCP-registration,
  and security-invariant coverage; focused lint, compilation, and `git diff
  --check` passed.
- [x] Source-fetch kill-switch checkpoint passed (`106 passed, 1 xfailed, 4
  warnings`) across evidence, discovery, competitor, agentic-research, security
  governance, provider-routing, tool, control-plane, and security-invariant
  coverage; focused lint, compilation, and `git diff --check` passed.
- [x] Memory-write kill-switch checkpoint passed (`108 passed, 1 xfailed, 4
  warnings`) across memory-service, security-governance, tool-boundary,
  agentic-research, context-compiler, control-plane, and security-invariant
  coverage; focused lint, compilation, and `git diff --check` passed.
- [x] Agent-write kill-switch checkpoint passed (`83 passed, 1 xfailed, 4
  warnings`) across tool-boundary, MCP-adapter, agentic-research,
  security-governance, control-plane, and security-invariant coverage; focused
  lint, compilation, and `git diff --check` passed.
- [x] External-MCP kill-switch checkpoint passed (`57 passed, 1 xfailed, 1
  warning`) across MCP registration, MCP adapter, tool-boundary, control-plane,
  and security-invariant coverage; focused lint, compilation, and `git diff
  --check` passed.
- [x] Remote-MCP enablement checkpoint passed (`65 passed, 1 xfailed, 1
  warning`) across remote review, MCP registration, MCP adapter, tool-boundary,
  control-plane, API-contract, and security-invariant coverage; focused lint,
  compilation, and `git diff --check` passed.
- [x] Encrypted MCP-credential checkpoint passed (`60 passed, 1 xfailed, 1
  warning`) across credential storage, MCP registration/review/adapter,
  kill-switch, envelope-encryption, and security-invariant coverage; focused
  lint, compilation, Alembic single-head/offline SQL rendering, and `git diff
  --check` passed.
- [x] Scoped-token review checkpoint passed (`60 passed, 1 xfailed, 1 warning`)
  across MCP credential, registration, remote-review, adapter, kill-switch,
  envelope-encryption, and security-invariant coverage; focused lint,
  compilation, and `git diff --check` passed.
- [x] OAuth authorization-code PKCE checkpoint passed (`42 passed, 1 xfailed,
  1 warning`) across remote token, MCP credential, and security-invariant
  coverage; changed-file lint/format, Alembic single-head/offline SQL rendering,
  and `git diff --check` passed.
- [x] Approved remote-write checkpoint passed (`72 passed, 4 warnings`) across
  tool-boundary, MCP-adapter, security-governance, remote-review, and
  registration coverage; changed-file lint/format, Alembic single-head/offline
  SQL rendering, and `git diff --check` passed.
- [x] Compose-pinned OPA 0.67.0 parser/runtime checkpoint passed: strict Rego
  parsing, bundle construction, and REST decision evaluation for allow and
  default-deny paths across all six mounted policy packages passed. The local
  workspace still has no Docker CLI, so full Compose graph rendering remains a
  deployment-environment verification item.

## Sprint 67 Progress

- [x] Establish the normalized, tenant/RLS-scoped security-event foundation.
  `security_events` now persists redacted severity/source, event type, summary,
  containment status, and bounded request, session, AI, trace, workflow, tool,
  approval, and audit correlation identifiers. Every high-risk audit record is
  projected into this stream in the same transaction, so existing guardrail,
  tool, and MCP high-risk paths become queryable by workspace owners and admins
  through the governed project endpoint. Retention now purges the correct event
  type with the worker's narrowly scoped delete grant.
- [x] Add actionable high-severity alerting and the first anomaly detection.
  Every high or critical security event now opens a tenant/RLS-scoped alert with
  a disposition lifecycle for later incident handling. Repeated blocked prompt
  injection, jailbreak, or system-prompt extraction attempts from the same
  actor within a configured window produce one critical, attributable escalation
  event and alert. Workspace owners and admins can query the redacted alert
  queue per project.
- [x] Establish a durable, immutable workflow security-budget contract.
  Each research sprint snapshots all required model, tool, external-query,
  retrieval, token, cost, duration, memory-proposal, structured-repair,
  critique-loop, repeated-identical-tool, alternating-tool-cycle, and
  repeated-retrieval-query limits before durable execution.
  The snapshot is visible through the sprint API, persists across
  retries/configuration changes, travels with the Temporal payload, and
  constrains its execution timeout by the configured workflow duration limit.
- [x] Enforce the sprint-scoped tool-call budget at the shared governed tool
  boundary. Direct local calls, reviewed remote MCP calls, and approval-gated
  proposals lock and count durable tool invocations before any tool preparation
  or external effect. Exhaustion stops the workflow with the prescribed safe
  response, records a high-risk audit event, and produces the normalized
  workflow security event and alert. The default ceiling is 32 calls so the
  standard multi-stage agentic research workflow can complete while retaining a
  strict finite limit.
- [x] Enforce the sprint-scoped retrieved-chunk budget before governed
  retrieval. Every evidence search locks the workflow budget, counts the
  already persisted returned chunks, caps the next request and returned output
  to the remaining allowance, and safely stops once it is exhausted. The denial
  emits a high-risk audit record plus the normalized workflow security event and
  alert, including the configured and observed chunk totals.
- [x] Enforce the sprint-scoped memory-proposal budget at both governed proposal
  entry points. Direct/MCP proposal calls and agent-created proposal helpers now
  count every durable `propose_memory_update` attempt before creating an
  approval request, including proposals later approved or rejected. Exhaustion
  safely stops the workflow and records a high-risk audit, normalized workflow
  security event, and alert with configured and observed proposal totals.
- [x] Enforce the sprint-scoped external-query budget before source-discovery
  provider search. Each batch durably reserves only its remaining cleaned query
  allowance under the locked sprint budget before egress, so failures and
  retries cannot evade the limit. Exhaustion prevents another provider call and
  records the configured and observed query counts in the high-risk audit,
  normalized workflow security event, and alert.
- [x] Meter real research-sprint model calls at the shared LiteLLM gateway.
  Context-scoped sprint budgets are bound around source discovery, competitor
  discovery, and agentic memo synthesis and reserve a durable `model_calls`
  count under the sprint lock immediately before every non-streaming or
  streaming provider request. Structured-output repair calls naturally take
  separate reservations. Exhaustion prevents provider egress and emits the
  configured and observed totals through the high-risk workflow audit,
  normalized security event, and alert.
- [x] Enforce actual token and provider-cost limits at that same gateway. After
  every real completion, returned token usage and LiteLLM response cost are
  durably accumulated under the locked sprint before a workflow can consume the
  result. A response that crosses either immutable total persists its usage,
  records the configured and observed total in the high-risk workflow audit,
  normalized security event, and alert, and safely stops downstream workflow
  writes. Streamed requests also account for reported response cost when scoped.
- [x] Enforce structured-output repair limits at the shared retry loop. Every
  repair reservation locks and increments the sprint before another provider
  request, so a malformed response cannot create an unbounded correction loop.
  Exhaustion prevents the next repair call and emits the configured and observed
  totals through the high-risk workflow audit, normalized security event, and
  alert.
- [x] Enforce agentic-research critique-loop limits before the governed critic
  stage. Each critique reserves durable sprint usage before citation review;
  exhaustion stops the graph before the memo-writing stage and records the
  configured and observed totals in the high-risk workflow audit, normalized
  security event, and alert.
- [x] Detect repeated identical sprint-scoped tool invocations at the shared
  governed boundary. A canonical SHA-256 digest of redacted, schema-validated
  input is compared under the locked durable sprint budget before a local call,
  remote-MCP preparation, or approval-gated proposal is persisted. The default
  allows five matching calls; the next one safely stops with a high-risk audit,
  normalized workflow security event, and alert that retain only the digest and
  configured/observed counts.
- [x] Detect alternating sprint-scoped tool cycles before the second invocation
  can complete an over-limit pair. The governed execution and proposal paths
  lock the durable cycle limit, compare only recent tool names, and stop the
  next completed cycle with a high-risk audit, normalized workflow security
  event, and alert containing the cycle names and configured/observed counts.
- [x] Detect repeated equivalent sprint-scoped retrieval queries before the
  retrieval service runs. Validated query semantics are normalized across case,
  whitespace, source-type ordering, and `top_k` pagination, then compared by
  SHA-256 fingerprint under the locked durable limit. Exhaustion safely stops
  before another retrieval invocation or result persistence and emits a
  high-risk audit, normalized workflow security event, and alert with only the
  digest and configured/observed counts.

## Next Sprint

Continue Sprint 67 with the remaining loop and anomaly detection rules,
operational metrics, dashboard, and incident-response requirements.

Sprint 41-50 delivered the portfolio baseline but left production-grade gaps.
The follow-up audit and next ordered upgrade backlog are captured in
`IMPLEMENTATION_BRIEF.md` under "Post-Sprint 50 Audit and Future Upgrade
Backlog." The execution-level handoff is `SPRINT_51_60_TODO.md`, which now
contains a gap coverage ledger, deferred verification list, and specific
acceptance work for each remaining sprint. It also assigns stable work-item IDs
(`G41-*` through `G50-*`) to every remaining Sprint 41-50 carry-forward so the
final sprint audit can record `implemented`, `intentionally out of V1`, or
`future owner` status for each gap. The TODO also includes residual routing for
completed Sprints 51-58, a file-level Sprint 59 cleanup punch list,
step-by-step Sprint 60 pickup notes, an audit gap crosswalk, a per-sprint
completion-gate table, and a per-ID pickup checklist. Each unfinished gap now
has an exact owner, edit target, status update, verification bar,
blocker-recording rule, and completion disposition.

Current branch status: Sprints 51-60 are implemented on this branch. Sprint 58 closes the local document-AI gap with
parser/snapshot metadata, deterministic OCR and table extraction, quote provenance,
source-quality weighting, enriched citation metadata, collapsed Inspect
surfaces, and fixture-backed extraction evals. Live Tavily and multimodal
provider QA remain opt-in and surface explicit unavailable warnings when
credentials or egress are not configured. Sprint 60 resolves the remaining
document-intelligence carry-forwards by recording final dispositions:
deterministic parser fallback is the V1 path, true screenshot/page artifact
storage and screenshot-region OCR/table provenance are intentionally out of V1,
and live-provider plus browser QA checks have exact future-owner blockers.
Sprint 60 also adds the carried-gap audit that records `implemented`,
`intentionally out of V1`, or `future owner` status for every Sprint 41-50 gap.

Completion semantics: checked Sprint 51-58 implementation items show that code
landed on this branch, but they do not fully close the original Sprint 41-50
gaps. The `G41-*` through `G50-*` work items in `SPRINT_51_60_TODO.md` are the
source of truth. Each must receive an `implemented`,
`intentionally out of V1`, or `future owner` disposition with source/docs and
verification output or exact blocker before the branch can claim full gap
closure.

Latest planning patch: `SPRINT_51_60_TODO.md` and `IMPLEMENTATION_BRIEF.md`
now include explicit Sprint 51-60 completion gates and status terms. A checked
Sprint 51-58 item means code-landed, not gap-closed. The original Sprint 41-50
gap is not closed until every related `G41-*` through `G50-*` item has a final
disposition row with source/doc links, verification output or exact blocker
text, and a future owner when deferred. The TODO also replaces misleading
"close gaps" checked items with "land code for..." wording and keeps the final
docs, browser QA, provider QA, hosted smoke, audit output, and honest-limit work
assigned to the exact `S59-R*` or `S60-P*` package.

Latest gap-capture patch: the TODO now defines a `Gap Capture Control` rule so a
Sprint 41-50 gap is not considered captured unless it has a stable `G*` ID, an
audit-crosswalk row, an owning Sprint 59/60 queue row with concrete edit targets
and verification, and a required final disposition row in this file. It also
adds a `Sprint 59 Row Closure Checklist` with the exact service entrypoints,
private helpers, feature-module targets, service-owned side effects, and package
map rows required for `S59-R1` through `S59-R10`, plus a `Sprint 60 Required
Artifact Checklist` that requires named docs, README links, status rows, and
verification or exact blockers for `S60-P1` through `S60-P10`.

Latest sprint-pickup patch: `SPRINT_51_60_TODO.md` now has a
`Gap-Patching Rule for Completed Sprints`, and the Sprint 60 pickup queue has
been expanded so each `S60-P*` row names the exact `G*` IDs, doc/source targets,
commands to run, browser/provider/audit checks to complete or block, status rows
to write, and README/portfolio claim impact. The implementation brief mirrors
this rule: a Sprint 60 package is not complete until its owning doc or source
artifact, README/navigation language, and all related `IMPLEMENTATION_STATUS.md`
rows are updated together.

Latest Sprint 59 closeout patch: `docs/BACKEND_FEATURE_PACKAGE_MAP.md` now
includes shared duplication disposition, intentionally centralized services and
models, and a future cleanup backlog. `SPRINT_51_60_TODO.md` marks `S59-R8` and
`S59-R9` closed at the row level because context/memory ownership and
duplication decisions are now recorded with service-owned boundaries. `S59-R10`
now records the final package-map closeout verification: focused R8/R9 tests,
full backend pytest, ruff, compileall, feature-boundary check, quality gate,
diff check, conflict-marker scan, and `__pycache__` cleanup.

Latest Sprint 59 row-closure patch: the authoritative
`Sprint 59 Row Closure Checklist` in `SPRINT_51_60_TODO.md` now has no unchecked
`S59-R*` items. `S59-R1` explicitly defers broader retrieval execution DTOs to
future cleanup while marking SQL/vector execution, cache lookup/invalidation,
embedding similarity, candidate loading, citation persistence, and route
orchestration service-owned. `S59-R2` records evidence ingestion/storage/
security-event boundaries as service-owned. `S59-R3` records validation
experiment-result parsing, broader validation DTOs, DB-backed proposal
orchestration, provider calls, approvals, memory writes, confidence mutation,
and DB commits as service-owned or future cleanup. `S59-R4` records the
research graph review and keeps LangGraph, Temporal, DB, tool, provider, and
approval side effects service-owned.

Latest sprint-specific gap patch: `SPRINT_51_60_TODO.md` and
`IMPLEMENTATION_BRIEF.md` now make the incomplete validation/decision cleanup
work explicit in `S59-P2` and `S59-R3`. The sprint docs distinguish the
implemented validation interpretation fallback, mission-context projection,
prompt payloads, proposed-update payloads, weak-evidence labels, rejection
tests, and generation prompt/fallback helpers from the still-open
experiment-result parsing, broader validation DTOs, DB-backed decision proposal
boundaries, audit/proposal helpers, and service-owned provider/approval/memory/
confidence/DB orchestration.

Latest no-ambiguity sprint patch: `SPRINT_51_60_TODO.md` now has a
`No-Ambiguity Sprint Pickup Contract`, and `IMPLEMENTATION_BRIEF.md` mirrors it.
Each follow-up sprint now has exact original gap IDs, first files to open,
required docs/code targets, verification commands or blocker rules, and required
`IMPLEMENTATION_STATUS.md` disposition rows. This is the pickup surface for the
previous audit concern that Sprints 41-50 were only partially complete:

| Follow-up sprint | Still-open gap IDs | Pickup package |
|---|---|---|
| Sprint 51 closeout | `G42-A` through `G42-D`, `G43-A` through `G43-D` | `S60-P2` context docs/QA and `S60-P3` memory docs/QA |
| Sprint 52 closeout | `G44-A` through `G44-D` | `S60-P4` MCP docs/smoke |
| Sprint 53 closeout | `G46-A` through `G46-D` | `S60-P6` Ask Thesys streaming docs/QA |
| Sprint 54 closeout | `G41-A` through `G41-E`, deployment portion of `G50-D` | `S60-P9` security/deployment docs/audits |
| Sprint 55 closeout | `G45-A` through `G45-D` | `S60-P5` retrieval/citation docs/evals |
| Sprint 56 closeout | `G47-A` through `G47-D` | `S60-P7` evals/observability docs/QA |
| Sprint 57 closeout | cache portions of `G45-B`, `G47-A`, `G47-C`, `G47-D` | `S60-P5` and `S60-P7` cache docs/diagnostics |
| Sprint 58 closeout | `G48-A` through `G48-E` | `S60-P8` source-intelligence dispositions/provider/browser QA |
| Sprint 59 refactor closeout | `G49-A` through `G49-E` | `S59-R1` through `S59-R10` plus final package-map closeout |
| Sprint 60 final closeout | all remaining `G41-*` through `G50-*` | `S60-P1` through `S60-P10`, starting with the final disposition table |

Do not mark any row above complete from implementation prose alone. Each gap ID
needs a source/doc link, exact command output or exact blocker, a future owner
when deferred, and a portfolio-claim consequence in this file.

Latest original-sprint gap manifest patch: `SPRINT_51_60_TODO.md` now also has
an `Original Sprint 41-50 Gap Patch Manifest`. It enumerates each partially
complete original sprint, the owning `S59-R*` or `S60-P*` pickup items, first
files to open, exact artifacts to patch, commands to run, blocker wording to
record, and status rows required before closure. This is now the first place to
look when resuming work. The manifest explicitly keeps the following gaps open:
Sprint 41 security/deployment audit and hosted posture, Sprint 42 context docs
and Inspect QA, Sprint 43 memory lifecycle/docs/QA, Sprint 44 MCP docs and live
smoke, Sprint 45 retrieval/citation docs/evals, Sprint 46 Ask Thesys web/browser
QA and event docs, Sprint 47 eval/observability runbooks and hidden report QA,
Sprint 48 source-intelligence productization/provider/browser dispositions,
Sprint 49 feature-package cleanup, and Sprint 50 post-refactor navigation,
diagrams, code docs, deployment docs, and honest-limit audit.

## Sprint 60 Final Carried-Gap Disposition

This table is the required final ledger for the Sprint 41-50 carry-forwards.
Rows marked `future owner` are deliberately not hidden: the work has a concrete
next owner, exact blocker, and portfolio-language consequence. Rows marked
`intentionally out of V1` are productization work that should not be claimed by
the portfolio V1 app.

| Gap ID | Status | Owner sprint item | Source/doc links | Verification | Blocker / future owner | Portfolio claim |
|---|---|---|---|---|---|---|
| `G41-A` | `future owner` | `S60-P9` | `docs/DEPLOYMENT_SECURITY.md`, `scripts/security_check.py`, `scripts/audit_dependencies.py` | `python3 scripts/security_check.py` ran: backend security/governance tests passed, AI quality eval scored 10/10, dependency audit returned warnings; `python3 scripts/audit_dependencies.py` repeated the dependency blockers; direct `pip-audit` returned `command not found`. | Future owner: CI/security hardening. Install `pip`/`pip-audit` in the API venv and rerun with stable npm registry access; `pnpm audit --prod` failed with registry `fetch failed`/`ECONNRESET`. | Claim repeatable security/audit gates, not a fully green strict dependency audit. |
| `G41-B` | `implemented` | `S60-P9` | `docs/DEPLOYMENT_SECURITY.md`, README security section | Security docs now list local/dev, deterministic demo, provider-backed demo, staging-like, and production-like profiles; backend security tests passed in `python3 scripts/security_check.py`. | None for V1. | Claim documented hosted-demo auth posture with dev-auth isolation. |
| `G41-C` | `implemented` | `S60-P9` | `docs/DEPLOYMENT_SECURITY.md`, README security section, auth settings and tests | Security docs cover JWT, API-key/service-key, revocation, workspace attribution, and known production limits; backend security tests passed in `python3 scripts/security_check.py`. | Managed OIDC/JWKS operations remain future production hardening, not a V1 portfolio claim. | Claim production-shaped auth boundaries; qualify OIDC/JWKS operations as future owner work. |
| `G41-D` | `implemented` | `S60-P9` | `docs/DEPLOYMENT_SECURITY.md`, URL/provider guard services, `scripts/security_check.py` | `python3 scripts/security_check.py` passed backend governance/security tests and records provider-egress/audit behavior in the gate output. | None for local V1; live-provider allowlists still require environment-specific configuration. | Claim SSRF and provider-egress guardrails with documented limits. |
| `G41-E` | `future owner` | `S60-P9` | `docs/DEPLOYMENT_SECURITY.md`, README docs navigation | Backup/restore boundaries and hosted smoke checklist are documented. | Future owner: hosted deployment owner. Hosted smoke checks require deployed infrastructure, seeded data, provider credentials, and a browser-ready web install. | Claim backup/restore and smoke runbooks, not completed hosted verification. |
| `G42-A` | `implemented` | `S60-P2` | `docs/CONTEXT_ENGINEERING.md`, `apps/api/app/services/context_service.py`, `apps/api/app/features/context/*` | `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q` passed (`60 passed, 1 warning`). | None for backend/docs. | Claim unified context engineering with source-linked owners. |
| `G42-B` | `implemented` | `S60-P2` | `docs/CONTEXT_ENGINEERING.md`, `CONTEXT_PROFILES` in `context_service.py` | Context profile inventory is documented; the same context pytest slice passed (`60 passed, 1 warning`). | None for backend/docs. | Claim workflow-specific context profiles and token budgets. |
| `G42-C` | `future owner` | `S60-P2` | `docs/CONTEXT_ENGINEERING.md`, Context Inspect UI in `apps/web/src/features/projects/project-overview.tsx` | `pnpm --filter thesys-web typecheck` could not reach TypeScript because pnpm dependency status/install repeatedly hit npm registry `ECONNRESET`; the run was stopped with SIGINT after retries. | Future owner: frontend QA. Retry web install/typecheck/test and IDE browser QA when npm registry access is stable. | Qualify Context Inspect as implemented but browser QA pending in this environment. |
| `G42-D` | `implemented` | `S60-P2` | `docs/CONTEXT_ENGINEERING.md`, `scripts/eval_ai_quality.py`, `scripts/eval_quality_gate.py` | Context eval commands, report paths, profile extension steps, and failure interpretation are documented. | None for docs/eval handoff. | Claim context eval handoff and extension guidance. |
| `G43-A` | `implemented` | `S60-P3` | `docs/MEMORY_SYSTEM.md`, `apps/api/app/services/memory_service.py`, `apps/api/app/features/memory/*` | `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q` passed (`66 passed, 1 warning`). | None for backend/docs. | Claim durable memory lifecycle beyond chat history. |
| `G43-B` | `implemented` | `S60-P3` | `docs/MEMORY_SYSTEM.md`, memory schemas and service profiles | Semantic, episodic, procedural, preference, working, and project memory types are documented with selection and context eligibility. | None for backend/docs. | Claim multiple memory flavors with workflow-aware selection. |
| `G43-C` | `implemented` | `S60-P3` | `docs/MEMORY_SYSTEM.md`, memory feature modules | "Adding a memory type" steps cover schema, service profile, review, Inspect, stale/conflict tests, and docs updates. | None for docs handoff. | Claim developer-ready memory extension path. |
| `G43-D` | `future owner` | `S60-P3` | `docs/MEMORY_SYSTEM.md`, Memory Inspect UI in `project-overview.tsx` | Backend memory tests are part of Sprint 60 verification; browser QA is blocked by the same npm registry `ECONNRESET` failures that blocked web typecheck/tests. | Future owner: frontend QA after stable web dependency install. | Qualify Memory Inspect as implemented with browser QA pending. |
| `G44-A` | `implemented` | `S60-P4` | `docs/MCP_INTEGRATION.md`, `apps/api/app/mcp/adapter.py`, `apps/api/app/features/mcp/protocol.py` | `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_feature_package_boundaries.py -q` passed (`67 passed, 1 warning`). | None for local protocol/docs. | Claim MCP-shaped JSON-RPC over governed tools. |
| `G44-B` | `implemented` | `S60-P4` | `docs/MCP_INTEGRATION.md`, `scripts/mcp_stdio_server.py` | Stdio and HTTP/SSE commands, client config, env vars, auth headers, and project scoping are documented. | None for docs. | Claim integration-ready MCP docs and client setup. |
| `G44-C` | `future owner` | `S60-P4` | `docs/MCP_INTEGRATION.md`, `scripts/eval_mcp_contract.py`, `scripts/mcp_stdio_server.py` | Backend MCP/tool tests passed (`67 passed, 1 warning`); live stdio/API smoke needs a running API and seeded project ID. | Future owner: integration QA. Run read/proposal/denied-write/invalid-param smoke commands against a live project. | Claim governed MCP adapter; qualify live-client smoke as pending. |
| `G44-D` | `implemented` | `S60-P4` | `docs/MCP_INTEGRATION.md`, README docs navigation | No new homepage or primary-workflow settings surface was added; MCP integration remains in docs/API paths and advanced developer setup. | None. | Claim MCP is hidden from the main workflow unless explicitly configured. |
| `G45-A` | `implemented` | `S60-P5` | `docs/RETRIEVAL_AND_CITATIONS.md`, retrieval service and feature modules | Retrieval/citation pytest slice passed (`67 passed, 1 warning`); `python3 scripts/eval_retrieval_quality.py` passed (`7/7`). | None for local V1. | Claim source-linked multi-stage retrieval and citation pipeline. |
| `G45-B` | `implemented` | `S60-P5` | `docs/RETRIEVAL_AND_CITATIONS.md`, retrieval/reranker/cache services | Ranking limits, Postgres `ts_rank` behavior, BM25-like fallback, reranker extension, cache keys, and invalidation inputs are documented. | None for docs/local behavior. | Claim hybrid retrieval with honest ranking and cache limits. |
| `G45-C` | `implemented` | `S60-P5` | `docs/RETRIEVAL_AND_CITATIONS.md`, citation verifier feature modules | Citation verifier ownership matrix, unsupported/weak claim handling, and extension steps are documented. | None. | Claim artifact-aware citation verification and unsupported-claim handling. |
| `G45-D` | `implemented` | `S60-P5` | `docs/RETRIEVAL_AND_CITATIONS.md`, `scripts/eval_retrieval_quality.py` | `python3 scripts/eval_retrieval_quality.py` passed (`7/7`) with precision/recall proxies, citation support, stale-source, and prompt-injection checks. | None for local evals. | Claim repeatable retrieval/citation quality evals. |
| `G46-A` | `implemented` | `S60-P6` | `docs/ASK_THESYS_STREAMING.md`, `apps/api/app/services/guide_service.py`, `apps/api/app/features/guide/events.py` | Stream event names, ordering, payload IDs, final-payload parity, timeout, cancellation, proposals, citations, and diagnostics are documented. | None for backend/docs. | Claim Ask Thesys streaming contract and governed guide behavior. |
| `G46-B` | `future owner` | `S60-P6` | `docs/ASK_THESYS_STREAMING.md`, `apps/web/src/lib/api.ts` | `pnpm --filter thesys-web typecheck` and `pnpm --filter thesys-web test` both entered pnpm dependency-status/install retries and hit npm registry `ECONNRESET`; both were stopped with SIGINT after repeated retries. | Future owner: frontend CI/QA. Retry when npm registry access is stable. | Qualify frontend verification as environment-blocked. |
| `G46-C` | `future owner` | `S60-P6` | `docs/ASK_THESYS_STREAMING.md`, `apps/web/src/features/projects/guide-panel.tsx` | Browser QA for deltas, provider events, cancellation, timeout, citations, and workflow clutter could not run because web typecheck/test could not install dependencies. | Future owner: browser QA after web dependencies install. | Claim UI support exists; qualify browser smoke as pending. |
| `G46-D` | `implemented` | `S60-P6` | `docs/ASK_THESYS_STREAMING.md`, `apps/api/app/tests/test_guide.py` | Guide/context pytest slice passed (`77 passed, 1 warning`) and covers provider deltas, proposal events, timeout fallback, cancellation, citations, and final payload parity. | None for backend eval/test handoff. | Claim guide eval and stream-behavior handoff. |
| `G47-A` | `implemented` | `S60-P7` | `docs/EVALS_AND_OBSERVABILITY.md`, `scripts/eval_quality_gate.py` | `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60-final LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security` completed warn (`40/40`, no failed checks, warning gates `mcp_contract`, `security_check`). | None for local runbook; unavailable environment gates warn rather than disappear. | Claim CI-ready local quality gates with warn semantics. |
| `G47-B` | `implemented` | `S60-P7` | `docs/EVALS_AND_OBSERVABILITY.md`, eval report feature modules | JSON/Markdown/HTML report locations, trend JSONL, metadata, changelog paths, and regression interpretation are documented. | None. | Claim file-backed eval reports and trend artifacts. |
| `G47-C` | `implemented` | `S60-P7` | `docs/EVALS_AND_OBSERVABILITY.md`, observability metric feature modules | Metric names, LangSmith settings, redaction behavior, trace IDs, cache metrics, saved token/cost/latency examples, and budget-denial metrics are documented. | None for local/export docs. | Claim local observability plus optional redacted LangSmith export. |
| `G47-D` | `future owner` | `S60-P7` | `docs/EVALS_AND_OBSERVABILITY.md`, hidden eval report UI in `project-overview.tsx` | Eval-report pytest slice passed (`75 passed, 1 warning`) and quality gate completed warn (`40/40`); hidden report browser QA is blocked by npm registry failures. | Future owner: frontend/browser QA. Retry collapsed gate, trend, failure-link, budget/cache/cost metric checks when web dependencies install. | Qualify hidden eval-report browser QA as pending. |
| `G48-A` | `implemented` | `S60-P8` | `docs/SOURCE_INTELLIGENCE.md`, evidence extraction services | V1 decision is documented: deterministic `html.parser` fallback remains the local parser path, with parser/version/confidence metadata and productization tradeoffs. | None for V1 decision. | Claim deterministic local extraction; qualify maintained readability dependency as productization work. |
| `G48-B` | `intentionally out of V1` | `S60-P8` | `docs/SOURCE_INTELLIGENCE.md`, source provenance docs | Source snapshot metadata is documented and fixture-tested, but true page/screenshot object-storage artifact persistence is not in portfolio V1. | Future productization owner if the app becomes hosted: add storage keys, retention, redaction, and restore tests. | Do not claim true screenshot/page artifact storage in V1. |
| `G48-C` | `intentionally out of V1` | `S60-P8` | `docs/SOURCE_INTELLIGENCE.md`, extraction eval docs | Screenshot-region OCR/table provenance depends on true screenshot capture, so it is out of V1 with an explicit dependency on `G48-B`. | Future productization owner after screenshot/page artifact storage lands. | Do not claim screenshot-region OCR in V1. |
| `G48-D` | `future owner` | `S60-P8` | `docs/SOURCE_INTELLIGENCE.md`, `scripts/eval_extraction_quality.py` | `python3 scripts/eval_extraction_quality.py --json` scored 7/7 locally and warned that Tavily and live multimodal provider QA were skipped because credentials/provider mode were unavailable. | Future owner: live-provider QA. Rerun with `TAVILY_API_KEY`, `EXTERNAL_SEARCH_PROVIDER=tavily`, `MULTIMODAL_EXTRACTION_PROVIDER=litellm`, and egress allowlists. | Claim credential-free extraction evals; qualify live-provider QA as pending. |
| `G48-E` | `future owner` | `S60-P8` | `docs/SOURCE_INTELLIGENCE.md`, provenance UI surfaces | Extraction eval passed locally; web/browser provenance QA could not run because npm registry failures blocked frontend checks. | Future owner: frontend/browser QA for Evidence Inspect, retrieval/guide citations, research memo citations, source discovery, and Project Inspect trust summaries. | Qualify provenance browser QA as pending. |
| `G49-A` | `implemented` | `S59-R1` through `S59-R10` | `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, characterization tests | Sprint 59 verification passed focused characterization tests, full backend pytest, ruff, compileall, boundary checks, quality gate, diff check, and conflict scan. | None. | Claim refactor protected by characterization coverage. |
| `G49-B` | `implemented` | `S59-R1` through `S59-R10` | `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, `apps/api/app/features/*`, service wrappers | Feature-owned pure helpers and intentionally service-owned orchestration boundaries are documented for retrieval, evidence, validation, decisions, research, guide, MCP/tools, evals, context, memory, and structured output. | None; broader execution DTO extraction remains future cleanup where explicitly named. | Claim feature-package cleanup with honest service-owned boundaries. |
| `G49-C` | `implemented` | `S59-R1` through `S59-R10` | `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, contract-shape tests | DTO boundary ledger covers context, retrieval, citations, guide events, tools, eval gates, cache diagnostics, extraction, memory, proposals, audit, and fallback metadata. | None. | Claim typed boundary ledger and route-shape preservation. |
| `G49-D` | `implemented` | `S59-R9` | `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, common/feature helpers | Shared duplication disposition records tested centralization for prompt/schema repair, retrieval shaping, citation/provenance shaping, audit metadata redaction, proposal/action-card creation, Markdown rendering, and fallback metadata. | None. | Claim DRY cleanup where behavior is pinned by tests. |
| `G49-E` | `implemented` | `S59-R10` | `docs/BACKEND_FEATURE_PACKAGE_MAP.md`, shim/migration ledger | Sprint 59 boundary check passed and the package map records old path, new module, shim type, parity tests, temporary/permanent status, and cleanup follow-ups. | None. | Claim understandable post-refactor package map and migration evidence. |
| `G50-A` | `implemented` | `S60-P10` | `docs/CONTEXT_ENGINEERING.md`, `docs/MEMORY_SYSTEM.md`, `docs/MCP_INTEGRATION.md`, `docs/RETRIEVAL_AND_CITATIONS.md`, `docs/EVALS_AND_OBSERVABILITY.md`, `docs/SOURCE_INTELLIGENCE.md`, `docs/DEPLOYMENT_SECURITY.md` | Source-linked flow diagrams and owner tables exist for context, memory, MCP, retrieval, evals, source intelligence, and deployment/security. | None. | Claim source-linked architecture diagrams for interview review. |
| `G50-B` | `implemented` | `S60-P10` | README AI engineering map and developer docs navigation | README maps features to AI patterns/technologies and links developer docs for workflows, context, memory, retrieval, source ingestion, MCP, evals, security, observability, and Inspect surfaces. | None. | Claim portfolio-ready AI engineering tour. |
| `G50-C` | `implemented` | `S60-P10` | `apps/api/app/services/context_service.py`, `apps/api/app/services/memory_service.py`, `apps/api/app/mcp/adapter.py`, `apps/api/app/services/guide_service.py`, `apps/api/app/features/guide/events.py` | Public service entrypoints and protocol-shaping helpers have targeted docstrings for context, memory, MCP, guide governance, stream events, and non-obvious orchestration boundaries. | None for targeted docs; full docstring coverage remains ordinary maintenance. | Claim code navigation is developer-friendly without pretending every line is documented. |
| `G50-D` | `implemented` | `S60-P9` and `S60-P10` | `docs/DEPLOYMENT_SECURITY.md`, README developer docs navigation | Environment profiles, auth modes, provider/cache/auth/egress posture, object-storage expectations, backup/restore guidance, hosted smoke checklist, and audit commands are documented. | Hosted smoke execution remains `G41-E` future-owner work. | Claim deployment/security runbooks, not completed hosted smokes. |
| `G50-E` | `implemented` | `S60-P1` and `S60-P10` | This table, README roadmap/gap notes, `SPRINT_51_60_TODO.md` | Final disposition audit found `44` rows, no missing `G*` IDs, no duplicate IDs, and no extra IDs. | None; future-owner and out-of-V1 rows are intentionally explicit. | Claim honest portfolio limits with no unsupported completed-work language. |

## Sprint 60 Verification

Final Sprint 60 checks:

- Final disposition audit script: `44` final rows, no missing IDs, no duplicate
  IDs, no extra IDs.
- `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  passed (`60 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  passed (`66 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_feature_package_boundaries.py -q`
  passed (`67 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py app/tests/test_feature_package_boundaries.py -q`
  passed (`67 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  passed (`77 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_research_history_eval.py app/tests/test_demo_eval_workflows.py app/tests/test_feature_package_boundaries.py -q`
  passed (`75 passed, 1 warning`).
- `cd apps/api && .venv/bin/pytest app/tests/test_security_governance.py app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py -q`
  passed (`37 passed, 3 warnings`).
- `python3 scripts/eval_retrieval_quality.py` passed (`7/7`).
- `python3 scripts/eval_extraction_quality.py --json` passed (`7/7`) with
  warnings for missing `TAVILY_API_KEY` and deterministic multimodal provider
  mode.
- `python3 scripts/security_check.py` completed non-strict: backend security
  governance tests passed, AI quality eval passed (`10/10`), dependency audit
  warnings remained for missing `pip`/`pip-audit` in the API venv and npm
  registry fetch failures.
- `python3 scripts/audit_dependencies.py` completed non-strict with the same
  dependency blockers.
- Direct `pip-audit` returned `command not found`.
- `pnpm --filter thesys-web typecheck` and `pnpm --filter thesys-web test`
  could not reach TypeScript/tests because pnpm dependency-status/install
  repeatedly hit npm registry `ECONNRESET`; both sessions were stopped with
  SIGINT after repeated retries.
- `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60-final LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security`
  completed with warn status (`40/40`, no failed checks, warning gates:
  `mcp_contract`, `security_check`).
- `cd apps/api && .venv/bin/pytest -q` passed (`264 passed, 3 warnings`).
- `python3 scripts/check_feature_boundaries.py` passed.
- `cd apps/api && .venv/bin/ruff check app` passed.
- `cd apps/api && .venv/bin/python -m compileall app -q` passed.
- `git diff --check` passed.
- Conflict-marker scan found no matches.

## Sprint 0 Scope

- [x] Create monorepo structure.
- [x] Add Docker Compose services for web, API, Postgres + pgvector, Redis,
  MinIO, and LiteLLM.
- [x] Add `.env.example`.
- [x] Scaffold FastAPI app.
- [x] Scaffold Next.js app.
- [x] Add Alembic.
- [x] Add base SQLAlchemy model infrastructure.
- [x] Add healthcheck endpoints.
- [x] Add README local setup instructions.

## Sprint 0 Verification

Checks run:

- [x] `docker compose config`
- [x] `cd apps/api && pytest`
- [x] `cd apps/api && alembic upgrade head --sql`
- [x] `cd apps/api && ruff check apps/api`
- [x] `cd apps/web && node -e "JSON.parse(...)"`
- [x] `pnpm install && pnpm --filter thesys-web typecheck`

## Sprint 1 Scope

- [x] Add dev auth boundary and identity context.
- [x] Add users, workspaces, workspace members, projects, and project theses.
- [x] Add Alembic migrations for Sprint 1 tables.
- [x] Implement workspace-scoped project CRUD API.
- [x] Build project list UI.
- [x] Build project creation UI.
- [x] Build project overview page with empty states.

## Sprint 1 Verification

Checks run:

- [x] `cd apps/api && ruff check apps/api`
- [x] `cd apps/api && pytest`
- [x] `cd apps/api && alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`

## Sprint 2 Scope

- [x] Add LiteLLM client for the OpenAI-compatible proxy endpoint.
- [x] Add deterministic local LLM stub mode.
- [x] Add AI run and step SQLAlchemy models.
- [x] Add Alembic migration for `ai_runs` and `ai_steps`.
- [x] Add structured-output helper using Pydantic schemas.
- [x] Add prompt versioning convention.
- [x] Add token/cost logging fields.
- [x] Add structured-output smoke-test API endpoint.

## Sprint 2 Verification

Checks run:

- [x] `apps/api/.venv/bin/ruff check apps/api`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/api && uv lock`
- [x] `docker compose config`
- [x] `pnpm --filter thesys-web typecheck`

## Sprint 3 Scope

- [x] Implement structured intake Pydantic schema.
- [x] Add LangGraph-backed structured intake generation workflow.
- [x] Add `/intake/analyze`, `/intake/answer`, and `/intake/finalize`.
- [x] Store structured intake records, first thesis version, customer segments, and problems.
- [x] Build frontend intake wizard on the project overview page.
- [x] Keep intake workflow executions visible in `ai_runs` and `ai_steps`.

## Sprint 3 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

## Sprint 4 Scope

- [x] Implement evidence source and chunk tables.
- [x] Add URL ingestion.
- [x] Add manual note ingestion.
- [x] Add PDF/text/Markdown upload.
- [x] Add object storage integration with MinIO/S3 mode and local fallback.
- [x] Add parser/chunker and deterministic dev-safe embedding generation.
- [x] Store embeddings in pgvector-backed `evidence_chunks`.
- [x] Implement project-scoped semantic, keyword, and hybrid retrieval.
- [x] Add metadata filters for source type, freshness, competitor ID, and assumption ID.
- [x] Return retrieval results with source IDs, chunk IDs, scores, and metadata.
- [x] Trace ingestion and retrieval through `ai_runs` and `ai_steps`.
- [x] Build the Evidence tab with URL, note, upload, source list, and retrieval UI.

## Sprint 4 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

Original Sprint 5 plan:

- Implement opportunity brief workflow.
- Retrieve relevant evidence before generation.
- Generate structured opportunity brief and markdown artifact.
- Run citation audit.
- Store claims, unsupported assumptions, artifact, and artifact version.
- Display brief with citations.
- Extract assumptions and risks from brief.

## Sprint 5 Scope

- [x] Add artifact and artifact version persistence.
- [x] Add cited claims and claim-to-evidence links.
- [x] Add assumptions and risks produced by the opportunity brief.
- [x] Implement project-scoped opportunity brief generation.
- [x] Retrieve project evidence before generation.
- [x] Generate structured opportunity brief output and markdown artifact content.
- [x] Run citation audit before saving supported claims.
- [x] Save unsupported claims separately in structured artifact content.
- [x] Add artifact API routes and opportunity brief generation endpoint.
- [x] Build the Brief tab with generation, cited claims, unsupported claims, and versions.

## Sprint 5 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

Original Sprint 6 plan:

- Add competitor tables.
- Add manual competitor URL input.
- Implement competitor source ingestion.
- Implement competitor profile extraction.
- Implement competitor clustering.
- Generate competitor landscape artifact.
- Build Competitors tab.

## Sprint 6 Scope

- [x] Add `competitors` and `competitor_evidence_links` tables.
- [x] Add Alembic migration for competitor analysis records.
- [x] Add competitor CRUD API endpoints.
- [x] Add competitor analysis endpoint.
- [x] Ingest user-seeded competitor URLs through the evidence pipeline.
- [x] Attach `competitor_id` metadata to linked evidence chunks.
- [x] Generate structured competitor profiles, clusters, positioning gaps, and wedge notes.
- [x] Save the competitor landscape as a versioned artifact.
- [x] Preserve cited claims and unsupported claims.
- [x] Build the Competitors tab with URL entry, profile list, analysis action, and artifact display.

## Sprint 6 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

Original Sprint 7 plan:

- Build Assumptions tab.
- Build Risks display.
- Implement validation plan generation.
- Build Experiments tab.
- Add manual result logging.
- Update assumption confidence based on results.
- Build Decisions tab.
- Allow decision records linked to assumptions, evidence, artifacts, and experiments.

## Sprint 7 Scope

- [x] Add `experiments`, `experiment_results`, `decisions`, and `decision_links` tables.
- [x] Add Alembic migration for validation and decision records.
- [x] Add assumption/risk listing, extraction, and assumption update endpoints.
- [x] Add validation-plan generation endpoint that creates versioned artifacts and experiments.
- [x] Add manual experiment result logging.
- [x] Update assumption status/confidence and project confidence after result logging.
- [x] Add decision ledger endpoints with validated links to assumptions, risks, evidence,
  artifacts, competitors, and experiments.
- [x] Build Assumptions tab with risk display and per-assumption validation-plan action.
- [x] Build Experiments tab with validation plans and result logging.
- [x] Build Decisions tab with rationale, expected outcome, review date, and links.

## Sprint 7 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`

Original Sprint 8 plan:

- Add loading/progress states.
- Add SSE workflow updates.
- Add error handling.
- Add empty states.
- Add basic eval checks.
- Add seed/demo project.
- Add README demo script.
- Add screenshots or walkthrough GIF later.

## Sprint 8 Scope

- [x] Add workflow trace APIs:
  - `GET /api/projects/{project_id}/workflows`
  - `GET /api/workflows/{run_id}`
  - `GET /api/workflows/{run_id}/events`
- [x] Add SSE workflow event streaming over persisted `ai_runs` and `ai_steps`.
- [x] Add local-dev demo seeding endpoint:
  - `POST /api/demo/seed`
- [x] Seed the implementation-brief fitness coach scenario with structured project state,
  evidence, cited artifacts, competitors, assumptions, risks, validation experiment result,
  decision links, and workflow observability.
- [x] Add MVP eval endpoint:
  - `GET /api/projects/{project_id}/evals/mvp`
- [x] Add frontend workflow trace panels to intake, brief, competitor analysis,
  assumption extraction, and validation-plan generation.
- [x] Add project overview MVP readiness and recent workflow panels.
- [x] Add project-list demo seeding action.
- [x] Update README demo script and eval docs.
- [ ] Add screenshots or walkthrough GIF later.

## Sprint 8 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_demo_eval_workflows.py`
- [x] `pnpm --filter thesys-web typecheck`

Original Sprint 9 plan:

- Add AI status endpoint.
- Add visible web AI mode indicator.
- Document live-demo configuration.
- Verify structured-output smoke test can run with `used_stub=false`.
- Improve live-mode error handling.
- Show token and cost metadata in workflow traces.
- Decide whether to add real embeddings.
- Add tests for AI status and live/stub mode behavior.

## Sprint 9 Scope

- [x] Add `GET /api/ai/status` with configured stub mode, resolved mode,
  LiteLLM model/base URL, LiteLLM reachability, provider-key presence booleans,
  embedding configuration, and optional structured-output healthcheck.
- [x] Add global API error handling for LiteLLM and structured-output failures
  so provider issues return actionable 502 responses.
- [x] Add strict structured-output repair attempts and configurable fallback
  policy: `disabled`, `emergency`, or `always`.
- [x] Add web AI mode indicator showing `Stub mode` or `Live LLM`, model name,
  and LiteLLM reachability.
- [x] Add provider/model, token, and cost visibility to workflow traces.
- [x] Render AI-generated markdown output as readable headings, paragraphs,
  lists, links, inline code, and emphasis across project tabs.
- [x] Update `.env.example`, `README.md`, and API docs with the live-demo path.
- [x] Keep deterministic hash embeddings for Sprint 9 and expose the embedding
  model/dimension through AI status.
- [x] Add tests for AI status and live/stub structured-output behavior.

## Sprint 9 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] Browser-verified Brief, Competitors, Assumptions, Experiments, and
  Decisions tabs show no raw markdown heading/list syntax.

Original Sprint 10 plan:

- Add or compute project lifecycle stage.
- Replace developer-facing MVP readiness with founder-facing Idea Readiness.
- Replace Recent Workflows with Recent Strategic Updates.
- Add Current Recommendation, Next Best Action, Strategic Snapshot, and
  Evidence Health overview sections.
- Add guided empty states and outcome-oriented button labels.
- Add overview, readiness, strategic updates, and next-action API endpoints.
- Avoid V1 monitoring, collaboration, portfolio, or agentic research work.

## Sprint 10 Scope

- [x] Add computed overview schemas for project stage, recommendation, next
  action, readiness, strategic snapshot, evidence health, and strategic
  updates.
- [x] Add `ProjectOverviewService` using existing structured project,
  evidence, artifact, claim, assumption, risk, experiment, decision, and
  workflow data.
- [x] Add API endpoints:
  - `GET /api/projects/{project_id}/overview`
  - `GET /api/projects/{project_id}/readiness`
  - `GET /api/projects/{project_id}/strategic-updates`
  - `POST /api/projects/{project_id}/next-action`
- [x] Redesign the Overview tab around Current Recommendation, Next Best
  Action, Idea Readiness, Strategic Snapshot, Evidence Health, Recent
  Strategic Updates, and Key Assumptions/Risks.
- [x] Keep the AI mode badge visible but secondary to project guidance.
- [x] Replace implementation-oriented labels such as “Analyze Idea,”
  “Finalize Intake,” “MVP Readiness,” and “Recent Workflows.”
- [x] Add guided empty states with clear CTAs for briefs, evidence,
  competitors, assumptions, experiments, and decisions.
- [x] Add tests for new-project and seeded-demo overview behavior.

## Sprint 10 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_project_overview.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose up -d`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`

Original V1 Sprint 1 plan:

- Add `Run Research Sprint` CTA to the Overview page.
- Generate a research plan from the current idea/thesis.
- Let the user approve, edit, or reject the research plan.
- Store approved research plans.
- Show research workflow progress.
- Do not perform autonomous browsing/research before user approval.

## V1 Sprint 1 Scope

- [x] Add `research_plans` and `research_sprints` tables.
- [x] Add Alembic migration for research sprint planning records.
- [x] Add `ResearchPlanDraft` structured output schema.
- [x] Add research sprint planning prompt version.
- [x] Add LangGraph-backed planning workflow with project-context loading,
  structured plan generation, persistence, and AI run/step logging.
- [x] Put generated planning runs into `waiting_for_human` status.
- [x] Add research sprint endpoints:
  - `GET /api/projects/{project_id}/research-sprints`
  - `POST /api/projects/{project_id}/research-sprints/plan`
  - `PATCH /api/projects/{project_id}/research-plans/{plan_id}`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/approve`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/reject`
- [x] Add Overview page Research Sprint card with objective input, plan editing,
  save draft, approve, reject, recent plans, and workflow trace.
- [x] Keep autonomous source discovery, competitor discovery, and ingestion out
  of V1 Sprint 1.

## V1 Sprint 1 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_sprints.py`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_sprints.py app/tests/test_project_overview.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `docker compose config`

Original V1 Sprint 2 plan:

- Generate source discovery queries from approved research plans.
- Discover useful public source candidates.
- Rank and dedupe source candidates.
- Let users approve/reject sources before ingestion.
- Link discovered sources to research sprints.

## V1 Sprint 2 Scope

- [x] Add `discovered_sources` table with candidate, approved, rejected,
  ingested, and failed statuses.
- [x] Add `SourceDiscoveryService` that uses LiteLLM structured output in live
  mode and deterministic fallback in stub mode to create ranked public source
  candidates from research plan queries.
- [x] Add source discovery workflow tracing through `ai_runs` and `ai_steps`.
- [x] Add source candidate review endpoints:
  - `GET /api/projects/{project_id}/research-sprints/{sprint_id}/sources`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/approve`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/reject`
- [x] Approving a source candidate ingests a reviewed URL snapshot through the
  existing evidence chunking and embedding pipeline.
- [x] Add Overview page source candidate review UI.

Original V1 Sprint 3 plan:

- Discover direct competitors, indirect competitors, substitutes, and
  incumbents.
- Classify competitors.
- Let users approve, reject, or edit competitor candidates.
- Approved competitors become project competitor records.
- Each candidate explains why it matters.

## V1 Sprint 3 Scope

- [x] Add `competitor_candidates` table with candidate, approved, rejected, and
  merged statuses.
- [x] Add `CompetitorDiscoveryService` that uses LiteLLM structured output in
  live mode and deterministic fallback in stub mode to produce classified
  competitor and substitute candidates from the approved research plan.
- [x] Add competitor discovery workflow tracing through `ai_runs` and
  `ai_steps`.
- [x] Add competitor candidate review endpoints:
  - `GET /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/discover`
  - `PATCH /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/approve`
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/reject`
- [x] Approving a competitor candidate creates or updates a first-class
  project competitor and links approved discovered evidence when available.
- [x] Add Overview page competitor candidate review and edit UI.

## V1 Sprints 2-3 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_discovery.py app/tests/test_research_sprints.py`
- [x] Discovery tests assert that live mode calls the structured-output layer
  instead of bypassing LiteLLM.
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`

Original V1 Sprint 4 plan:

- Approved discovered sources and competitors should be ingested automatically
  into the project evidence graph.
- Fetch approved source content.
- Extract useful text.
- Chunk and embed content.
- Store source metadata and freshness timestamps.
- Link evidence to the project, competitors, assumptions, research questions,
  and artifacts where applicable.
- Make ingestion failures visible and recoverable.

## V1 Sprint 4 Scope

- [x] Add research ingestion metadata fields for discovered source ingestion
  timestamps and competitor candidate evidence ingestion status.
- [x] Upgrade discovered source approval from snapshot-only ingestion to real
  URL fetch, text extraction, chunking, embedding, and evidence-source linking.
- [x] Fall back to ingesting the reviewed discovery snapshot when a public URL
  blocks automated fetch, while preserving the remote fetch error in chunk
  metadata.
- [x] Stamp evidence chunk metadata with research sprint, research plan,
  discovered source, source type, research question, and assumptions-to-test
  provenance.
- [x] Upgrade competitor candidate approval to ingest the candidate URL when
  present, fall back to candidate snapshot ingestion when blocked, and link
  ingested chunks to the merged project competitor.
- [x] Link approved discovered-source evidence referenced by competitor
  candidates to the merged competitor.
- [x] Extend retrieval metadata filtering to support both singular and list
  metadata IDs for competitor-scoped retrieval.
- [x] Show source and competitor evidence ingestion status in the Overview
  research discovery review UI.

## V1 Sprint 4 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_discovery.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`

Original V1 Sprint 5 plan:

- Implement the core agentic RAG workflow.
- Break the research objective into subquestions.
- Choose semantic search, keyword search, source reading, competitor lookup,
  project-memory lookup, artifact lookup, and assumption lookup tools.
- Execute multiple retrieval/tool calls.
- Detect evidence gaps.
- Perform at least one additional retrieval pass when evidence is weak.
- Synthesize cited findings.
- Critique weak claims and unsupported conclusions.
- Produce a final research memo.
- Pause for human approval before major project-memory updates.

## V1 Sprint 5 Scope

- [x] Add `AGENTIC_RESEARCH_PROMPT_VERSION`.
- [x] Add structured schemas for agentic research findings, memo output, and API response.
- [x] Add `AgenticResearchService` with LangGraph nodes:
  - `load_research_context`
  - `research_planner`
  - `retrieval_strategy_selector`
  - `tool_executor`
  - `evidence_selector`
  - `gap_detector`
  - `follow_up_retriever`
  - `synthesizer`
  - `critic`
  - `final_memo_writer`
  - `human_approval_interrupt`
- [x] Implement project-scoped tool interfaces for semantic search, keyword
  search, source reading, competitor lookup, project-memory lookup, artifact
  lookup, and assumption lookup.
- [x] Write cited `research_memo` artifact versions with structured content
  linking back to the research sprint, plan, tool calls, selected evidence,
  evidence gaps, and critic output.
- [x] Store supported claims and claim-to-evidence links from the memo.
- [x] Mark unsupported or weak claims and keep memory updates pending human approval.
- [x] Add endpoint:
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run`
- [x] Add Overview page action to run agentic RAG from the research discovery panel.
- [x] Show the resulting trace and review status in the research sprint UI.
- [x] Add inline research memo review UI with rendered memo content, cited
  claims, unsupported claims, citations, version metadata, and pending human
  review state.
- [x] Add a research memo approval endpoint and UI action that completes the
  human review gate, marks the memo approved, and completes the research sprint.

## V1 Sprint 5 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_research_discovery.py app/tests/test_research_sprints.py -q`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] In-app browser verification for memo review and approval UI.

Original V1 Sprint 6 plan:

- Upgrade research memos so they feel like sharp strategic analysis.
- Add sections for market landscape, pain signals, competitors, substitutes,
  pricing signals, risks, assumptions, evidence summary, unknowns, validation
  actions, and decision recommendation.
- Keep citations and unsupported claims visible.
- Trace memo versions back to research sprints, sources, evidence, and claims.

## V1 Sprint 6 Scope

- [x] Extend `AgenticResearchMemoDraft` with V1 memo sections.
- [x] Render upgraded research memo markdown with the required V1 sections.
- [x] Add research-derived risk and assumption drafts to memo structured content.
- [x] Add memory-update previews to research memo artifact versions.
- [x] Keep cited claims, unsupported claims, selected evidence, tool calls,
  gaps, critic output, and sprint/version links in structured content.
- [x] Show approved memory-update summaries in the memo review UI.

Original V1 Sprint 7 plan:

- Convert research findings into operational validation priorities.
- Create or update assumptions and risks after user approval.
- Rank assumptions by importance, uncertainty, evidence strength, and kill risk.
- Link assumptions to evidence.
- Refresh overview recommendation and next best action after memory changes.

## V1 Sprint 7 Scope

- [x] Add `assumption_evidence_links` table and Alembic migration.
- [x] Add assumption evidence links to API schemas and web types.
- [x] Change research memo approval from metadata-only approval to a memory
  writer that creates or updates assumptions and risks.
- [x] Link research-derived assumptions to cited evidence chunks.
- [x] Update project confidence from research-derived assumption confidence.
- [x] Invalidate overview, assumptions, risks, and experiments after memo
  approval so the UI reflects the new state.
- [x] Add research memo strategic update language to the Overview feed.

Original V1 Sprint 8 plan:

- Help users take action after research.
- Generate validation assets from high-risk assumptions.
- Include interview scripts, screeners, survey questions, landing page copy,
  outreach messages, success criteria, note templates, and result rubrics.
- Keep external execution manual and user-controlled.

## V1 Sprint 8 Scope

- [x] Extend validation plan schemas with screener questions, landing page copy,
  outreach copy, note-taking templates, and result interpretation rubrics.
- [x] Update validation-plan prompting and deterministic stubs to generate the
  richer validation asset set.
- [x] Render validation assets into artifact markdown and experiment plans.
- [x] Show evidence-link counts on research-derived assumptions.
- [x] Preserve the existing manual experiment execution and result logging flow.

## V1 Sprints 6-8 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check ...`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_validation.py -q`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`

Original V1 Sprint 9 plan:

- Show research sprint history.
- Show what changed after each sprint.
- Show evidence added.
- Show assumptions created/updated.
- Show recommendation changes.
- Show memory updates approved/rejected.
- Show research memo versions.

## V1 Sprint 9 Scope

- [x] Add project research-history API:
  - `GET /api/projects/{project_id}/research-history`
- [x] Compute per-sprint history from research plans, source candidates,
  competitor candidates, research memo artifact versions, workflow review state,
  and memory-update status.
- [x] Add explicit research memo rejection endpoint:
  - `POST /api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/reject`
- [x] Preserve rejected memory updates in artifact structured content without
  writing assumptions or risks into project memory.
- [x] Surface research history on the Overview page with evidence counts,
  competitor counts, memo/version links, recommendation changes, and event
  timelines.
- [x] Add research-specific strategic updates for memo generation, approved
  memory updates, rejected memory updates, and sprint completion/failure.

Original V1 Sprint 10 plan:

- Add eval cases for autonomous research quality.
- Add retrieval quality checks.
- Add groundedness checks.
- Add latency/cost tracking.
- Add trace inspection.
- Create polished demo projects.

## V1 Sprint 10 Scope

- [x] Add 10-case local research sprint eval dataset:
  - `apps/api/app/evals/research_sprint_cases.json`
- [x] Add V1 research eval endpoint:
  - `GET /api/projects/{project_id}/evals/v1-research`
- [x] Evaluate source discovery, competitor discovery, citation coverage,
  unsupported claims, high-risk assumptions, validation actions, agentic trace
  persistence, evidence gap detection, and cost/latency visibility.
- [x] Show Research Quality checks on the Overview page.
- [x] Document V1 research history and eval commands in README and docs.

## V1 Sprints 9-10 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_history_eval.py -q`
- [x] `cd apps/api && .venv/bin/ruff check ...`
- [x] `pnpm --filter thesys-web typecheck`

## Sprint 11 Scope

- [x] Add Sprint 11 UI/UX refactor requirements to the implementation brief.
- [x] Refactor project navigation to Overview, Research, Evidence, Competitors,
  Assumptions, Validation, and Decisions.
- [x] Move research sprint planning, discovery review, research memo review,
  research history, and quality checks into the Research tab.
- [x] Keep Overview focused on recommendation, next action, lifecycle progress,
  strategic snapshot, top risks, evidence health, and recent strategic updates.
- [x] Add progressive disclosure for manual evidence entry, research traces,
  generated memos, validation plans, and source details.
- [x] Group competitors by category and make competitor profiles easier to scan.
- [x] Refactor assumptions around the riskiest assumption, filters, and a ranked
  operational table.
- [x] Rename Experiments to Validation and make validation assets copyable.
- [x] Add current decision recommendation to the Decisions page.

## Sprint 11 Verification

Checks run:

- [x] `pnpm --filter thesys-web typecheck`

## Sprint 12 Scope

- [x] Audit current V1 project pages against best-in-class workflow patterns
  from Linear, Jira Product Discovery, Dovetail, NotebookLM, and Clay.
- [x] Refine Overview as a Linear-inspired command center with one primary
  action, strong hierarchy, lifecycle progress, and secondary technical status.
- [x] Refine Assumptions and idea-readiness surfaces using prioritization,
  risk, confidence, evidence-strength, and status patterns from Jira Product
  Discovery.
- [x] Refine Evidence and Research surfaces so findings and source-linked
  insights lead, while raw chunks/details stay behind drawers or progressive
  disclosure.
- [x] Refine briefs and research memos around source-grounded reading patterns:
  executive verdict first, citations near claims, sources used, unsupported
  claims, and "what we still do not know."
- [x] Refine research sprint, source discovery, competitor discovery, and
  approval flows around inspectable plain-English workflow steps and structured
  candidate rows/cards.
- [x] Validate the full seeded demo journey across Overview, Research,
  Evidence, Competitors, Assumptions, Validation, and Decisions.

## Sprint 12 Verification

Checks run:

- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose restart web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`

## Sprint 13 Scope

- [x] Add Sprint 13 UX/Product Activation Refactor to `IMPLEMENTATION_BRIEF.md`.
- [x] Create Sprint 13 UX audit/TODO list.
- [x] Add persistent project Verdict Bar across project tabs.
- [x] Rename Overview Current State to Strategic Verdict and add explicit Why framing.
- [x] Surface Riskiest Assumption on the Overview page.
- [x] Refactor the home/project list around product promise, verdict, stage, next action,
  and project-scoped evidence state.
- [x] Make the new-project form start from "Investigate a New Idea" and add Quick Scan /
  Deep Research Sprint choice.
- [x] Refactor Research page so conclusions lead and run/process details are secondary.
- [x] Refactor Evidence page around supported findings and open questions.
- [x] Refactor Competitors page around landscape summary and strategic implication.
- [x] Refactor Assumptions labels and CTA hierarchy.
- [x] Refactor Validation into a step-by-step execution guide.
- [x] Refactor Decisions into suggested decision, rationale, and missing evidence.
- [x] Improve seeded demo project presentation if needed.
- [x] Run Sprint 13 usability task tests.
- [x] Add Sprint 13 product-clarity addendum for strategic judgment, state-aware
  CTAs, workflow-progress labeling, and implication-driven evidence.
- [x] Replace procedural overview/verdict language with strategic recommendations
  from the shared overview service.
- [x] Clarify workflow progress vs idea confidence in the project header,
  verdict bar, Overview, and lifecycle details.
- [x] Add Research Result, Top Validation Priorities, state-aware validation
  CTAs, and stronger decision recommendations.

## Sprint 13 Verification

Checks run:

- [x] `pnpm --filter thesys-web typecheck`
- [x] Manual code-path QA against Sprint 13 usability tasks:
  - home/project list promise and strategic project cards
  - project verdict bar and Overview verdict/next action/riskiest assumption
  - Research conclusions before inspectable run details
  - Evidence supported findings and open questions before raw sources
  - Competitors landscape summary, substitutes, and strategic implication
  - Assumptions risk/confidence labels and primary riskiest-assumption CTA
  - Validation step plan, assets, prominent result logging, and interpretation
  - Decisions suggested decision, rationale, and missing evidence
- [x] `git diff --check`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] `docker compose restart web`
- [x] `curl -I -fsS http://localhost:3000/projects` after restart
- [x] Browser smoke check for `/projects` and seeded demo project verdict context
- [x] Re-run Sprint 13 product-clarity checks after the additional addendum:
  - strategic project card/verdict bar wording
  - hash navigation across project tabs
  - assumptions top priorities and no horizontal overflow
  - evidence implication/open-question format and consistent counts
  - validation state-aware CTA and decision handoff

## V1 Sprint 14 Scope

- [x] Add opt-in LangSmith configuration to API settings, Docker Compose, and
  `.env.example`.
- [x] Add LangSmith dependency and a best-effort observability service that
  creates local trace IDs when external tracing is disabled.
- [x] Persist trace IDs/URLs on `ResearchSprint`, `AIRun`, `AIStep`, and
  `ArtifactVersion`.
- [x] Add Alembic migration for trace columns and indexes.
- [x] Trace research sprint planning, source discovery, competitor discovery,
  agentic research planning/retrieval/synthesis/critique/memo-writing,
  assumption extraction, memory-update approval/rejection, and validation-plan
  generation.
- [x] Expose trace fields through workflow, artifact, and research schemas.
- [x] Show trace links in workflow details, research history, memo review, and
  research quality panels.
- [x] Expand the research eval dataset to 10 Sprint 14 cases with competitor,
  risky-assumption, output-section, unsafe-claim, next-action, and demo-ready
  fields.
- [x] Add V1 research eval metrics for memo completeness, trace ID persistence,
  span coverage, and secret redaction.
- [x] Add local `pnpm eval:research` command.
- [x] Document LangSmith observability and local eval usage in README.

## V1 Sprint 14 Verification

Checks run:

- [ ] `cd apps/api && uv lock` was attempted but `uv` is not installed in this
  shell; `apps/api/uv.lock` already contains `langsmith==0.8.5`.
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_langsmith_observability.py app/tests/test_agentic_research.py app/tests/test_research_history_eval.py app/tests/test_validation.py -q`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `PATH=... node_modules/.bin/next typegen` from `apps/web`
- [x] `PATH=... node_modules/.bin/tsc --noEmit` from `apps/web`
- [x] `python3 scripts/eval_research_sprints.py`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose config`
- [x] `git diff --check -- . ':(exclude)IMPLEMENTATION_BRIEF.md'`
- [ ] Full `git diff --check` is blocked by trailing whitespace in the
  user-updated `IMPLEMENTATION_BRIEF.md`.
- [ ] Browser smoke check is blocked because `http://localhost:3000/projects`
  timed out in the in-app browser.
- [ ] Container restart is blocked because `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
  hung with no output and had to be terminated.

## V1 Sprint 15 Scope

- [x] Add MCP-compatible internal tool definitions with names, descriptions,
  input/output schemas, access modes, risk levels, approval policies, and
  allowed project roles.
- [x] Add `tool_invocations` audit persistence with project and research sprint
  scope, requested-by attribution, redacted input/output payloads, status,
  risk, access mode, and approval metadata.
- [x] Add API endpoints for:
  - `GET /api/tools`
  - `GET /api/projects/{project_id}/tool-invocations`
  - `POST /api/projects/{project_id}/tool-invocations/{invocation_id}/approve`
  - `POST /api/projects/{project_id}/tool-invocations/{invocation_id}/reject`
- [x] Register at least 8 read tools:
  - `get_project_summary`
  - `search_project_evidence`
  - `list_project_sources`
  - `list_competitors`
  - `list_assumptions`
  - `list_validation_plans`
  - `list_decisions`
  - `get_research_memo`
- [x] Register proposal tools:
  - `propose_research_plan`
  - `propose_memory_update`
  - `propose_validation_plan`
  - `propose_decision`
- [x] Route agentic research project context reads, evidence searches, lookup
  calls, and memory/validation/decision proposals through the tool layer.
- [x] Gate research-plan and research-memo proposal approvals before final
  project state mutation.
- [x] Add a secondary Tool Activity panel to the project evidence review UI.
- [x] Document the internal MCP-style tool boundary in README.

## V1 Sprint 15 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app/tests/test_tool_boundary.py app/services/tool_service.py app/routers/tools.py app/services/agentic_research_service.py app/services/research_sprint_service.py`
- [x] `cd apps/api && .venv/bin/python -m pytest app/tests/test_tool_boundary.py app/tests/test_agentic_research.py -q`
- [x] `cd apps/api && .venv/bin/python -m pytest -q`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/apps/web/node_modules/.bin:$PATH tsc --noEmit` from `apps/web`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Post-restart browser smoke check against
  `/projects/386742ee-948b-49d4-9beb-e646d09b8e41#research-sprint`: Tool Activity
  panel rendered one approved `propose_research_plan` invocation and browser
  console reported no errors.

## V1 Sprint 16 Scope

- [x] Replace the legacy member role with owner/admin/editor/viewer permission
  checks for project viewing, research execution, memory approval, high-risk
  tool approval, decision recording, project writes, and owner-only deletion.
- [x] Add `audit_events` and `approval_requests` persistence with Alembic
  migration, Pydantic schemas, governance service helpers, and project-scoped
  API routes.
- [x] Enforce tool authorization by role, access mode, risk, and approval
  policy; deny safely and audit tool denials.
- [x] Create approval requests for research plans, memory updates, validation
  plans, tool proposals, and high-risk decisions.
- [x] Record governance events for research sprint start/approval, tool
  requests/executions/denials, memory proposals/approvals/rejections,
  validation-plan creation, decision recording, and high-risk requests.
- [x] Add shared redaction for API keys, bearer/JWT-like tokens, sensitive key
  names, secret values, and emails across audit, tool, workflow, LangSmith, and
  UI-facing error surfaces.
- [x] Add prompt-injection hardening: agent prompts state retrieved content is
  evidence, not instruction, and retrieved evidence/snippets are wrapped in
  `<untrusted_retrieved_content>` blocks.
- [x] Add the project governance approval queue UI with summary, risk, why it
  matters, proposed state changes, approve/reject controls, and recent audit
  events.
- [x] Document Security and Governance in README.

## V1 Sprint 16 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/python -m pytest app/tests/test_security_governance.py app/tests/test_tool_boundary.py -q`
- [x] `cd apps/api && .venv/bin/python -m pytest app/tests/test_langsmith_observability.py app/tests/test_security_governance.py -q`
- [x] `cd apps/api && .venv/bin/python -m pytest app/tests/test_competitors.py app/tests/test_security_governance.py -q`
- [x] `cd apps/api && .venv/bin/python -m pytest -q`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/apps/web/node_modules/.bin:$PATH next typegen` from `apps/web`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/apps/web/node_modules/.bin:$PATH tsc --noEmit` from `apps/web`
- [x] `git diff --check -- . ':(exclude)IMPLEMENTATION_BRIEF.md'`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Browser QA against
  `/projects/103c6571-aee6-46a0-b0f5-af6be2b409de#research-sprint`: the
  governance approval queue rendered one pending research-plan approval, showed
  proposed change JSON and audit events, the Approve button resolved the queue
  to zero pending approvals, and the browser console reported no errors.
- [ ] `pnpm --dir apps/web typecheck` was attempted but `pnpm` is not installed
  in this shell; local `next typegen` and `tsc --noEmit` both passed.

## V1 Sprint 17 Scope

- [x] Add Temporal SDK dependency, settings, local Docker service, and dedicated
  `temporal-worker` process.
- [x] Add Temporal execution metadata to `research_sprints`: workflow ID, run ID,
  current step, failed step, and failure message.
- [x] Add Alembic migration for durable execution metadata and expanded sprint
  statuses.
- [x] Implement `ResearchSprintWorkflow` as the deterministic Temporal business
  workflow.
- [x] Implement side-effecting Temporal activities for source discovery,
  competitor discovery, ingestion, embedding boundary, LangGraph research
  synthesis, eval checks, memory-update proposal handling, persistence, and
  finalization.
- [x] Keep LangGraph-owned reasoning inside `run_langgraph_research_activity`.
- [x] Add durable workflow API routes for status, start, retry, and cancel.
- [x] Signal the Temporal workflow from research-plan and memory-update approval
  endpoints.
- [x] Add project UI durable workflow status panel with current step, action
  required, retry, and cancel controls.
- [x] Add unit tests for Temporal metadata, approval signaling, retry, cancel,
  and disabled-mode status behavior.
- [x] Document Durable Workflow Orchestration in README.

## V1 Sprint 17 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_temporal_research_orchestration.py app/tests/test_research_sprints.py app/tests/test_agentic_research.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/apps/web/node_modules/.bin:$PATH tsc --noEmit` from `apps/web`
- [x] `git diff --check -- . ':(exclude)IMPLEMENTATION_BRIEF.md'`
- [x] `PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH docker compose up -d --build temporal api temporal-worker`
- [x] `PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH docker compose restart web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] `PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH docker compose exec -T api alembic current`
  reported `0018_temporal_research (head)`.
- [x] `PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH docker compose ps`
  confirmed `temporal`, `temporal-worker`, `api`, and `web` were running.
- [x] Browser QA against
  `/projects/244d865c-b270-4df7-83ff-746a90912b39#research-sprint`: generated
  a Temporal-backed sprint, confirmed the durable workflow panel rendered
  `Temporal enabled`, `waiting for approval`, current step
  `wait for research plan approval`, workflow ID, and action required
  `Approve research plan`; then clicked `Cancel workflow` and confirmed the
  panel and API durable status changed to `cancelled` with no browser console
  errors.

Notes:

- [x] A full web image rebuild was attempted with `docker compose up -d --build
  temporal api temporal-worker web`, but the Docker build exhausted npm
  registry retries with `ECONNRESET`. No frontend dependencies changed in this
  sprint, and the web service bind-mounts `apps/web`, so the existing web image
  was restarted and served the updated source successfully.

## V1 Sprint 18 Scope

- [x] Add guide schema contracts for context, action cards, recommendation
  responses, chat requests, chat responses, and related project entities.
- [x] Add `GuideService` that loads project overview state, derives current
  focus, missing context, biggest unknown, confidence/risk, evidence summary,
  and stage-aware next actions.
- [x] Add guide API routes for:
  - `GET /api/projects/{project_id}/guide/context`
  - `POST /api/projects/{project_id}/guide/recommend`
  - `POST /api/projects/{project_id}/guide/actions/{action_id}/execute`
- [x] Map guide actions to existing project tabs/forms through stable deep
  links and action metadata.
- [x] Cover guide output across at least five project stages.

## V1 Sprint 18 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_guide.py`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_guide.py apps/api/app/tests/test_project_overview.py`
- [x] `apps/api/.venv/bin/ruff check apps/api/app/services/guide_service.py apps/api/app/schemas/guide.py apps/api/app/routers/projects.py apps/api/app/tests/test_guide.py`
- [x] `apps/api/.venv/bin/pytest`
- [x] Runtime check:
  `GET /api/projects/53002617-c8bc-4335-bc4d-9ac43a338390/guide/context`
  returned stage-aware context with missing evidence, assumptions, validation,
  and decision context.
- [x] Runtime check:
  `POST /api/projects/53002617-c8bc-4335-bc4d-9ac43a338390/guide/recommend`
  returned the expected current focus, recommended action, secondary actions,
  and suggested questions.
- [x] Runtime check:
  `POST /api/projects/53002617-c8bc-4335-bc4d-9ac43a338390/guide/actions/generate_brief/execute`
  returned the executable action and target route.

## V1 Sprint 19 Scope

- [x] Add a persistent `GuidePanel` to project pages in both mobile and desktop
  layouts.
- [x] Render current focus, why it matters, the primary recommended action,
  secondary actions, suggested questions, and constrained Ask Thesys responses.
- [x] Wire guide panel actions to existing project navigation and workspace
  affordances.
- [x] Add frontend API client types and calls for guide context,
  recommendations, action execution, and guide chat.
- [x] Add backend guide chat that stays constrained to thesis, evidence,
  blockers, validation, and decisions.

## V1 Sprint 19 Verification

Checks run:

- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin node_modules/.bin/next typegen`
  from `apps/web`
- [x] `PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/bin:/bin node_modules/.bin/tsc --noEmit`
  from `apps/web`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Runtime check:
  `POST /api/projects/53002617-c8bc-4335-bc4d-9ac43a338390/guide/chat`
  returned a project-scoped answer, action cards, and related thesis/research
  entities.
- [x] Browser QA in the Codex in-app browser against
  `/projects/53002617-c8bc-4335-bc4d-9ac43a338390#intelligence`: the Guide
  rendered current focus, why it matters, primary action, secondary actions,
  suggested questions, and Ask Thesys; the Guide stayed visible across
  Decision, Intelligence/Evidence, Validation, and Record workspaces; the
  Improve thesis action opened the structured project context form; Ask Thesys
  returned a project-scoped answer with action cards and related entities; the
  browser console reported no errors.

## V1 Sprint 20 Scope

- [x] Add a standalone conversational investigation preview API:
  - `POST /api/intake/investigation/preview`
- [x] Add Sprint 20 response contracts for thesis drafts, investigation modes,
  missing context, assumptions made, clarifying questions, and first next
  action.
- [x] Keep the existing project-bound structured intake APIs intact.
- [x] Add backend preview generation that asks only 2-4 clarifying questions,
  supports continuing with assumptions, and returns a first testable thesis.
- [x] Rebuild the new investigation UI around a guided flow:
  - paste rough idea
  - shape idea
  - answer or skip clarifying questions
  - review first testable thesis
  - choose Quick Orientation, Evidence Review, or Validation Sprint
  - create and finalize the structured project
- [x] Route new projects to the recommended investigation path after creation.

## V1 Sprint 20 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_intake.py`
- [x] `apps/api/.venv/bin/pytest`
- [x] `apps/api/.venv/bin/ruff check apps/api/app`
- [x] `/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node node_modules/next/dist/bin/next typegen`
  from `apps/web`
- [x] `/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node node_modules/typescript/bin/tsc --noEmit`
  from `apps/web`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects/new`
- [x] Runtime check:
  `POST /api/intake/investigation/preview` returned a live LLM thesis draft,
  2-4 clarifying questions, investigation modes, and a recommended path.
- [x] Runtime check:
  preview -> create project -> finalize structured intake -> overview returned
  project `b4706caa-f785-4bd3-9f64-11af9e60f3f5` at stage
  `structured_intake` with next action `Run first research pass`.
- [x] Browser QA: opened `/projects/new`, pasted a rough idea, clicked
  `Shape idea`, verified the first testable thesis appeared, used `Continue
  with assumptions`, created the investigation, and confirmed the project
  opened at `/projects/c1c642a5-f52b-4722-a9f4-25d483c13ccf#research`.
  Captured screenshots in `/private/tmp/thesys-sprint20-qa`; the run reported
  no failed HTTP responses and no browser console errors.

## V1 Sprint 21 Scope

- [x] Add `ThesisCanvas` and `ThesisEvolutionEvent` persistence with project and
  workspace scoping.
- [x] Add Alembic migration for the thesis canvas and evolution timeline tables.
- [x] Add project APIs:
  - `GET /api/projects/{project_id}/thesis-canvas`
  - `PATCH /api/projects/{project_id}/thesis-canvas`
  - `GET /api/projects/{project_id}/thesis-evolution`
- [x] Seed thesis canvases from existing project descriptions, current theses,
  structured intake, assumptions, problems, and validation state.
- [x] Record thesis edits as manual evolution events and create a new project
  thesis version when the current thesis changes.
- [x] Add derived evolution events for research artifacts, validation blockers,
  experiment results, and decisions.
- [x] Teach Ask Thesys to answer how an idea changed and expose `Show evolution`
  and thesis editing actions.
- [x] Add the frontend Thesis tab with editable canvas fields and a chronological
  evolution timeline.

## V1 Sprint 21 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_thesis_canvas.py app/tests/test_guide.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/web && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/cgable/Repos/thesys/node_modules/.bin:$PATH ./node_modules/.bin/next typegen && ./node_modules/.bin/tsc --noEmit`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose config`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Runtime check: `POST /api/demo/seed`, then
  `GET /api/projects/244d865c-b270-4df7-83ff-746a90912b39/thesis-canvas`
  returned a seeded thesis canvas with original idea, current thesis, target
  user, problem, workaround, wedge, biggest unknown, proof needed, and evolution
  events derived from assumptions, research, validation, and decisions.
- [x] Runtime check: created a disposable project, loaded its thesis canvas,
  patched the canvas, confirmed one manual evolution event and thesis version 2,
  then deleted the disposable project.
- [x] Browser QA in the Codex in-app browser: opened the demo project at
  `#thesis`, verified the Thesis workspace rendered seeded canvas fields,
  derived evolution events, and the `Show evolution` guide action; opened a
  disposable project, edited and saved the thesis canvas through the UI,
  confirmed rejected direction/open question counts, manual timeline event, and
  thesis version 2, then deleted the disposable project. Browser console
  reported no errors.

## V1 Sprint 22 Scope

- [x] Add `WedgeOption` persistence with project/workspace scoping.
- [x] Add Alembic migration for the `wedge_options` table.
- [x] Add project APIs:
  - `GET /api/projects/{project_id}/wedges`
  - `POST /api/projects/{project_id}/wedges/generate`
  - `POST /api/projects/{project_id}/wedges/{wedge_id}/select`
  - `POST /api/projects/{project_id}/wedges/{wedge_id}/test`
  - `POST /api/projects/{project_id}/wedges/{wedge_id}/research-more`
  - `POST /api/projects/{project_id}/wedges/{wedge_id}/reject`
- [x] Generate wedge options from the current Thesis Canvas, evidence source
  count, supported claims, competitors, and top assumptions.
- [x] Support `Select wedge`, `Test this wedge`, `Research more`, and `Reject`
  actions.
- [x] Update the Thesis Canvas and create `wedge_change` evolution events when
  a wedge is selected, moved to validation, or rejected.
- [x] Preserve rejected wedges in the Thesis Canvas rejected directions.
- [x] Add a focused Wedge Explorer comparison panel inside the Thesis workspace.
- [x] Update Guide actions and Ask Thesys wedge answers to point to the Wedge
  Explorer instead of the competitor map.

## V1 Sprint 22 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_wedge_explorer.py -q`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_wedge_explorer.py apps/api/app/tests/test_guide.py apps/api/app/tests/test_thesis_canvas.py -q`
- [x] `apps/api/.venv/bin/pytest`
- [x] `apps/api/.venv/bin/ruff check apps/api/app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/web && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/next typegen && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc --noEmit`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Browser QA in the Codex in-app browser after restarting containers:
  created a disposable QA project, opened `#thesis`, generated wedges, selected
  `Manual workaround replacement`, confirmed it became the single recommended
  wedge, moved it to validation, rejected the broad concept wedge, and confirmed
  Ask Thesys answered the wedge question with the recommended wedge, why it
  might work, main risk, and first test. Browser logs reported no app warnings
  or errors.

## V1 Sprint 23 Scope

- [x] Add `ValidationMission` persistence with project/workspace scoping,
  assumption link, optional experiment link, mission status, steps, criteria,
  and validation assets.
- [x] Add Alembic migration for the `validation_missions` table.
- [x] Add mission APIs:
  - `GET /api/projects/{project_id}/experiments/missions`
  - `GET /api/projects/{project_id}/experiments/missions/current`
  - `POST /api/projects/{project_id}/experiments/missions/{mission_id}/start`
  - `POST /api/projects/{project_id}/experiments/missions/{mission_id}/interpret`
- [x] Create validation missions when validation plans generate experiments.
- [x] Advance mission state when a mission starts, results are logged, and
  results are interpreted.
- [x] Update demo seeding so the fitness coach demo includes a validation
  mission.
- [x] Update Guide actions and related entities to route to the current
  validation mission.
- [x] Redesign the Validation workspace front door around a mission-first
  current proof with steps, progress, primary CTA, criteria, assets, result
  logging, and interpretation.

## V1 Sprint 23 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_guide.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/web && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/next typegen && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc --noEmit`
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Browser QA in the Codex in-app browser after restarting containers:
  created a disposable QA project, generated and started a validation mission,
  pasted raw interview/pricing/workaround notes, confirmed the interpreted
  signal summary, pain/urgency/WTP/switching fields, strengthened/weakened
  bullets, recommended next action, and pending-approval copy, then approved the
  pending memory update from Intelligence > Evidence review and confirmed the
  governance panel cleared to 0 pending with audit events recorded.
- [x] `/Applications/Docker.app/Contents/Resources/bin/docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Browser QA in the Codex in-app browser after restarting containers:
  created a disposable QA project, extracted assumptions, generated a
  validation plan, opened `#validation-mission`, started the mission, logged a
  result, interpreted the result, and confirmed the final CTA routes to
  `#decisions`. Checked desktop and mobile mission-panel viewports for
  horizontal overflow.

## V1 Sprint 24 Scope

- [x] Add persisted `ValidationResultInterpretation` records linked to
  project, mission, experiment, assumption, AI run, and approval request.
- [x] Add Alembic migration for validation result interpretations.
- [x] Replace the status-only mission interpretation endpoint with a structured
  interpretation workflow that accepts pasted validation notes or uses logged
  results.
- [x] Extract pain severity, urgency, willingness-to-pay signal, switching
  signal, objections, quotes, confidence change, next action, and decision
  recommendation.
- [x] Create a pending `memory_update` approval before applying major project
  state changes.
- [x] Apply approved interpretation updates to assumption confidence/status,
  project confidence, audit trail, and thesis evolution.
- [x] Show the latest interpretation inside the Validation Mission UI.
- [x] Add a paste-notes interpretation form with a pending-approval message.
- [x] Treat validation interpretations as decision evidence in overview
  readiness/stage logic.

## V1 Sprint 24 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py -q`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `cd apps/web && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/next typegen && PATH=/Users/cgable/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc --noEmit`

## V1 Sprint 25 Scope

- [x] Add backend Decision Coach response contracts for recommendation,
  supporting evidence, missing evidence, risks, action cards, and suggested
  decision record prefill.
- [x] Add decision APIs:
  - `GET /api/projects/{project_id}/decisions/recommendation`
  - `POST /api/projects/{project_id}/decisions/coach`
- [x] Derive recommendations from interpreted validation results when present,
  with deterministic fallbacks for projects that still need evidence.
- [x] Generate suggested decision records with trace links to the key blocker,
  evidence sources, and validation experiment tied to the mission.
- [x] Route decision-related Guide chat questions through Decision Coach.
- [x] Update the Decisions workspace to show a Decision Coach panel with the
  recommended decision, rationale, missing proof, supporting evidence, risks,
  constrained Q&A, and prefilled record action.
- [x] Preserve the existing durable decision record form and evidence-link
  workflow.

## V1 Sprint 25 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_validation.py apps/api/app/tests/test_guide.py -q`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests -q`
- [x] `apps/api/.venv/bin/ruff check apps/api/app/services/validation_service.py apps/api/app/routers/decisions.py apps/api/app/services/guide_service.py apps/api/app/schemas/validation.py apps/api/app/tests/test_validation.py`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I http://localhost:3000/projects`
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 26 Scope

- [x] Add a typed playbook navigation contract to the project overview API.
- [x] Compute stage-aware playbook steps for Guide, Thesis, Research, Test,
  Decision, and History.
- [x] Mark each playbook step as available, blocked, complete, or current.
- [x] Highlight the current lifecycle step based on project stage:
  - draft idea -> Thesis
  - structured/researched stages -> Research
  - assumption/validation stages -> Test
  - results logged -> Decision
  - recorded/paused/killed stages -> History
- [x] Replace the project page "Workspaces" navigation with "Idea Playbook."
- [x] Show each playbook item with user-facing purpose text and status.
- [x] Replace mobile "Switch workspace" copy with "Switch playbook step."
- [x] Preserve existing internal tab routes while exposing guided playbook
  labels and deep links.
- [x] Rename the visible Intelligence surface to Research.

## V1 Sprint 26 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_project_overview.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 27 Scope

- [x] Add persisted `ProjectNudge` records with severity, message,
  why-it-matters copy, embedded `GuideAction`, and dismissed state.
- [x] Add Alembic migration for `project_nudges`.
- [x] Add deterministic `NudgeService` that derives project-specific nudges
  from current project state instead of generating generic chat output.
- [x] Generate proactive nudges for:
  - broad ideas that need wedge comparison
  - projects with enough research for a first validation test
  - validation plans/missions with no logged results
  - weak evidence areas such as willingness to pay or unsupported claims
- [x] Cap visible nudges to at most two active nudges.
- [x] Add nudge APIs:
  - `GET /api/projects/{project_id}/nudges`
  - `POST /api/projects/{project_id}/nudges/{nudge_id}/dismiss`
- [x] Add nudge display in the persistent Guide panel.
- [x] Add a compact nudge surface to the project overview.
- [x] Let users dismiss nudges and keep dismissal persisted.
- [x] Route nudge action cards through existing guide action navigation.

## V1 Sprint 27 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_nudges.py`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_nudges.py app/tests/test_guide.py app/tests/test_project_overview.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test created a disposable project, added evidence,
  extracted assumptions, confirmed two project-specific nudges, dismissed one,
  and confirmed it no longer appeared in active nudges.
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 28 Scope

- [x] Refresh the primary fitness-coach demo into a guided strategic journey
  rather than a generic seeded data project.
- [x] Seed a messy original idea, structured intake, Thesis Canvas, thesis
  evolution events, and rejected directions.
- [x] Seed Wedge Explorer options with a recommended narrow wedge and explicit
  avoid/research-later alternatives.
- [x] Seed a validation mission with interpreted results so the project reaches
  the Decision Coach instead of stopping at raw experiment output.
- [x] Seed a Decision Coach-aligned decision record recommendation that
  preserves the "continue research" path and trace links to the relevant
  assumption and experiment.
- [x] Reset demo nudges on refresh so the guided project is repeatable.
- [x] Update the project list demo entry point and API response so the demo
  opens at the Guide panel.
- [x] Extend demo seed counts and tests to verify the Sprint 28 journey objects.

## V1 Sprint 28 Verification

Checks run:

- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_demo_eval_workflows.py -q`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests/test_demo_eval_workflows.py apps/api/app/tests/test_thesis_canvas.py apps/api/app/tests/test_wedge_explorer.py apps/api/app/tests/test_validation.py apps/api/app/tests/test_guide.py apps/api/app/tests/test_project_overview.py -q`
- [x] `apps/api/.venv/bin/pytest apps/api/app/tests -q`
- [x] `apps/api/.venv/bin/ruff check apps/api/app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` created the guided demo
  project and returned `#guide` with seeded thesis canvas, thesis evolution,
  wedges, validation mission, interpretation, and decision counts.
- [x] Browser QA in the Codex in-app browser: clicked `Load guided demo`,
  verified redirect to `#guide`, checked Guide, Thesis, Validation, Decision,
  and History markers, confirmed no browser console warnings/errors, and ran
  desktop/mobile layout probes for horizontal overflow and button text overflow.

## V1 Sprint 30 Scope

- [x] Add `after_that` to guide recommendations so the Guide explains what
  happens after the primary action.
- [x] Add `recommended_action` to guide chat responses.
- [x] Cap guide secondary actions to three.
- [x] Replace vague guide action labels with specific routing commands such as
  "Show evidence behind the blocker," "Rewrite thesis with current wedge,"
  "Compare wedge options," "Open validation result form," and "Prepare decision
  record."
- [x] Keep backward-compatible aliases for older guide action IDs.
- [x] Align project nudges and Decision Coach evidence actions with the new
  guide action-router vocabulary.
- [x] Replace the inline guide disclosure with a bottom-right `Ask Thesys`
  button and bottom drawer.
- [x] Update the Guide panel copy to the Sprint 30 structure: what matters now,
  why, do this next, after that, and actions.
- [x] Update prompt chips to be action-oriented.

## V1 Sprint 30 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_nudges.py app/tests/test_wedge_explorer.py app/tests/test_thesis_canvas.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided demo
  project successfully.
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 31 Scope

- [x] Add a derived `GET /api/projects/{project_id}/idea-story` API that
  summarizes original idea, current thesis, selected wedge, rejected
  directions, why the idea changed, current blocker, and next proof from
  existing Thesis Canvas, wedge, and evolution records.
- [x] Add a compact "How this idea has changed" section to Current Step.
- [x] Replace the Current Step peer-field grid with a storyline that keeps
  original idea, thesis, selected wedge, rejected direction, blocker, and next
  proof visible together.
- [x] Simplify Wedge Explorer's default view to show the recommended wedge, one
  avoid-for-now/rejected direction, and one research-later/promising direction.
- [x] Keep the full Wedge Explorer available behind "Compare all wedges."
- [x] Extend Guide chat so it can answer idea evolution, wedge rationale,
  rejected broad-direction, and next-proof questions.
- [x] Add tests for Idea Story derivation and Sprint 31 Guide prompts.

## V1 Sprint 31 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_thesis_canvas.py app/tests/test_guide.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `pnpm --filter thesys-web test`
- [x] `docker compose config`
- [x] `docker compose restart api web temporal-worker`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and `GET /api/projects/{project_id}/idea-story` returned the
  original idea, current thesis, selected wedge, rejected directions, blocker,
  and next proof.
- [ ] Browser QA in the Codex in-app browser is blocked because Computer Use
  is not allowed to access `com.openai.codex`. Per the sprint request, no
  external browser QA was attempted.

## V1 Sprint 32 Scope

- [x] Update the homepage headline/subheading around the Sprint 32 promise:
  rough idea → wedge → biggest unknown → next proof.
- [x] Rename the default queue to "Ideas in progress" and reduce project rows
  to the allowed essentials: thesis/description, verdict, next action, stage,
  and evidence summary.
- [x] Hide disposable smoke, QA, and browser-test projects from the homepage by
  default while keeping the guided fitness-coach demo visible.
- [x] Add a "Show test projects" filter for inspecting hidden QA projects.
- [x] Keep new-investigation intake focused after preview by showing one
  recommended path and collapsing alternate paths.
- [x] Route newly created investigations to Current Step by default, with
  explicit actions for Current Step, research, or wedge comparison.
- [x] Compress Current Step so the primary job, CTA, thesis, selected wedge,
  biggest unknown, and next proof are visible first.
- [x] Move supporting evidence, recovery, blocker details, and idea-history
  details behind Inspect sections.
- [x] Apply Sprint 32 terminology across visible detail labels: evidence
  summary, competitors and substitutes, full research memo, active test, and
  assumptions behind the decision.
- [x] Add frontend tests for homepage test-project filtering.

## V1 Sprint 32 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned `#current-step` with seeded thesis canvas, thesis
  evolution, wedges, validation mission, interpretation, and decision counts.
- [x] Browser QA in the Codex in-app browser: verified homepage copy, "Ideas in
  progress," default hiding of QA/browser/endpoint-audit/demo clutter, "Show
  test projects" reveal behavior, guided demo visibility, direct Current Step
  landing on `#current-step`, compact thesis/wedge/biggest unknown/next proof
  story, collapsed Inspect sections, and no browser warn/error console logs.

## V1 Sprint 33 Scope

- [x] Make Current Step the quiet default project workspace surface by removing
  the default status bar, project map/sidebar, mobile project menu, mobile
  workspace action, and mobile decision spine from that tab.
- [x] Keep the current verdict/status, one primary CTA, and current test path
  visible before any process detail.
- [x] Preserve the active idea story: current thesis, selected wedge, biggest
  unknown, and next proof remain visible together.
- [x] Move project nudges, decision context, evidence summary, recovery detail,
  supporting workspace links, and decision history behind Inspect details.
- [x] Keep Ask Thesys available through the floating guide drawer instead of a
  permanent guide panel or secondary button row on the default Current Step.
- [x] Preserve workspace routes and deep links for Test, Research, Shape,
  Decide, and History from the inspect controls.
- [x] Add frontend regression coverage for the quiet Current Step rendering
  contract.

## V1 Sprint 33 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned
  `/projects/3160c9e9-5c3e-491f-9cc5-6e8081c2917c#current-step`.
- [x] Manual Chrome browser QA against the guided demo project: verified the
  desktop default Current Step shows one main panel, one primary CTA, the
  current test path, collapsed Inspect details, and the floating Ask Thesys
  drawer without the old project map/sidebar or default status/process chrome.
- [x] Manual responsive QA in Chrome DevTools at 400px width: verified the
  mobile Current Step starts with the project title, primary CTA, current test
  path, Inspect details, and Ask Thesys without the old mobile menu or mobile
  decision spine.

## V1 Sprint 34 Scope

- [x] Add a reusable `ProjectInspectDrawer` driven by existing project overview
  and idea-story data.
- [x] Move advanced status, evidence, assumptions, test path, research details,
  decision history, and project context into the drawer.
- [x] Replace the inline Current Step inspect/evolution detail with an
  `Inspect details` button that opens local drawer state without changing the
  route or hash.
- [x] Keep the closed Current Step focused on the verdict/current step, one
  primary CTA, current thesis, selected wedge, biggest unknown, next proof, and
  lightweight Ask Thesys access.
- [x] Replace the desktop project map/sidebar and mobile project menu with a
  compact `Explore` control backed by `projectNavigationItems`.
- [x] Keep canonical Explore routing at `#current-step`, `#shape`, `#research`,
  `#test`, `#decide`, and `#history`.
- [x] Preserve legacy aliases and deep-link anchors such as `#guide`,
  `#decision`, `#evidence`, `#validation`, `#record`,
  `#validation-mission`, and `#record-decision-panel`.
- [x] Add frontend regression coverage for the quiet Current Step, Inspect
  drawer sections/actions, responsive sheet sizing, compact Explore control,
  removed legacy navigation chrome, and routing compatibility.

## V1 Sprint 34 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose config`
- [x] `docker compose restart api web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned
  `/projects/3160c9e9-5c3e-491f-9cc5-6e8081c2917c#current-step`.
- [x] Desktop browser QA in the Codex in-app browser: verified the quiet
  Current Step has one dominant CTA, current thesis/wedge/unknown/proof path,
  Inspect details, Ask Thesys, no default evidence metrics/status history, no
  old Guided mode sidebar/mobile project menu labels, and no app console
  warnings/errors.
- [x] Desktop Inspect drawer QA in the Codex in-app browser: verified all
  required sections and action links, close-button focus, Escape close,
  backdrop close, body scroll lock cleanup, and no URL hash change for drawer
  open/close.
- [x] Desktop Explore QA in the Codex in-app browser: verified compact
  navigation opens with Current Step, Shape, Research, Test, Decide, and History;
  each item closes Explore and routes to the canonical hash.
- [x] Deep-link QA in the Codex in-app browser: verified `#research`,
  `#validation-mission`, `#record-decision-panel`, and `#history` land on the
  expected workspace surface without restoring old navigation chrome.
- [x] Responsive browser QA at 410x844 through a temporary Chrome CDP session:
  verified the quiet Current Step has no horizontal overflow, Inspect details
  opens as a full-screen sheet with required sections/actions and closes without
  changing `#current-step`, Explore opens as a full-screen sheet, and selecting
  Shape routes to `#shape`.

## V1 Sprint 35 Scope

- [x] Simplify `/projects` into a launcher with one headline, one supporting
  sentence, one dominant `Start investigation` CTA, and secondary
  `Load guided demo` access.
- [x] Remove the right-side launcher/demo cards from `/projects`.
- [x] Collapse search, stage/risk filters, sort, compact rows, and
  `Show test projects` behind one `Filter` disclosure on every viewport.
- [x] Preserve project queue behavior, keyboard shortcut entry points, and
  disposable test/demo/audit hiding by default, including existing local audit
  rows.
- [x] Convert `/projects/new` to a single-column rough-idea flow without
  persistent explanatory sidebars.
- [x] Keep context checks, clarifying questions, assumptions continuation,
  thesis preview, recommended path, loading states, validation errors, sample
  idea, and existing API calls.
- [x] Make `Continue to Current Step` the dominant post-preview creation action,
  with `Run research` and `Compare wedges` as secondary actions.
- [x] Preserve primary routing to `/projects/{id}#current-step` and secondary
  routing to `#research` and `#wedge`.
- [x] Add frontend regression coverage for disposable row hiding, collapsed
  launcher filters, removed competing launcher cards, and single-column new
  investigation structure.

## V1 Sprint 35 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose stop web`
- [x] `docker compose rm -f web`
- [x] `docker volume rm thesys_web_next_cache`
- [x] `docker compose up -d web`
- [x] `docker compose restart web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned
  `/projects/3160c9e9-5c3e-491f-9cc5-6e8081c2917c#current-step`.
- [x] Desktop Codex in-app browser QA on `/` and `/projects`: verified `/`
  redirects to `/projects`, only one dominant `Start investigation` CTA is
  visible, `Load guided demo` is secondary, the old right rail cards are gone,
  filters are collapsed behind `Filter`, disposable test/demo/audit rows are
  hidden by default, `Show test projects` lives inside the filter disclosure and
  reveals hidden rows, and the app console reported no warnings/errors.
- [x] Desktop Codex in-app browser QA on `/projects/new`: verified the page is
  single-column, no persistent explanatory sidebar cards render, the sample
  rough idea previews a first thesis, possible wedge, biggest unknown, and
  recommended path, `Continue to Current Step` is primary, `Run research` and
  `Compare wedges` are secondary, and creating from preview opens
  `/projects/{id}#current-step`.
- [x] Mobile Codex in-app browser QA at 410px width on `/projects`: verified no
  horizontal overflow, the primary CTA stays obvious, the filter menu opens
  cleanly, and `Show test projects` is usable inside the disclosure.
- [x] Mobile Codex in-app browser QA at 410px width on `/projects/new`: verified
  no horizontal overflow, the single-column preview remains usable, and the
  post-preview Current Step/research/wedge action row fits and remains usable.

## V1 Sprint 36 Scope

- [x] Standardize empty states across default project surfaces so they state
  what is missing, why it matters, and the next action.
- [x] Reduce non-primary card treatment on `/projects`, `/projects/new`,
  Current Step supporting sections, Explore, and Inspect by using border bands,
  dividers, compact rows, and sheet sections.
- [x] Remove duplicate post-preview intake copy by replacing the old
  `Continue with assumptions` path with a single dominant
  `Continue to Current Step` action that preserves assumptions when needed.
- [x] Keep `/projects` as one dominant `Start investigation` launcher with
  secondary guided-demo access and collapsed filters.
- [x] Keep `/projects/new` as a single-column rough-idea flow with stacked
  mobile actions and no persistent explanatory sidebar.
- [x] Keep Current Step focused on one current action, current thesis, selected
  wedge, biggest unknown, next proof, Inspect details, and Ask Thesys.
- [x] Keep Inspect details advanced and route-local; opening and closing it does
  not change the hash.
- [x] Add Sprint 36 source-structure regression tests for quiet launcher/intake
  structure, stale card/navigation skeleton prevention, empty-state wording, and
  the Current Step CTA wording.

## V1 Sprint 36 Verification

Checks run:

- [x] `pnpm --filter thesys-web test`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `docker compose config`
- [x] `docker compose restart web` after the IDE browser showed stale Next.js
  output for `/projects/new`.
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack API smoke test: `POST /api/demo/seed` refreshed the guided
  demo project and returned
  `/projects/3160c9e9-5c3e-491f-9cc5-6e8081c2917c#current-step`.
- [x] Desktop Codex in-app browser QA: verified `/` redirects to `/projects`;
  `/projects` has one dominant `Start investigation` CTA, secondary guided demo
  access, collapsed filters, and no right-rail launcher cards; `/projects/new`
  is single-column, previews cleanly, and routes `Continue to Current Step` to
  `/projects/{id}#current-step`; no horizontal overflow or app console
  warnings/errors were observed.
- [x] Desktop guided-demo browser QA: verified `#current-step` shows one clear
  current action, current thesis, selected wedge, biggest unknown, next proof,
  Inspect details, and Ask Thesys without default status/card clutter.
- [x] Desktop Inspect and Explore browser QA: verified Inspect opens/closes
  cleanly without changing the route/hash, advanced details remain grouped in
  drawer sections, Explore opens Current Step, Shape, Research, Test, Decide,
  and History, and legacy deep links `#research`, `#validation-mission`,
  `#record-decision-panel`, and `#history` land on the correct surfaces.
- [x] Mobile Codex in-app browser QA at 410px width: verified `/projects` has no
  horizontal overflow, primary CTA remains obvious, and the Filter disclosure is
  usable; `/projects/new` has no horizontal overflow and post-preview actions
  wrap cleanly.
- [x] Mobile guided-demo browser QA at 410px width: verified Current Step places
  the current action and test path before advanced detail, Inspect opens as a
  full-screen sheet, Explore opens as a full-screen sheet, and selected Explore
  destinations route correctly.

## V1 Sprint 37 Scope

- [x] Add embedding provider configuration for deterministic local embeddings
  and LiteLLM/OpenAI-compatible production embeddings, including model,
  provider, version, timeout, retry, and dimension validation.
- [x] Store embedding provenance on `evidence_chunks`: provider, model,
  dimension, version, embedded timestamp, and embedding error.
- [x] Add a migration for embedding provenance columns plus a pgvector ANN index,
  preferring HNSW and falling back to IVFFlat where needed.
- [x] Preserve deterministic dev embeddings while adding provider metadata to
  ingestion traces and retrieval results.
- [x] Implement the Postgres pgvector SQL retrieval path for semantic and hybrid
  evidence search, with project/source/freshness/metadata filters applied before
  vector ranking.
- [x] Keep deterministic Python retrieval as the non-Postgres/configured
  fallback path and return explicit fallback diagnostics.
- [x] Persist retrieval diagnostics in `ai_steps.output_json` and return them
  through the evidence retrieval API.
- [x] Add `POST /api/projects/{project_id}/evidence/reembed` with dry-run,
  project/workspace scope, current-provider eligibility checks, and per-chunk
  failure reporting.
- [x] Surface retrieval path diagnostics, per-result embedding provenance, and
  re-embedding maintenance controls in the advanced Evidence detail surface.
- [x] Extend AI status, tool schemas, docs, Docker Compose, `.env.example`, and
  LiteLLM config for the production embedding/retrieval path.

## V1 Sprint 37 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_embedding_service.py app/tests/test_ai.py`
- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_research_history_eval.py app/tests/test_tool_boundary.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `docker compose config`
- [x] `docker compose restart api temporal-worker web`
- [x] `curl -fsS http://localhost:8000/health`
- [x] `curl -I -fsS http://localhost:3000/projects`
- [x] Live-stack AI status smoke test: verified embedding provider/model/version,
  dimension, retrieval vector path, and Python fallback configuration are
  returned by `/api/ai/status`.
- [x] Live-stack API fixture smoke test: created `Sprint 37 browser check`,
  ingested one note source, retrieved one hybrid result through the HNSW
  pgvector SQL path, and verified diagnostics reported `used_sql_vector_search`
  with no fallback.
- [x] Live-stack re-embed API smoke test: dry-run re-embed scanned one chunk,
  skipped it as already current, and returned zero failures.
- [x] Desktop Codex in-app browser QA: opened the fixture project, navigated
  Research -> Inspect -> Evidence summary, ran a hybrid source-chunk search,
  verified the rendered `Retrieval: pgvector SQL` diagnostics, opened the result
  receipt, verified retrieved text plus embedding provenance, and confirmed
  `Dry run` and `Re-embed project` maintenance summaries render correctly.
- [x] Browser console QA: no app console errors were present after the Sprint 37
  verification flow.

## V1 Sprint 38 Scope

- [x] Add reusable retrieval pipeline service with broad-query planning,
  strategic intent classification, target entity/evidence-type extraction, and
  subquery decomposition.
- [x] Run semantic, keyword, metadata-filtered, freshness-boosted, and
  credibility-aware retrieval through the existing pgvector SQL path with Python
  fallback.
- [x] Add deterministic reranking by default, disabled mode, and optional
  LiteLLM reranker configuration with deterministic fallback on provider errors.
- [x] Assemble bounded context with near-duplicate suppression, source diversity,
  minimum context score, token budget enforcement, and preserved source/chunk
  IDs.
- [x] Extend retrieval API schemas with rerank score, final rank, context
  inclusion, selection reason, nested query plan, reranker, context, and quality
  diagnostics.
- [x] Wire the pipeline into evidence retrieve, opportunity brief evidence
  retrieval, agentic research tool execution, evidence selection, follow-up
  retrieval, final memo structured content, and V1 research eval metrics.
- [x] Keep retrieval-quality visibility in existing Inspect, workflow trace,
  evidence search, memo review, and eval/check surfaces only.
- [x] Add reranker/context configuration to `.env.example`, Docker Compose,
  README, AI status, and frontend API types.
- [x] Refine redaction so real secrets remain redacted while non-secret
  retrieval token counts and token budgets remain inspectable.

## V1 Sprint 38 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_opportunity_brief.py app/tests/test_agentic_research.py app/tests/test_research_history_eval.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `pnpm --filter thesys-web test`
- [x] `docker compose config`
- [x] Local-stack browser QA: created `Sprint 38 retrieval QA`, seeded four
  sources, ran the broad query `Which wedge is strongest and what proof is
  missing?`, and verified Inspect showed pgvector SQL retrieval, 3 subqueries,
  deterministic reranker, 1 selected chunk, 47/3500 context tokens, precision
  1.00, recall 0.25, duplicate suppression, and no noisy source selected.
- [x] Browser brief QA: regenerated an opportunity brief in stub mode, verified
  cited claims and appendix entries preserved source/chunk-backed quotes, and
  opened the trace showing 5 retrieval queries, deterministic reranker, 2
  context chunks, and 89/3500 context tokens.
- [x] Browser agentic research QA: ran an agentic evidence review in stub mode,
  verified the memo stored 6 retrieval diagnostics plus 4 selected context
  chunks at 226/3500 tokens, and confirmed Evidence Checks showed multi-stage
  retrieval strategy, reranker visibility, context assembly, and retrieval
  quality report metrics in Inspect.
- [x] Browser console and responsive QA: console errors/warnings were empty for
  the app tab; at 410px width, the Inspect evidence-check content had no
  horizontal overflow, no overflowing buttons, and retrieval-quality lines
  remained readable and scrollable.

## V1 Sprint 39 Scope

- [x] Preserve the existing guide intent guardrail, bounded out-of-scope
  refusal, deterministic fallback path, and action-card routing.
- [x] Add traced `guide_chat` AI runs/steps for Ask Thesys with prompt version,
  model/provider metadata, latency/cost fields, intent guardrail output,
  retrieval context output, and answer summaries.
- [x] Ground in-scope Ask Thesys answers through the governed
  `search_project_evidence` read-only tool and return cited evidence IDs,
  retrieval diagnostics, confidence level, unsupported/missing evidence, and
  trace IDs in the guide chat response.
- [x] Add live-mode structured LLM guide answers with citation filtering,
  existing-action filtering, untrusted retrieved-content instructions, and
  deterministic fallback if generation or validation fails.
- [x] Keep chat non-mutating: proposal-style prompts route to existing
  navigation/workflow actions, including scoped research-plan routing, without
  executing write/proposal tools directly from chat.
- [x] Add bounded session context by sending only the last six guide turns from
  the panel and including the trimmed context in live LLM prompt input.
- [x] Surface compact Ask Thesys grounding metadata in the guide panel without
  turning the UI into a transcript-heavy chat surface.
- [x] Extend guide tests for grounded retrieval metadata, AI run/step traces,
  read-only tool logging, long-query truncation, non-mutating proposal prompts,
  research-plan routing, live structured LLM output, citation filtering, action
  filtering, and bounded recent-turn prompt context.

## V1 Sprint 39 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_guide.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `pnpm --filter thesys-web test`
- [x] `docker compose config`
- [x] Local-stack functional QA on alternate ports with a disposable SQLite
  model-created database: started the API on `127.0.0.1:8010` and web on
  `127.0.0.1:3010`, seeded the guided demo project, asked `What does the
  evidence say about weekly coach check-ins?`, and verified the guide response
  returned cited evidence IDs, medium confidence, retrieval diagnostics,
  related evidence entities, and an AI run trace ID.
- [x] Local-stack non-mutation QA: asked `Create and apply a validation plan for
  the riskiest assumption.` and verified the response returned existing guide
  actions while the tool invocation log contained only read-only
  `search_project_evidence` calls and no proposal/write invocation.

Manual environment note:

- Codex in-app browser QA was blocked in this session: the Browser plugin setup
  succeeded but no `iab`/browser target was registered, and the local
  app-control surface timed out while listing apps. Docker-backed localhost
  verification was also unavailable because Docker returned internal API errors
  and its owned `3000`/`8000` listeners did not respond.

## V1 Sprint 40 Scope

- [x] Add governed external search settings and a provider boundary with
  deterministic and Tavily adapters.
- [x] Keep external search disabled by default, with deterministic local mode
  and opt-in Tavily via `EXTERNAL_SEARCH_ENABLED`, `EXTERNAL_SEARCH_PROVIDER`,
  and `TAVILY_API_KEY`.
- [x] Route approved research-sprint source discovery through external search
  when enabled, dedupe by normalized URL, store provider/query/rank/retrieval
  provenance, and preserve the existing review/approval/rejection flow.
- [x] Carry search provenance into evidence source metadata and chunk metadata
  after source approval, including fallback snapshot ingestion when remote fetch
  fails.
- [x] Add multimodal evidence extraction through a backend extractor boundary
  with deterministic fixture extraction by default and LiteLLM multimodal
  extraction for live image/PDF paths.
- [x] Support PNG, JPG, JPEG, and WebP uploads; keep text-native PDFs on `pypdf`
  and route low-text PDFs to multimodal fallback only when configured.
- [x] Add `source_metadata` storage and expose evidence source `metadata` through
  the existing evidence API.
- [x] Keep search and extraction details behind Research/Evidence inspection
  controls so Current Step stays quiet.
- [x] Extend V1 research eval with search relevance, source diversity,
  duplicate-rate, and provenance-coverage metrics.
- [x] Document external search and multimodal extraction settings in
  `.env.example`, Docker Compose, README, API status, and frontend API types.

## V1 Sprint 40 Verification

Checks run:

- [x] `cd apps/api && .venv/bin/ruff check app`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_discovery.py app/tests/test_evidence.py app/tests/test_research_history_eval.py`
- [x] `cd apps/api && .venv/bin/pytest`
- [x] `cd apps/api && .venv/bin/alembic upgrade head --sql`
- [x] `pnpm --filter thesys-web typecheck`
- [x] `pnpm --filter thesys-web test`
- [x] `docker compose config`
- [x] IDE browser deterministic connector QA on alternate local ports
  `127.0.0.1:3010`/`127.0.0.1:8010`: created disposable project
  `Sprint 40 connector QA`, planned and approved an evidence review, ran
  `Find sources`, confirmed deterministic candidates showed provider/query/rank
  and retrieval time, approved one source, rejected one source, and confirmed
  the approved source appeared as ready evidence.
- [x] Browser evidence inspection QA: opened the approved source detail and
  confirmed search provider, query, rank, retrieval timestamp, risk, and content
  type appeared only behind the provenance details control.
- [x] Browser retrieval QA: searched stored chunks for deterministic-source text
  and confirmed the approved URL source was retrieved.
- [x] Browser multimodal QA: uploaded the Sprint 40 fixture image through the
  evidence file endpoint, inspected it in the browser, confirmed ready status,
  deterministic extraction metadata, extracted text preview, and retrieval by a
  phrase from the extracted text.
- [x] Browser PDF QA: uploaded a normal text PDF, inspected it in the browser,
  and confirmed `pypdf` metadata without multimodal fallback.
- [x] Browser quality QA: browser console errors/warnings were empty, app API
  responses during the verified flow were 2xx, and the 410px viewport had no
  horizontal overflow with extraction details absent from Current Step.

Manual environment note:

- The local Docker API/web ports were already occupied, so manual browser QA used
  isolated alternate ports plus a temporary SQLite database and local object
  storage. The optional live Tavily path was not run because no `TAVILY_API_KEY`
  was configured for this session.

## Recently Completed V1 AI Engineering Upgrade Track

Sprints 41-50 landed the following baseline capabilities on the AI upgrade
branch. Each item also has remaining production-grade work tracked in Sprints
51-60:

1. V1 Sprint 41: Security, AI Safety, and Abuse Hardening
   - Added SSRF-resistant URL validation, redirect re-checks, response-size
     limits, upload validation, file-name sanitization, and audit events for
     rejected ingestion.
2. V1 Sprint 42: Context Engineering and Prompt Context Architecture
   - Added typed context packs with token budgets, provenance, dropped-item
     diagnostics, and untrusted-content rules for Ask Thesys and research.
3. V1 Sprint 43: Multiple Memory Types and Memory Management
   - Added typed project memory records, workflow-aware memory selection,
     memory explanation APIs, and governed memory indexing.
4. V1 Sprint 44: MCP Adapter and External Tool Integration Boundary
   - Added MCP-shaped HTTP endpoints over the existing governed tool registry,
     preserving approvals, permissions, and audit logs.
5. V1 Sprint 45: Advanced Retrieval Quality and Citation Verification
   - Added shared citation verification and stronger source-diverse context
     selection.
6. V1 Sprint 46: Ask Thesys Streaming, Tool Proposals, and Guide Evals
   - Added guide SSE streaming, proposal-only guide actions for state changes,
     and guide grounding/governance evals.
7. V1 Sprint 47: Observability, Cost Controls, and CI Eval Gates
   - Added AI accounting, budget/circuit checks, `/evals/ai`, and
     `scripts/eval_ai_quality.py`.
8. V1 Sprint 48: External Research and Multimodal Intelligence Hardening
   - Added source provenance helpers, canonical URL/content-hash dedupe, fetch
     failure classification, prompt-injection markers, source quality signals,
     and PDF page lineage.
9. V1 Sprint 49: Codebase Architecture Cleanup
   - Added shared service utilities for metadata merging and workflow run
     finalization, with characterization tests covering evidence and retrieval.
10. V1 Sprint 50: Developer Documentation and Code Navigation
    - Added README updates, developer docs under `docs/`, and concise docstrings
      for context, memory, MCP, provenance, and shared service utilities.

The main homepage and primary project workflow remain straightforward. Advanced
diagnostics, trace details, memory internals, security findings, and retrieval
explanations stay hidden by default and are available through metadata,
inspection surfaces, eval output, or developer docs.

Unfinished Sprint 41-50 gaps are tracked as follows. The concise table below is
the status summary; the concrete implementation tasks, tests, and deferred
verification items live in the `SPRINT_51_60_TODO.md` gap coverage ledger.

| Prior sprint gap | Owning follow-up sprint |
|---|---|
| Sprint 41 rate limits, workflow concurrency, dependency audits, live-provider egress, production auth, and threat model | Sprint 54, with eval/report gates in Sprint 56 |
| Sprint 42 central context compiler, workflow profiles, memory-aware context, compression, conflict detection, and context evals | Sprint 51 |
| Sprint 43 memory compaction, preference capture, conflict resolution, memory browser, write-review workflow, and context-pack integration | Sprint 51 |
| Sprint 44 real MCP JSON-RPC transport, stdio/SSE, client configs, and external harnesses | Sprint 52 |
| Sprint 45 Postgres text search/BM25 semantics, MMR/diversity, cross-encoder-compatible reranking, golden retrieval evals, and artifact-wide citation verification | Sprint 55 |
| Sprint 46 true Ask Thesys streaming, cancellation, live retrieval/tool events, citation drilldowns, and stronger guide evals | Sprint 53 |
| Sprint 47 OpenTelemetry, CI gates, eval trend reports, prompt/schema changelog, and pre-call budget enforcement | Sprint 54 and Sprint 56 |
| Sprint 48 readability extraction, screenshots, OCR, table extraction, richer source quality, and live provider QA | Sprint 58, with required fixture-backed proof for maintained readability extraction, raw/page/screenshot snapshot metadata, OCR confidence/page metadata, positive table extraction, exact quote provenance, retrieval use of source quality, collapsed citation/Evidence Inspect metadata, and explicit live-provider-unavailable warnings |
| Sprint 49 feature-package refactor, service splits, typed DTOs, characterization coverage, and layout docs | Sprint 59 |
| Sprint 50 architecture diagrams, post-refactor developer navigation, targeted code docs, and production/deployment posture | Sprint 60 |

## V1 Sprint 51 Branch Progress

Sprint 51 is implemented on `codex/v1-sprints-51-60`:

- Added a shared `ContextCompiler` with explicit workflow profiles for
  assumption extraction, Ask Thesys, agentic research, opportunity briefs,
  competitor analysis, validation planning, validation-result interpretation,
  and decision recommendation.
- Routed the major AI workflows through compiled context packs with workflow
  metadata, token budgets, selected memory, dropped-item explanations,
  citation IDs, and untrusted-content safety metadata.
- Added Memory V2 policy behavior for workflow-aware selection, excluded-memory
  reasons, proposed preference memory, approval-gated compaction candidates,
  conflict detection/resolution, proposal approval/rejection, and
  recommendation-to-memory provenance links.
- Added hidden-by-default Inspect surfaces for project memory and context
  diagnostics so the homepage and primary workflow stay focused.
- Added `/api/projects/{project_id}/evals/context` and wired the static AI eval
  gate to check context profiles, relevant inclusion, poisoned-instruction
  isolation, stale exclusion, citation scoping, dropped-context explanations,
  and memory-policy visibility.

Sprint 51 verification run:

- [x] `python3 -m compileall -q` on the touched API modules
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_validation.py app/tests/test_agentic_research.py app/tests/test_demo_eval_workflows.py -q --maxfail=1`
- [x] `cd apps/api && .venv/bin/pytest -q`
- [x] `python3 scripts/eval_ai_quality.py --json`
- [x] `git diff --check`
- [x] `rg -n "<{7}|={7}|>{7}" .`
- [ ] `pnpm --filter thesys-web typecheck` could not complete in this
  environment because pnpm failed before TypeScript while fetching registry
  tarballs and supply-chain metadata (`ECONNRESET` / `fetch failed`).

## V1 Sprint 52 Branch Progress

Sprint 52 is implemented on `codex/v1-sprints-51-60`:

- Added MCP JSON-RPC endpoints at `/api/mcp/rpc` and
  `/api/mcp/projects/{project_id}/rpc`.
- Implemented `initialize`, `notifications/initialized`, `tools/list`, and
  `tools/call` with request ID preservation, capability negotiation, generated
  tool schemas, structured protocol errors, and project-scoped tool calls.
- Preserved the governed tool boundary: MCP calls still use RBAC, approval
  requests, audit events, risk levels, redaction, and project/workspace scoping.
- Kept the legacy MCP-shaped HTTP routes for simple local clients.
- Added `scripts/mcp_stdio_server.py` for stdio-based local developer-agent
  clients and `scripts/eval_mcp_contract.py` for live initialize/list/read/
  proposal contract checks.
- Updated README and `docs/GOVERNANCE_AND_MCP.md` with JSON-RPC examples,
  stdio client configuration, and capability limits.

Sprint 52 verification run:

- [x] `python3 -m compileall -q apps/api/app/mcp/adapter.py apps/api/app/routers/mcp.py apps/api/app/schemas/mcp.py scripts/mcp_stdio_server.py scripts/eval_mcp_contract.py`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_security_governance.py -q --maxfail=1`
- [x] `cd apps/api && .venv/bin/pytest -q`
- [x] `python3 scripts/eval_ai_quality.py --json`

## V1 Sprint 53 Branch Progress

Sprint 53 is implemented on `codex/v1-sprints-51-60`:

- Replaced the Ask Thesys stream route that previously emitted one post-hoc
  delta with a service-owned SSE event generator.
- Added a stable guide event protocol for `message_started`, `metadata`,
  `retrieval_started`, `tool_call_started`, `tool_call_completed`,
  `retrieval_result`, `context_compiled`, `proposal_created`, `answer_delta`,
  `timeout`, `cancelled`, `error`, and `final`.
- Added OpenAI-compatible LiteLLM streaming support and live-mode guide
  streaming that extracts answer deltas from the provider's structured JSON
  while still validating the final schema before persistence.
- Added timeout handling with a safe final response and no project-state writes.
- Added cancellation persistence when the backend stream generator is closed;
  the UI also records a local `cancelled` event when the user aborts the stream.
- Added normalized citation drilldown metadata to guide responses, including
  source IDs, chunk IDs, title, URL, source type, excerpt, support status,
  context item IDs, and memory IDs.
- Updated the Ask Thesys panel to render progressive answer text, a compact
  cancel control, collapsed progress metadata, final action cards, and collapsed
  citation/context drilldowns.

Sprint 53 verification run:

- [x] `python3 -m compileall -q apps/api/app/ai/litellm_client.py apps/api/app/services/guide_service.py apps/api/app/routers/projects.py apps/api/app/schemas/guide.py apps/api/app/core/config.py`
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_guide.py -q --maxfail=1`
- [x] `cd apps/api && .venv/bin/pytest -q`
- [x] `python3 scripts/eval_ai_quality.py --json`
- [ ] `pnpm --filter thesys-web typecheck` could not complete in this
  environment because pnpm failed before TypeScript while fetching registry
  packages and npm attestation metadata (`ECONNRESET`). The retrying process was
  stopped after several minutes, so web tests and IDE browser QA remain blocked
  until registry access is stable.

## V1 Sprint 54 Branch Progress

Sprint 54 is implemented on `codex/v1-sprints-51-60`:

- Added production-auth shape for `AUTH_MODE=jwt` and `AUTH_MODE=api_key`.
  JWT mode verifies HS256 bearer tokens with issuer, audience, expiry, role, and
  workspace claims, plus active key IDs and revoked token IDs for rotation and
  revocation behavior. API-key mode verifies SHA-256 key hashes, denies revoked
  key hashes, and maps accepted keys to a service-account workspace membership.
- Dev auth remains local-only: `X-Dev-User-*` headers are rejected outside
  `AUTH_MODE=dev`.
- Added `security_policy_service.guarded_workflow` for expensive workflow
  policy: per-user/per-workspace rate limits, per-user/per-workspace
  concurrency limits, pre-call token/cost budget checks, provider-egress
  allowlist checks, and redacted audit events for denied route work.
- Routed the policy guard through Ask Thesys, research sprint planning, Temporal
  research starts/retries, source discovery, source candidate ingestion,
  competitor discovery, agentic research, evidence ingestion/retrieval/
  reembedding/reprocessing, opportunity briefs, competitor analysis,
  assumption/risk extraction, validation planning, validation interpretation,
  decision guidance, intake analysis, MCP JSON-RPC/tool calls, eval endpoints,
  and AI structured-output smoke tests.
- Added live-provider egress checks to LiteLLM chat/streaming, LiteLLM
  embeddings, LiteLLM multimodal extraction, Tavily search, and LiteLLM health
  probes.
- Hardened URL fetch validation with optional domain allow/deny lists, port
  allowlists, fetched response content-type allowlists, redirect revalidation,
  and existing private/link-local/metadata-address protections.
- Added `scripts/audit_dependencies.py` and `scripts/security_check.py` for
  local/CI-friendly dependency, redaction, SSRF, auth/RBAC, MCP/tool-boundary,
  budget, and provider-egress checks.
- Replaced the placeholder `docs/security.md` with current security posture and
  added `docs/THREAT_MODEL.md` covering uploads, URL fetching, DNS rebinding,
  prompt injection, model egress, MCP/tool access, Temporal activities, object
  storage, database multi-tenancy, auth tokens/API keys, logs/traces, and eval
  artifacts.

Sprint 54 verification run:

- [x] `cd apps/api && .venv/bin/ruff check ...` on touched security/auth/policy/router/test files
- [x] `python3 -m compileall -q` on touched API modules and security scripts
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_security_governance.py -q --maxfail=1` (`20 passed`)
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_security_governance.py app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py app/tests/test_ai.py app/tests/test_guide.py app/tests/test_research_sprints.py app/tests/test_research_discovery.py app/tests/test_opportunity_brief.py app/tests/test_competitors.py app/tests/test_validation.py app/tests/test_intake.py -q --maxfail=1`
- [x] `cd apps/api && .venv/bin/pytest -q` (`162 passed`)
- [x] `python3 scripts/security_check.py` (`31 passed` in the focused security slice, AI quality `10/10`, Docker Compose image inventory printed)
- [ ] Strict dependency audits are not fully runnable in this environment:
  `pip-audit` is not installed in the API venv and `pnpm audit --prod` hit npm
  registry `ECONNRESET` / `fetch failed`. The non-strict security check reported
  those issues and exited successfully after security tests and AI-quality evals
  passed.

## V1 Sprint 55 Branch Progress

Sprint 55 is implemented on `codex/v1-sprints-51-60`:

- Added retrieval policy settings for Postgres text search, hybrid text weight,
  MMR, max chunks per domain, max chunks per source type, max chunks per
  competitor, and no-op/deterministic/LiteLLM reranker providers.
- Added Postgres text-rank signals with
  `ts_rank_cd(websearch_to_tsquery(...))` combined with pgvector similarity for
  hybrid SQL retrieval.
- Added BM25-like local keyword scoring for deterministic SQLite/fallback
  retrieval.
- Added `retrieval_reranker_service.py` with no-op, deterministic, and
  LiteLLM cross-encoder-compatible adapters behind one interface.
- Added MMR source-diversity ordering plus source, domain, source-type, and
  competitor caps during context assembly.
- Expanded retrieval diagnostics with reranker adapter, MMR/cap settings,
  recall@k, precision@k, MRR, nDCG proxy, citation support rate, and
  unsupported-claim rate.
- Added richer citation verification outcomes: `supported`,
  `weakly_supported`, `unsupported`, `source_missing`, `stale_source`, and
  `filtered_as_unsafe`.
- Added claim-level citation outcome metadata to opportunity briefs, competitor
  analyses, and agentic research memos. Validation-plan artifacts explicitly
  mark citation verification as not applicable when no cited claims are
  generated.
- Added `retrieval_quality_eval_service.py` and
  `scripts/eval_retrieval_quality.py` for credential-free golden retrieval
  regression checks covering positive/negative evidence, duplicate removal,
  competitor/source coverage, prompt-injection filtering, stale-source handling,
  and citation support metrics.
- Updated `docs/RETRIEVAL_PIPELINE.md` and README portfolio language with the
  Sprint 55 retrieval and citation patterns.

Sprint 55 verification run:

- [x] `cd apps/api && .venv/bin/ruff check ...` on touched retrieval/citation files and eval script
- [x] `python3 -m compileall -q` on touched retrieval/citation modules and eval script
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py -q --maxfail=1` (`16 passed`)
- [x] `python3 scripts/eval_retrieval_quality.py` (`7/7` golden metrics passed)
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py app/tests/test_opportunity_brief.py app/tests/test_competitors.py app/tests/test_agentic_research.py app/tests/test_guide.py app/tests/test_validation.py app/tests/test_demo_eval_workflows.py app/tests/test_research_history_eval.py -q --maxfail=1` (`68 passed`)
- [x] `cd apps/api && .venv/bin/pytest -q` (`164 passed`)
- [x] `python3 scripts/eval_ai_quality.py --json` (`10/10`)

## V1 Sprint 56 Branch Progress

Sprint 56 is implemented on `codex/v1-sprints-51-60`:

- Added `scripts/eval_quality_gate.py` as the aggregate local quality gate for
  AI quality, retrieval quality, research-sprint evals, extraction readiness,
  MCP contract availability, pytest slices, security checks, and optional
  LangSmith export/upload.
- Added `scripts/eval_extraction_quality.py` for credential-free checks covering
  URL fetch policy, canonical dedupe, prompt-injection markers, PDF page
  lineage, multimodal boundaries, and source-quality signals.
- Added file-backed local eval artifacts under `reports/evals/`: latest JSON,
  Markdown, HTML, per-run JSON/Markdown/HTML, and JSONL trend history.
- Added guarded report and observability endpoints for latest eval report, trend
  history, and OpenTelemetry-compatible project metrics.
- Added hidden-by-default Inspect UI for quality-gate status, failing gates,
  trend rows, cache/cost/egress metrics, and report artifact paths.
- Added `docs/AI_CHANGELOG.md` for prompt, schema, context-pack, retrieval,
  memory, provider/reranker, and tool-schema changes.
- Added focused report generation, trend persistence, metric payload, and API
  access-control tests.

Sprint 56 verification run:

- [x] `python3 scripts/eval_extraction_quality.py --json` (`6/6`)
- [x] `cd apps/api && .venv/bin/ruff check ...` on touched eval/report/schema/router files and eval scripts
- [x] `cd apps/api && .venv/bin/python -m compileall ...` on touched eval/report/schema/router files and eval scripts
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py -q` (`3 passed`)
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-default LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json` (`warn`, `32/32`, only MCP contract warned because no running project/API was provided)
- [x] `python3 scripts/security_check.py` (security slice passed; strict dependency audit remained environment-limited)
- [x] `cd apps/api && .venv/bin/pytest -q` (`167 passed`)
- [ ] `pnpm --filter thesys-web typecheck` and `pnpm --filter thesys-web test`
  could not complete because pnpm repeatedly failed while fetching npm registry
  packages (`ECONNRESET` / `fetch failed`). Sprint 60 owns the retry plus IDE
  browser QA for the hidden eval-report Inspect surface.

## V1 Sprint 57 Branch Progress

Sprint 57 is implemented on `codex/v1-sprints-51-60`:

- Added DB-backed `AICacheEntry` and `AICacheEvent` records plus migration
  `0027_ai_cache_entries.py` for workspace/project-scoped cache entries, hashed
  keys, version payloads, access events, stale-denial reasons, and saved
  token/cost/latency estimates.
- Added `ai_cache_service` with key builders for embeddings, retrieval plans,
  rerank results, and optional guide answers. Cache versions include evidence
  corpus, memory, thesis, assumption, decision, retrieval policy, prompt/schema,
  provider/model, and source-quality policy metadata.
- Routed evidence chunk embedding, re-embedding, retrieval query embedding,
  retrieval-plan execution, and rerank results through cache-aware paths.
- Added optional non-streaming Ask Thesys answer caching. Semantic answer caching
  is disabled by default; live-provider answer caching requires explicit
  opt-in.
- Added cache flags to settings, `.env.example`, Docker Compose, `/api/ai/status`,
  and the existing AI status tooltip.
- Added cache status to retrieval diagnostics and the Evidence search detail
  line.
- Added cache metrics to eval observability: hits, misses, stale denials, saved
  tokens, saved cost, and saved latency.
- Extended `scripts/eval_quality_gate.py` with a `cache_quality` gate and added
  the cache tests to the default pytest quality slice.
- Added `app/tests/test_ai_cache_service.py` for project isolation, no raw-text
  cache keys, exact hits, stale denials after evidence/memory/thesis changes,
  prompt/schema version invalidation, and observability cache metrics.

Sprint 57 verification run:

- [x] `cd apps/api && .venv/bin/ruff check ...` on touched cache/config/schema/router/service/test/script files
- [x] `cd apps/api && .venv/bin/python -m compileall ...` on touched cache/config/schema/router/service/test/script files
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_ai_cache_service.py app/tests/test_eval_reports.py -q` (`9 passed`)
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_guide.py app/tests/test_retrieval_quality_eval.py -q --maxfail=1` (`31 passed`)
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s57 LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security` (`warn`, `39/39`; cache quality `8/8`, skipped/unavailable gates warned)
- [x] `cd apps/api && .venv/bin/pytest -q` (`173 passed`)
- [x] `python3 scripts/security_check.py` exited `0` after focused security tests and AI quality passed; strict dependency auditing remained environment-limited because `pip-audit` was unavailable in the API venv and `pnpm audit --prod` hit npm registry `ECONNRESET` / `fetch failed`.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s57-default LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json` (`warn`; AI quality, retrieval quality, research-sprint dataset, extraction quality, cache quality, pytest quality slice, and security check passed; MCP contract warned because no live API/project endpoint was supplied).
- [ ] `pnpm --filter thesys-web typecheck` and `pnpm --filter thesys-web test` did not reach TypeScript/tests. Both commands repeatedly hit npm registry package and attestation fetch failures (`ECONNRESET`, with one `ENOTFOUND`) during pnpm dependency-status/install work and were stopped after several minutes. Sprint 60 owns the retry plus browser QA for Sprint 57 cache diagnostics.
- [x] Sprint 57 commit recorded in branch history.

## V1 Sprint 58 Branch Progress

Sprint 58 is implemented on `codex/v1-sprints-51-60`:

- Added source snapshot IDs and explicit snapshot metadata for fetched HTML,
  including capture/final/canonical URLs, byte hash/size, redaction status,
  retention policy, local-mode storage absence reason, and screenshot
  availability.
- Upgraded HTML extraction metadata to record parser/provider, readability
  policy version, boilerplate-skip warnings, section headings, and normalized
  section offsets.
- Added deterministic OCR metadata for image and low-text PDF extraction,
  including confidence, method, provider/model, page numbers, and warnings.
- Added deterministic table extraction artifacts with headers, rows, cells,
  summaries, page/region provenance, confidence, and searchable text metadata.
- Added chunk-level quote provenance with extraction method, source snapshot ID,
  page/section/table/region locators, normalized quote offsets, and source
  artifact metadata.
- Expanded source-quality scoring with policy version, factors, explanation,
  extraction confidence, OCR/table confidence, screenshot availability,
  canonical/dedupe status, prompt-injection penalties, and retrieval weight.
- Fed source quality into deterministic retrieval reranking and result metadata.
- Enriched artifact and guide citation DTOs with optional source type,
  provenance, extraction, snapshot, source-quality, locator, quote-offset, and
  warning fields.
- Preserved rich citation provenance through citation verification and fallback
  citation creation for research, opportunity brief, and competitor artifacts.
- Added collapsed UI metadata surfaces in Evidence source details, retrieval
  results, Ask Thesys citation details, research memo citation details, and
  source discovery review provenance.
- Extended context eval report items to retain `provenance.metadata` for Inspect
  diagnostics.
- Replaced structural extraction readiness checks with fixture-backed
  `scripts/eval_extraction_quality.py` cases for messy HTML, prompt-injected
  HTML, OCR fallback, table-heavy documents, quote offsets, source-quality
  factors, and live-provider-unavailable warnings.

Sprint 58 verification run:

- [x] `cd apps/api && .venv/bin/ruff check ...` on touched extraction,
  provenance, retrieval, guide, citation, schema, test, and eval-script files.
- [x] `cd apps/api && .venv/bin/python -m compileall ...` on touched backend
  services/schemas and `scripts/eval_extraction_quality.py`.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py -q --maxfail=1` (`17 passed`).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_research_discovery.py app/tests/test_agentic_research.py app/tests/test_opportunity_brief.py app/tests/test_guide.py -q --maxfail=1` (`37 passed`).
- [x] `cd apps/api && .venv/bin/pytest -q` (`174 passed`).
- [x] `python3 scripts/eval_extraction_quality.py --json` (`7/7` passed with
  explicit warnings for missing Tavily live QA and deterministic multimodal mode).
- [ ] `pnpm --filter thesys-web typecheck` did not reach TypeScript because pnpm
  repeatedly hit npm registry fetch failures (`ECONNRESET`) while installing
  packages. The latest retry was interrupted during `pnpm install` after pnpm
  began one-minute registry retry waits. Sprint 60 owns the retry plus browser
  QA for Sprint 58 Evidence, retrieval, guide, research memo, and
  source-discovery provenance disclosures.
- [ ] Live Tavily and live multimodal provider QA were not exercised in local
  deterministic verification; the extraction eval reports these as explicit
  unavailable warnings unless credentials/provider mode/egress are configured.
- [ ] Sprint 60 owns the explicit carry-forward decisions for maintained HTML
  parser dependency versus deterministic fallback, true page/screenshot artifact
  storage, screenshot-region OCR/table provenance, Project Inspect trust-summary
  browser QA, and live-provider credential smoke tests.

## V1 Sprint 59 Branch Progress

Sprint 59 is implemented on `codex/v1-sprints-51-60`:

- Added `docs/BACKEND_FEATURE_PACKAGE_MAP.md` with target feature packages,
  owners, entrypoints, DTO/schema boundaries, model ownership, characterization
  tests, dependency rules, and migration sequence.
- Added `scripts/check_feature_boundaries.py`, a static import-boundary check
  that prevents `app.features.*` modules from importing compatibility services
  or routers.
- Added `app.common.metadata` and kept `app.services.common.metadata` as a
  compatibility shim.
- Created `app.features.evidence` and moved source provenance, HTML/text
  extraction helpers, and citation verification into feature-owned modules while
  preserving service compatibility shims.
- Moved shared citation de-duplication and retrieved-ID checks into
  `app.features.evidence.citation_verifier`. Opportunity brief, competitor
  analysis, and agentic research preserve private `_dedupe_citations` and
  `_citation_is_valid` aliases while artifact-specific citation audit decisions,
  AI run steps, DB writes, and citation persistence remain service-owned.
- Created `app.features.retrieval` and moved the reranker adapter into a
  feature-owned module while preserving the old service import path.
- Moved deterministic retrieval query planning, target-entity extraction,
  deduplication, and tokenization helpers into
  `app.features.retrieval.planning` while preserving `retrieval_service.py`
  private aliases for current callers.
- Removed duplicate private reranker logic from `retrieval_service.py`; the
  feature-owned reranker now owns source-quality retrieval weighting and
  created-at freshness scoring, and `retrieval_service.py` keeps private aliases
  for compatibility.
- Moved retrieval context selection, MMR ordering, dedupe signatures,
  source/domain/type/competitor caps, selected/dropped counts, token estimates,
  retrieval-quality proxies, and fallback reason aggregation into
  `app.features.retrieval.context_selection` while preserving
  `retrieval_service.py` aliases. DB retrieval execution, cache
  lookup/invalidation, citation enrichment, and route orchestration remain
  service-owned.
- Moved retrieval result fusion into `app.features.retrieval.result_shaping`.
  The feature helper dedupes duplicate subquery hits by `chunk_id`, keeps the
  highest-scoring result, adds `retrieval_match_count`, and preserves score/date
  ordering. `retrieval_service.py` keeps `_fuse_results` as a private
  compatibility alias while DB retrieval execution, cache lookup/invalidation,
  reranking, citation enrichment, and route orchestration remain service-owned.
- Moved retrieval score math into `app.features.retrieval.scoring`, including
  semantic/keyword/hybrid score weighting, keyword-overlap scoring, and
  normalized BM25-like text scoring. `retrieval_service.py` keeps wrappers for
  settings-backed combined scoring and ORM-backed candidate scoring while
  candidate loading, embedding similarity, SQL/vector execution, cache
  lookup/invalidation, result serialization, citation enrichment, and route
  orchestration remain service-owned.
- Moved retrieval diagnostic DTO shaping into
  `app.features.retrieval.diagnostics`, including base diagnostics and
  multi-query pipeline diagnostics for candidate-count aggregation, SQL/fallback
  aggregation, query plan, reranker, context, quality-report, and cache fields.
  `retrieval_service.py` preserves `_diagnostics` and `_pipeline_diagnostics`
  aliases while timing, cache lookup/write, DB query paths, result serialization,
  and route orchestration remain service-owned.
- Created `app.features.evals` and moved local latest-report/trend file readers
  into `app.features.evals.report_files` while preserving
  `eval_report_service.py` public wrappers.
- Moved OpenTelemetry-compatible local metric payload assembly, workflow/model/
  retrieval latency helpers, timeout counters, approval wait calculations,
  cache metric coercion, audit-event denial counting, and UTC normalization into
  `app.features.evals.observability_metrics` while preserving
  `eval_report_service.py` private aliases. Audit-event DB queries remain in
  `eval_report_service.py`.
- Moved MVP/research eval section constants, lightweight check/metric records,
  section coverage, retrieval diagnostic observation, reranker diagnostic
  observation, context assembly observation, and quality-report interpretation
  into `app.features.evals.gate_checks` while preserving `eval_service.py`
  private aliases. DB-backed eval orchestration and secret redaction checks
  remain service-owned.
- Moved eval report file writing, latest aliases, trend-record projection,
  Markdown rendering, HTML rendering, terminal summary rendering, display paths,
  and HTML escaping into `app.features.evals.report_writer` while preserving
  `scripts/eval_quality_gate.py` private wrappers. CLI arguments, subprocess
  gate execution, live API fetches, and LangSmith export side effects remain
  script-owned.
- Moved eval report summary shaping into `app.features.evals.report_summary`,
  including aggregate pass/warn/fail status, failed/warning IDs, token/cost
  projection, trace IDs, and cache metric projection from live observability
  snapshots. `scripts/eval_quality_gate.py` preserves private wrappers while
  subprocess gate execution, live API fetches, CLI arguments, and LangSmith
  export side effects remain script-owned.
- Moved eval gate result parsing and shaping into
  `app.features.evals.gate_results`, including JSON stdout parsing,
  JSON-command gate DTOs, plain command gate DTOs, unavailable/skipped gate
  DTOs, stdout/stderr tail projection, metrics passthrough, and rerun metadata.
  `scripts/eval_quality_gate.py` preserves `_parse_json_output`,
  `_run_json_gate`, `_run_command_gate`, and `_warning_gate` as compatibility
  aliases/wrappers while CLI arguments, subprocess execution, live API fetches,
  report writing, and LangSmith export side effects remain script-owned.
- Moved eval LangSmith export payload shaping into
  `app.features.evals.langsmith_export`, including redacted payload projection,
  export filename/path derivation, status result DTOs, and LangSmith run input
  projection. `scripts/eval_quality_gate.py` preserves `_redact` and
  `_export_langsmith` as compatibility wrappers while local JSON file writes,
  `LANGSMITH_*` environment lookup, dynamic client import, external upload, and
  best-effort exception handling remain script-owned.
- Moved shared eval metric-record construction into
  `app.features.evals.metric_records`, including optional warnings used by
  extraction-provider checks. `scripts/eval_ai_quality.py`,
  `scripts/eval_extraction_quality.py`, `scripts/eval_mcp_contract.py`, and
  `scripts/eval_research_sprints.py` preserve private `_metric` aliases while
  static repo/file checks, live API fetches, extraction fixture setup, provider
  settings, required live API/project setup, process re-exec, and report
  printing remain script-owned.
- Moved research eval case loading and dataset scoring into
  `app.features.evals.research_cases`. Dataset path resolution, raw JSON
  loading, Pydantic schema validation, required category/field constants, and
  dataset coverage metrics are feature-owned. `eval_service._research_eval_cases`
  and `scripts/eval_research_sprints.py` preserve compatibility wrappers while
  live project metric fetches, API route orchestration, CLI argument parsing,
  and report printing remain service/script-owned.
- Moved eval report failure payload shaping into
  `app.features.evals.report_failures`. Missing-report, malformed-report,
  unreadable-report, malformed-trend-record, and unreadable-trend-file payloads
  are feature-owned while `report_files.py` keeps path selection and file IO.
- Moved eval trend-write warning payload shaping into
  `app.features.evals.report_failures`. `report_writer.write_reports` keeps
  JSON/Markdown/HTML artifacts available when the append-only trend file cannot
  be written and returns a UI-safe `paths.trend_write` warning.
- Moved live-provider-unavailable warning metric shaping into
  `app.features.evals.provider_warnings`. The extraction eval script keeps
  settings/env lookup and delegates the warning messages plus metric payload to
  the feature module through a compatibility alias.
- Added typed eval/report DTO boundary validation for `S59-R7`:
  `EvalGateResultRead`, `EvalGateMetricRecord`, `EvalReportFailureRead`,
  `EvalExportResultRead`, `EvalMetricPointRead`, `EvalReportSummaryRead`,
  `EvalReportTokenCostRead`, and `EvalCacheDiagnosticRead` now validate gate
  result, metric record, UI-safe failure, LangSmith export-result,
  OpenTelemetry-compatible metric-point, aggregate summary, token/cost, and
  cache diagnostic payloads at the feature boundary. Rerun metadata and local
  metric export payload assembly are feature-owned through
  `app.features.evals.gate_results` and
  `app.features.evals.observability_metrics`; aggregate summary and live cache
  projection validation are feature-owned through
  `app.features.evals.report_summary`. Full gate execution, trend persistence
  policy, and upload side effects remain script/service-owned future cleanup.
- Created `app.features.governance_tools` and moved tool schema, JSON,
  metadata, requested-by, proposal, output, and research-sprint-scope guards
  into `app.features.governance_tools.schema_guard` while preserving
  `tool_service.py` private aliases and the public `ToolGuardViolation` symbol.
- Moved static governed tool contracts, role groups, stable registry listing,
  tool lookup, approval-request type mapping, and output summaries into
  `app.features.governance_tools.registry` while preserving `tool_service.py`
  public/private aliases. Tool execution, authorization, approval writes/lookups,
  and audit writes remain service-owned.
- Moved pure governed-tool audit/proposal payload shaping into
  `app.features.governance_tools.audit`, including requested/executed/status/
  denial audit metadata, approval summaries, and approval proposed-change
  payloads. `tool_service.py` preserves private aliases while audit
  persistence, redaction calls, authorization, approval writes/lookups, and DB
  transactions remain service-owned.
- Created `app.features.mcp` and moved pure MCP protocol constants,
  initialize negotiation, JSON-RPC tool schema serialization, client ID and
  argument extraction, JSON-RPC result/error envelopes, MCP invocation metadata,
  and tool-call read serialization into `app.features.mcp.protocol` while
  preserving `app.mcp.adapter` aliases.
- Moved pure MCP metadata payload shaping into `app.features.mcp.protocol`,
  including input payload wrapping, MCP audit metadata, and MCP audit summary
  helpers. `app.mcp.adapter._attach_mcp_metadata` still owns redaction, audit
  persistence, commit, refresh, and transport orchestration.
- Pinned MCP stdio bridge HTTP failure behavior in
  `scripts/mcp_stdio_server.py`: the bridge preserves the JSON-RPC request ID,
  forwards `--dev-role`, skips blank stdin lines, and returns a structured
  `-32000` JSON-RPC error when HTTP forwarding fails. Live stdio read/proposal
  smoke remains Sprint 60 environment QA.
- Pinned MCP proposal approval parity across direct MCP HTTP calls, JSON-RPC
  calls, HTTP tool-invocation reads, approval-list reads, approval rejection, and
  denial audit metadata. `tool_service.py` now redacts persisted
  `ToolInvocation.output_summary` text for governed tool/proposal outputs so
  MCP-originated proposal summaries do not leak raw emails or secrets through
  the tool invocation surface.
- Created `app.features.validation` and moved validation mission step/asset
  builders plus validation plan and experiment markdown rendering into
  `app.features.validation.plan_rendering` while preserving
  `validation_service.py` private aliases.
- Moved validation result interpretation fallback heuristics, confidence delta
  defaults, quote extraction, objection extraction, current-workaround fallback,
  and assumption-status mapping into
  `app.features.validation.result_interpretation` while preserving
  `validation_service.py` private aliases. Provider-backed interpretation,
  approval persistence, memory writes, DB access, and route orchestration remain
  service-owned.
- Moved validation assumption-extraction and validation-plan prompt construction
  plus deterministic fallback draft shaping into
  `app.features.validation.generation` while preserving
  `validation_service.py` private wrappers. Provider calls, structured-output
  repair, AI run accounting, approval persistence, DB writes,
  artifact/mission creation, and route orchestration remain service-owned.
- Created `app.features.decisions` and moved deterministic decision
  recommendation shaping, context/untrusted-input serialization,
  supporting/missing-evidence/risk derivation, suggested decision record
  shaping, action cards, labels, markdown, and link dedupe into
  `app.features.decisions.recommendation` while preserving
  `validation_service.py` private aliases.
- Created `app.features.research` and moved research memo markdown rendering
  plus selected-evidence bundle serialization into
  `app.features.research.memo_rendering` while preserving
  `agentic_research_service.py` private aliases/wrappers.
- Moved source-discovery candidate shaping, external-search result normalization
  into candidate specs, deterministic fallback candidate specs, source
  type/risk inference, URL cleanup/deduplication, discovery snapshot text, and
  evidence-ingestion metadata into `app.features.research.source_discovery`
  while preserving `source_discovery_service.py` private aliases.
- Created `app.features.guide` and moved Ask Thesys retrieval event
  serialization, answer delta chunking, final stream metadata shaping, and
  partial JSON answer parsing into `app.features.guide.events`, plus citation
  drilldown shaping into `app.features.guide.citations` and deterministic
  intent/action routing into `app.features.guide.routing`, while preserving
  `guide_service.py` private aliases.
- Moved Ask Thesys action-card DTO shaping into `app.features.guide.actions`,
  including available action dedupe, next-best action copy, decision-coach
  action cards, support action cards, target modals, action types, and risk
  labels. `guide_service.py` preserves private aliases. Project-nudge
  action-card route, modal, risk, and `project_nudge` payload shaping now also
  live in `app.features.guide.actions` behind the `nudge_service.py`
  `_guide_action` alias; nudge candidate selection, persistence, dismissal, and
  serialization remain service-owned.
- Moved stage-aware Ask Thesys recommendation copy into
  `app.features.guide.recommendations`, including stage copy, suggested
  questions, fallback stage copy, after-that follow-up text, and readable list
  joining. `guide_service.py` preserves private aliases while overview loading,
  active validation/research lookups, chat/proposal/retrieval orchestration,
  provider calls, AI run writes, approvals, and route orchestration remain
  service-owned.
- Moved grounded Ask Thesys answer DTO shaping into
  `app.features.guide.grounding`, including the structured grounded-answer draft
  schema, prompt evidence-context projection, cited-source filtering, suggested
  action resolution, unsupported-claim fallback, assumption ID truncation,
  related entity projection, and retrieval diagnostic passthrough.
  `guide_service.py` preserves private aliases while retrieval execution,
  context-pack assembly, provider calls, cache lookup/write, citation detail
  enrichment, AI run writes, approvals, cancellation, and route orchestration
  remain service-owned.
- Moved Ask Thesys guide context projection and grounded prompt assembly into
  `app.features.guide.context_projection` and `app.features.guide.prompting`.
  Recent-turn bounding, overview-to-guide-context projection, risk-level
  selection, biggest-unknown selection, grounded prompt message assembly,
  trusted/untrusted context splitting, and untrusted retrieved-content wrapping
  are feature-owned. Active validation/research DB lookups, context-pack
  construction, retrieval execution, provider calls, cache lookup/write, AI run
  writes, approvals, cancellation, proposal creation, nudge candidate
  persistence, and route orchestration remain service-owned.
- Moved Ask Thesys guide eval read-model shaping into
  `app.features.guide.evals`, including stable metric keys, score/total/pass
  derivation, proposal/direct-write observed text, and direct-write failure
  shape. `eval_service.py` still owns project authorization, DB counts, eval
  route orchestration, and any future guide eval fixture loading.
- Created `app.features.context` and moved context-pack budget application,
  priority ordering, max-item and token-budget drop reasons, prompt pack
  metadata, safety rule metadata, and available citation ID projection into
  `app.features.context.packing`. `context_service.py` preserves private
  `_pack` and `_dropped` aliases while `ContextCompiler`, settings/profile
  selection, workflow-specific evidence/tool/memory item assembly, and eval
  route orchestration remain service-owned.
- Moved guide/workflow evidence result context-item conversion into
  `app.features.context.evidence_items`, including dict/object result inputs,
  900-character truncation, citation ID construction/omission, metadata
  projection, priority assignment, entity typing, and untrusted safety flags.
  `context_service.py` preserves private aliases while guide/research context
  assembly, retrieval/tool orchestration, workflow metadata, and route/eval
  orchestration remain service-owned.
- Created `app.features.memory` and moved memory context-pack item
  serialization, selected/excluded/conflict list normalization, memory-policy
  metadata, and local token estimates into `app.features.memory.context_pack`
  while preserving `context_service.py` private aliases.
- Moved compacted-memory proposal summary/content/provenance shaping into
  `app.features.memory.compaction`, including default/custom titles, summary
  caps, empty-summary handling, source-memory IDs/titles, source-entity refs,
  and approval-required provenance. `memory_service.py` preserves a private
  alias while auth, source loading, `upsert_memory_item`, commit/refresh,
  empty-source HTTP errors, and route orchestration remain service-owned.
- Moved memory selection/conflict policy helpers into
  `app.features.memory.selection_policy`, including `MemorySelection`,
  exclusion reasons, excluded-memory rows, conflict-key normalization, text
  normalization, and feature-level conflict-membership checks. `memory_service.py`
  preserves aliases/wrappers and keeps the existing HTTP 409 behavior for
  conflict-membership mismatches while DB reads/writes, approvals, compaction,
  conflict-resolution orchestration, and Inspect routes remain service-owned.
- Moved memory Inspect serialization and explanation payload helpers into
  `app.features.memory.inspection`, including `serialize_memory_item`, selected/
  excluded/proposed/conflict Inspect payload assembly, and provenance-backed
  explanation shaping. `memory_service.py` preserves the public
  `serialize_memory_item` alias while DB lookup, workflow memory selection,
  proposed-memory queries, approvals, compaction, conflict resolution, and route
  orchestration remain service-owned.
- Added `app.ai.fallback_completion` and routed repeated service-private
  `_fallback_completion` wrappers through it for intake, opportunity brief,
  competitor analysis/discovery, research planning, agentic research, source
  discovery, and validation workflows. Workflow-specific fallback names,
  deterministic-stub provider naming, token/cost accounting, error truncation,
  and route behavior remain compatible.
- Exposed `app.ai.structured_output.schema_instruction_message` as the shared
  JSON-schema system prompt builder for structured outputs. The normal
  structured-output gateway and Ask Thesys provider streaming now use the same
  prompt text, with private aliases preserving existing service call sites.
- Added `test_feature_package_boundaries.py` to protect compatibility shims,
  feature-owned extraction behavior, common metadata behavior, and reranker
  exports.
- Added `test_contract_shapes.py` to pin evidence response serialization and
  artifact/version structured-content shapes before larger route/service
  movement.
- Extended `test_tool_boundary.py` so every read tool is executed through the
  governed service boundary and checked against its declared output schema keys.
- Expanded Sprint 59 characterization coverage for context profile metadata,
  token budgets, dropped-context reasons, untrusted input fallback, tool-output
  context items, MCP schema parity, JSON-RPC invalid-param/no-invocation
  behavior, client ID aliases, redacted MCP proposal payloads, malformed eval
  reports, eval cache metric precedence, structured-output stub/repair behavior,
  and validation rejection/context metadata.
- Updated `scripts/eval_ai_quality.py` and `scripts/eval_extraction_quality.py`
  to point at the feature-owned modules instead of private service paths.
- Updated README navigation with the feature-package map and current moved AI
  feature modules.
- Expanded `docs/BACKEND_FEATURE_PACKAGE_MAP.md` with an implemented
  characterization matrix, DTO boundary ledger, shim/migration ledger, and
  function-level next-pickup slices for retrieval context selection, memory
  selection/conflict policy, validation interpretation fallback, governed tool
  registry contracts, and eval gate diagnostics.
- Added an S59-R2 evidence extraction boundary slice:
  `app.features.evidence.extraction` now owns direct URL response metadata,
  file identity metadata, image upload metadata, text upload metadata, PDF
  parser metadata, and OCR fallback metadata. `evidence_service.py` preserves
  private aliases while URL fetch validation/HTTP orchestration, upload
  validation/object storage, PDF parsing, OCR/multimodal provider calls, chunk
  persistence, embedding writes, security audit writes, DB transactions, and
  route orchestration remain service-owned until typed ingestion/extraction DTOs
  exist.
- Added an S59-R4 research graph-state boundary slice:
  `app.features.research.graph_state` now owns JSON-safe graph step output
  serialization through `_to_jsonable` and `_json_safe` compatibility aliases in
  `agentic_research_service.py`. LangGraph node execution, AI step
  persistence, tracing, error handling, provider calls, tool execution, DB
  writes, approvals, artifact persistence, and Temporal boundaries remain
  service-owned until typed graph-state/read-model DTOs exist.
- Added an S59-R4 research strategy boundary slice:
  `app.features.research.strategy` now owns deterministic subquestion planning,
  bounded tool-call strategy, lookup-tool mapping, lookup payload projection,
  evidence-gap detection, and research text/list normalization behind
  compatibility aliases/wrappers in `agentic_research_service.py`. Tool
  execution, retrieval execution, LangGraph transitions, provider calls, AI
  step persistence, approvals, DB writes, artifact persistence, and Temporal
  boundaries remain service-owned.
- Added an S59-R4 research memo prompt boundary slice:
  `app.features.research.memo_prompting` now owns final research memo prompt
  assembly, including trusted/untrusted context splitting, compact payload
  serialization, untrusted retrieved-content wrapping, and synthesis safety
  instructions behind the `_memo_messages` compatibility alias in
  `agentic_research_service.py`. Context-pack construction, provider calls,
  structured-output parsing, AI run/step persistence, tracing, approvals,
  artifact persistence, DB writes, and Temporal boundaries remain service-owned.
- Added an S59-R4 research citation-audit boundary slice:
  `app.features.research.citation_audit` now owns memo citation audit shaping,
  including claim support downgrades, unsupported-claim summary updates,
  finding-level citation filtering, citation enrichment, and final citation
  de-duplication behind the `_audit_citations` compatibility alias in
  `agentic_research_service.py`. Citation persistence, claim writes, artifact
  metadata writes, AI step persistence, approvals, DB transactions, and Temporal
  boundaries remain service-owned.
- Added an S59-R4 research planning boundary slice:
  `app.features.research.planning` now owns research sprint planning prompt
  assembly and deterministic fallback `ResearchPlanDraft` shaping behind
  `_planning_messages` and `_fallback_research_plan` compatibility aliases in
  `research_sprint_service.py`. LangGraph planning nodes, provider calls,
  structured-output parsing, AI run/step persistence, proposal creation, plan
  and sprint persistence, approvals, Temporal signaling, DB transactions, and
  route orchestration remain service-owned.
- Added an S59-R4 source-discovery prompt boundary slice:
  `app.features.research.source_discovery` now owns source-discovery prompt
  payload assembly in addition to candidate specs, external-search result
  normalization, deterministic fallback candidate specs, URL cleanup,
  source-type/risk inference, snapshot text, and evidence metadata behind
  compatibility aliases in `source_discovery_service.py`. LLM
  structured-output calls, external-search provider execution, DB writes,
  sprint status changes, evidence ingestion orchestration, and route
  orchestration remain service-owned.
- Added an S59-R4 research memo proposal boundary slice:
  `app.features.research.proposals` now owns memory-update, validation-plan,
  and decision proposal payload/input JSON shaping for research memo review
  behind the `_research_memo_proposal_payloads` compatibility alias in
  `agentic_research_service.py`. Tool proposal creation, approval rows, audit
  events, artifact structured-content updates, route orchestration, DB
  transactions, and Temporal boundaries remain service-owned.
- Patched `SPRINT_51_60_TODO.md` and `IMPLEMENTATION_BRIEF.md` so Sprint 59 and
  Sprint 60 use pickup-ready work packages with exact target modules, functions,
  commands, and closeout artifacts instead of broad cleanup titles.
- Added the explicit remaining pickup queues:
  - Sprint 59 now has `S59-P1` through `S59-P9` for evidence/retrieval,
    validation/decisions, research, guide/streaming, governed tools/MCP,
    eval/reporting, context/memory, shared duplication cleanup, and final
    refactor closeout. Each item names the owning `G49-*` gaps, the
    implementation boundary, required docs/status updates, and verification.
  - Sprint 60 now has `S60-P1` through `S60-P10` for the final carried-gap
    audit, context docs/QA, memory docs/QA, MCP docs/smoke, retrieval/citation
    docs, Ask Thesys streaming QA, eval/observability docs, source-intelligence
    dispositions, security/deployment posture, and post-refactor navigation/code
    docs. Each item maps directly back to `G41-*` through `G50-*`.

Sprint 59 verification so far:

- [x] `python3 scripts/check_feature_boundaries.py` passed.
- [x] `cd apps/api && .venv/bin/ruff check ...` on new common/feature modules,
  compatibility shims, feature-boundary tests, and touched eval scripts passed.
- [x] `cd apps/api && .venv/bin/python -m compileall ...` on new common/feature
  modules, compatibility shims, feature-boundary tests, and touched eval scripts
  passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_common_services.py app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py -q --maxfail=1` (`25 passed`).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_contract_shapes.py app/tests/test_evidence.py app/tests/test_project_overview.py -q --maxfail=1` (`18 passed`).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py -q --maxfail=1` (`11 passed`).
- [x] `cd apps/api && .venv/bin/pytest -q` (`183 passed`).
- [x] `python3 scripts/eval_ai_quality.py --json` (`10/10` passed).
- [x] `python3 scripts/eval_retrieval_quality.py` (`7/7` passed).
- [x] `python3 scripts/eval_extraction_quality.py --json` (`7/7` passed with
  explicit live-provider-unavailable warnings).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_eval_reports.py app/tests/test_mcp_adapter.py app/tests/test_ai.py app/tests/test_validation.py -q --maxfail=1` (`41 passed`).
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals app/services/eval_report_service.py app/tests/test_context_compiler.py app/tests/test_eval_reports.py app/tests/test_mcp_adapter.py app/tests/test_ai.py app/tests/test_validation.py` passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the evals
  feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_eval_reports.py -q --maxfail=1`
  (`18 passed`) after the eval observability metrics feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals app/services/eval_report_service.py app/tests/test_feature_package_boundaries.py`
  passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_demo_eval_workflows.py::test_seed_demo_project_runs_mvp_eval_and_exposes_workflow_events app/tests/test_research_history_eval.py::test_v1_research_eval_passes_for_completed_research_sprint app/tests/test_feature_package_boundaries.py -q`
  (`19 passed`) after the eval gate-check feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/services/eval_service.py app/features/evals/gate_checks.py app/tests/test_feature_package_boundaries.py`
  passed after the eval gate-check feature slice.
- [x] `cd apps/api && .venv/bin/python -m py_compile app/services/eval_service.py app/features/evals/gate_checks.py app/tests/test_feature_package_boundaries.py`
  passed after the eval gate-check feature slice.
- [x] `apps/api/.venv/bin/ruff check scripts/eval_quality_gate.py` passed after
  updating the cache-quality source check for the feature-owned metric module.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-metrics LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`).
- [x] `cd apps/api && .venv/bin/pytest -q` (`201 passed` after the eval
  observability metrics feature slice).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_evidence.py::test_source_quality_weight_affects_deterministic_rerank app/tests/test_retrieval_quality_eval.py -q --maxfail=1` (`8 passed`).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_agentic_research.py app/tests/test_research_history_eval.py app/tests/test_retrieval_quality_eval.py -q --maxfail=1` (`21 passed`).
- [x] `cd apps/api && .venv/bin/ruff check app/features/retrieval/planning.py app/features/retrieval/reranker.py app/services/retrieval_service.py` passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py::test_context_assembly_prioritizes_source_diversity app/tests/test_retrieval_quality_eval.py app/tests/test_feature_package_boundaries.py -q`
  (`18 passed`) after the retrieval context-selection feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_result_fusion_dedupes_chunks_and_preserves_match_count -q`
  (`1 passed`) before moving retrieval result fusion.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_result_fusion_dedupes_chunks_and_preserves_match_count app/tests/test_evidence.py::test_broad_evidence_retrieval_plans_reranks_and_assembles_context -q`
  (`2 passed`) after moving retrieval result fusion.
- [x] `cd apps/api && .venv/bin/ruff check app/features/retrieval/result_shaping.py app/services/retrieval_service.py app/tests/test_feature_package_boundaries.py`
  passed after the retrieval result-fusion feature slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/retrieval/result_shaping.py app/services/retrieval_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the retrieval result-fusion feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_scoring_helpers_preserve_hybrid_keyword_and_bm25_behavior -q`
  (`1 passed`) before moving retrieval score math.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_scoring_helpers_preserve_hybrid_keyword_and_bm25_behavior app/tests/test_evidence.py::test_note_ingestion_chunks_embeds_and_retrieves -q`
  (`2 passed`) after moving retrieval score math.
- [x] `cd apps/api && .venv/bin/ruff check app/features/retrieval/scoring.py app/services/retrieval_service.py app/tests/test_feature_package_boundaries.py`
  passed after the retrieval scoring feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_scoring_helpers_preserve_hybrid_keyword_and_bm25_behavior app/tests/test_feature_package_boundaries.py::test_retrieval_result_fusion_dedupes_chunks_and_preserves_match_count app/tests/test_evidence.py::test_note_ingestion_chunks_embeds_and_retrieves app/tests/test_evidence.py::test_broad_evidence_retrieval_plans_reranks_and_assembles_context app/tests/test_retrieval_quality_eval.py -q`
  (`5 passed`) after the retrieval scoring feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_citation_dedupe_helpers_are_feature_owned_and_service_compatible app/tests/test_citation_verifier.py app/tests/test_opportunity_brief.py app/tests/test_competitors.py app/tests/test_agentic_research.py -q`
  (`19 passed`) after moving shared citation de-duplication and retrieved-ID
  checks into `app.features.evidence.citation_verifier`.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evidence/citation_verifier.py app/services/opportunity_brief_service.py app/services/competitor_service.py app/services/agentic_research_service.py app/tests/test_feature_package_boundaries.py`
  passed after the shared citation helper feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_eval_gate_result_helpers_are_feature_owned app/tests/test_eval_reports.py::test_eval_quality_gate_script_writes_reports -q`
  (`2 passed`) after moving eval gate result shaping.
- [x] `apps/api/.venv/bin/ruff check apps/api/app/features/evals/gate_results.py apps/api/app/tests/test_feature_package_boundaries.py apps/api/app/tests/test_eval_reports.py scripts/eval_quality_gate.py`
  passed after the eval gate result slice.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-gate-results LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after the eval gate result slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`231 passed`) after the shared
  citation helper and eval gate result slices.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/retrieval app/services/retrieval_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the retrieval scoring feature slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the retrieval
  scoring feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/retrieval/context_selection.py app/services/retrieval_service.py app/tests/test_feature_package_boundaries.py app/features/validation/result_interpretation.py app/services/validation_service.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/retrieval/context_selection.py app/services/retrieval_service.py app/tests/test_feature_package_boundaries.py app/features/validation/result_interpretation.py app/services/validation_service.py -q`
  passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_tool_boundary.py app/tests/test_security_governance.py app/tests/test_mcp_adapter.py -q --maxfail=1` (`34 passed`).
- [x] `cd apps/api && .venv/bin/ruff check app/features/governance_tools app/services/tool_service.py` passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_tool_boundary.py::test_tool_registry_exposes_mcp_style_contracts app/tests/test_tool_boundary.py::test_read_tools_return_declared_output_schema_keys app/tests/test_mcp_adapter.py::test_mcp_jsonrpc_preserves_ids_and_tool_schema_parity app/tests/test_feature_package_boundaries.py -q`
  (`21 passed`) after the governed tool registry feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/governance_tools app/services/tool_service.py app/tests/test_feature_package_boundaries.py`
  passed after the governed tool registry feature slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/governance_tools app/services/tool_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the governed tool registry feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_mcp_adapter.py -q --maxfail=1`
  (`24 passed`) after the MCP protocol feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/mcp app/mcp/adapter.py app/tests/test_feature_package_boundaries.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/mcp app/mcp/adapter.py app/tests/test_feature_package_boundaries.py -q`
  passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the MCP
  protocol feature slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`202 passed` after the MCP
  protocol feature slice).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_project_overview.py app/tests/test_guide.py -q --maxfail=1` (`30 passed`).
- [x] `cd apps/api && .venv/bin/ruff check app/features/validation app/services/validation_service.py` passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_validation.py -q --maxfail=1` (`21 passed`).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py::test_interpret_validation_notes_creates_pending_memory_update app/tests/test_validation.py::test_validation_interpretation_rejection_does_not_write_memory_or_confidence app/tests/test_validation.py::test_decision_coach_uses_interpreted_results_and_prefills_record app/tests/test_feature_package_boundaries.py -q`
  (`19 passed`) after the validation result-interpretation feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/decisions app/services/validation_service.py app/tests/test_feature_package_boundaries.py` passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/decisions app/services/validation_service.py app/tests/test_feature_package_boundaries.py -q` passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the decisions
  feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_agentic_research.py app/tests/test_research_history_eval.py -q --maxfail=1` (`6 passed`).
- [x] `cd apps/api && .venv/bin/ruff check app/features/research app/services/agentic_research_service.py` passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_research_discovery.py -q --maxfail=1`
  (`23 passed`) after the source-discovery feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/research app/services/source_discovery_service.py app/tests/test_feature_package_boundaries.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/research app/services/source_discovery_service.py app/tests/test_feature_package_boundaries.py -q`
  passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the
  source-discovery feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_guide.py -q --maxfail=1` (`26 passed`).
- [x] `cd apps/api && .venv/bin/ruff check app/features/guide app/services/guide_service.py app/tests/test_feature_package_boundaries.py` passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/guide app/services/guide_service.py app/tests/test_feature_package_boundaries.py -q` passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the guide
  events feature slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`198 passed` after the guide and
  decision recommendation feature slices).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_context_compiler.py app/tests/test_memory_service.py -q --maxfail=1`
  (`22 passed`) after the memory context-pack feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/memory app/services/context_service.py app/tests/test_feature_package_boundaries.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/memory app/services/context_service.py app/tests/test_feature_package_boundaries.py -q`
  passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the memory
  context-pack feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py::test_memory_context_selection_explains_exclusions_and_conflicts app/tests/test_memory_service.py::test_memory_proposals_and_inspect_endpoint app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  (`26 passed`) after the memory selection-policy feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/memory/selection_policy.py app/services/memory_service.py app/tests/test_feature_package_boundaries.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/memory/selection_policy.py app/services/memory_service.py app/tests/test_feature_package_boundaries.py -q`
  passed.
- [x] `cd apps/api && .venv/bin/pytest -q` (`207 passed`) after the memory
  selection-policy feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_ai.py::test_fallback_completion_builds_local_completion_metadata app/tests/test_ai.py::test_fallback_completion_preserves_stub_provider_prefix app/tests/test_validation.py::test_assumption_extraction_can_force_local_fallback_with_always_policy app/tests/test_validation.py::test_assumption_extraction_uses_emergency_fallback_after_generation_failure app/tests/test_validation.py::test_validation_plan_can_force_local_fallback_with_always_policy app/tests/test_validation.py::test_validation_plan_uses_emergency_fallback_after_generation_failure app/tests/test_intake.py::test_structured_intake_answer_can_force_local_fallback_with_always_policy app/tests/test_intake.py::test_structured_intake_uses_emergency_fallback_after_generation_failure app/tests/test_opportunity_brief.py::test_generate_opportunity_brief_can_force_local_fallback_with_always_policy app/tests/test_opportunity_brief.py::test_generate_opportunity_brief_uses_emergency_fallback_after_generation_failure app/tests/test_competitors.py::test_competitor_analysis_can_force_local_fallback_with_always_policy app/tests/test_competitors.py::test_competitor_analysis_uses_emergency_fallback_after_generation_failure -q`
  (`12 passed`) after centralizing deterministic fallback completion metadata.
- [x] `cd apps/api && .venv/bin/ruff check app/ai/fallback_completion.py app/services/validation_service.py app/services/intake_service.py app/services/opportunity_brief_service.py app/services/competitor_service.py app/services/research_sprint_service.py app/services/agentic_research_service.py app/services/source_discovery_service.py app/services/competitor_discovery_service.py app/tests/test_ai.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/ai/fallback_completion.py app/services/validation_service.py app/services/intake_service.py app/services/opportunity_brief_service.py app/services/competitor_service.py app/services/research_sprint_service.py app/services/agentic_research_service.py app/services/source_discovery_service.py app/services/competitor_discovery_service.py app/tests/test_ai.py -q`
  passed.
- [x] `cd apps/api && .venv/bin/pytest -q` (`209 passed`) after centralizing
  deterministic fallback completion metadata.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py::test_assumption_extraction_can_force_local_fallback_with_always_policy app/tests/test_validation.py::test_assumption_extraction_uses_emergency_fallback_after_generation_failure app/tests/test_validation.py::test_generate_validation_plan_and_log_result_updates_confidence app/tests/test_validation.py::test_validation_plan_can_force_local_fallback_with_always_policy app/tests/test_validation.py::test_validation_plan_uses_emergency_fallback_after_generation_failure app/tests/test_feature_package_boundaries.py -q`
  (`25 passed`) after moving validation generation prompt/fallback helpers.
- [x] `cd apps/api && .venv/bin/ruff check app/features/validation/generation.py app/services/validation_service.py app/tests/test_feature_package_boundaries.py`
  passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the validation
  generation feature slice.
- [x] `git diff --check` passed after the validation generation feature slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`210 passed`) after the validation
  generation feature slice and sprint handoff patches.
- [x] `rg -n "<{7}|={7}|>{7}" .` returned no conflict markers after the
  validation generation feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_writer_creates_reports_latest_aliases_and_trend app/tests/test_eval_reports.py::test_eval_quality_gate_script_writes_reports -q`
  (`2 passed`) after moving eval report writer/rendering helpers.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`27 passed`) after adding direct feature-boundary coverage for eval report
  writer helpers and stdout/file `paths` compatibility.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/report_writer.py app/tests/test_eval_reports.py ../../scripts/eval_quality_gate.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/report_writer.py app/tests/test_eval_reports.py ../../scripts/eval_quality_gate.py -q`
  passed.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-writer LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) and generated `latest.md`,
  `latest.html`, and `latest.json` without changing the existing file/stdout
  `paths` behavior.
- [x] `cd apps/api && .venv/bin/pytest -q` (`212 passed`) after the eval report
  writer feature slice.
- [x] `git diff --check` passed and `rg -n "<{7}|={7}|>{7}" .` returned no
  conflict markers after the eval report writer feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_memory_inspection_helpers_are_feature_owned_and_service_compatible app/tests/test_memory_service.py::test_memory_explanation_and_duplicate_merge app/tests/test_memory_service.py::test_memory_proposals_and_inspect_endpoint -q`
  (`3 passed`) after moving memory Inspect serialization helpers.
- [x] `cd apps/api && .venv/bin/ruff check app/features/memory/inspection.py app/services/memory_service.py app/tests/test_feature_package_boundaries.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/memory/inspection.py app/services/memory_service.py app/tests/test_feature_package_boundaries.py -q`
  passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  (`33 passed`) after the memory Inspect feature slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the memory
  Inspect feature slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`213 passed`) after the memory
  Inspect feature slice.
- [x] `git diff --check` passed and `rg -n "<{7}|={7}|>{7}" .` returned no
  conflict markers after the memory Inspect feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_summary_shapes_status_failures_and_live_cache app/tests/test_feature_package_boundaries.py::test_eval_report_summary_helpers_are_feature_owned app/tests/test_eval_reports.py::test_eval_quality_gate_script_writes_reports -q`
  (`3 passed`) after moving eval report summary shaping helpers.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/report_summary.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_quality_gate.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/report_summary.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_quality_gate.py -q`
  passed.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`30 passed`) after the eval report summary feature slice.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-summary LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after the eval report summary
  feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_langsmith_export_helpers_redact_payload_and_shape_status app/tests/test_eval_reports.py::test_eval_quality_gate_script_exports_langsmith_payload_without_upload app/tests/test_feature_package_boundaries.py::test_eval_langsmith_export_helpers_are_feature_owned_and_script_compatible -q`
  (`3 passed`) after moving eval LangSmith export payload/result shaping.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_gate_result_helpers_parse_and_shape_command_results app/tests/test_feature_package_boundaries.py::test_eval_gate_result_helpers_are_feature_owned -q`
  (`2 passed`) after moving eval gate JSON parsing and command result shaping.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_metric_record_helper_shapes_optional_warnings app/tests/test_feature_package_boundaries.py::test_eval_metric_record_helper_is_feature_owned_and_script_compatible -q`
  (`2 passed`) after first moving shared eval metric-record construction, then
  (`2 passed`) after extending script alias coverage to the MCP contract and
  research sprint eval scripts.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_research_history_eval.py app/tests/test_demo_eval_workflows.py app/tests/test_feature_package_boundaries.py -q`
  (`53 passed`) after the eval LangSmith export feature slice and (`54 passed`)
  after adding eval gate command-result parsing/shaping coverage.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-langsmith LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security --export-langsmith`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) and wrote a redacted local
  LangSmith export payload without upload.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the eval
  LangSmith export feature slice.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-gate-results LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after moving eval gate command-result
  parsing/shaping.
- [x] `python3 scripts/eval_ai_quality.py --json` (`10/10` passed) after moving
  shared eval metric-record construction.
- [x] `python3 scripts/eval_extraction_quality.py --json` (`7/7` passed with
  live-provider unavailable warnings) after moving shared eval metric-record
  construction.
- [x] `python3 scripts/eval_research_sprints.py --json` (`7/7` passed) after
  extending shared eval metric-record aliases to the research sprint eval
  script.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_research_eval_case_helpers_are_feature_owned_and_script_compatible -q`
  (`1 passed`) after moving research eval case loading/scoring into
  `app.features.evals.research_cases`.
- [x] `python3 scripts/eval_research_sprints.py --json` (`7/7` passed) after
  moving research eval case loading/scoring into
  `app.features.evals.research_cases`.
- [x] `cd apps/api && .venv/bin/python - <<'PY' ... eval_service._research_eval_cases() ... PY`
  loaded 10 validated research eval cases after moving service case loading to
  `app.features.evals.research_cases`.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`48 passed`) after moving research eval case loading/scoring into
  `app.features.evals.research_cases`.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-research-cases LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after moving research eval case
  loading/scoring.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/research_cases.py app/services/eval_service.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_research_sprints.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/research_cases.py app/services/eval_service.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_research_sprints.py -q`
  passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after moving research
  eval case loading/scoring.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_endpoints_surface_missing_and_malformed_reports app/tests/test_eval_reports.py::test_eval_report_failure_helpers_shape_safe_warning_payloads app/tests/test_feature_package_boundaries.py::test_eval_report_failure_helpers_are_feature_owned -q`
  (`3 passed`) after moving missing/malformed/unreadable report and trend-read
  failure payload shaping into `app.features.evals.report_failures`.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/report_failures.py app/features/evals/report_files.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py`
  passed after the eval report failure-payload slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/report_failures.py app/features/evals/report_files.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  passed after the eval report failure-payload slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`50 passed`) after the eval report failure-payload docs/status update.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-report-failures LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after the eval report
  failure-payload docs/status update.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_failure_helpers_shape_safe_warning_payloads app/tests/test_eval_reports.py::test_eval_report_writer_creates_reports_latest_aliases_and_trend app/tests/test_eval_reports.py::test_eval_report_writer_surfaces_trend_write_failure app/tests/test_feature_package_boundaries.py::test_eval_report_failure_helpers_are_feature_owned app/tests/test_feature_package_boundaries.py::test_eval_report_writer_helpers_are_feature_owned -q`
  (`5 passed`) after adding feature-owned trend-write warning payload shaping.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`51 passed`) after adding the trend-write warning payload slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/report_failures.py app/features/evals/report_writer.py app/features/evals/report_files.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_quality_gate.py`
  passed after the trend-write warning payload slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/report_failures.py app/features/evals/report_writer.py app/features/evals/report_files.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_quality_gate.py -q`
  passed after the trend-write warning payload slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the
  trend-write warning payload slice.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-trend-write LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after the trend-write warning
  payload slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_provider_warning_helper_shapes_live_provider_metric app/tests/test_feature_package_boundaries.py::test_eval_metric_record_helper_is_feature_owned_and_script_compatible -q`
  (`2 passed`) after moving live-provider-unavailable warning metric shaping
  into `app.features.evals.provider_warnings`.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`52 passed`) after the provider warning helper slice.
- [x] `python3 scripts/eval_extraction_quality.py --json` (`7/7` passed with
  live-provider unavailable warnings) after the provider warning helper slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/provider_warnings.py app/features/evals/report_failures.py app/features/evals/report_writer.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_extraction_quality.py`
  passed after the provider warning helper slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/provider_warnings.py app/features/evals/report_failures.py app/features/evals/report_writer.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_extraction_quality.py -q`
  passed after the provider warning helper slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the provider
  warning helper slice.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-provider-warnings LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after the provider warning helper
  slice.
- [x] `python3 scripts/eval_mcp_contract.py --help` passed after extending the
  shared eval metric-record alias to the MCP contract script. Full MCP contract
  execution still requires a running API and a real `--project-id`.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-metric-records LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after the shared metric-record
  slice.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-metric-records-all LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after extending metric-record
  aliases to the MCP contract and research sprint eval scripts.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`47 passed`) after moving shared eval metric-record construction.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`47 passed`) after extending metric-record aliases to all four local eval
  scripts.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/metric_records.py app/features/evals/gate_results.py app/features/evals/langsmith_export.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_ai_quality.py ../../scripts/eval_extraction_quality.py ../../scripts/eval_quality_gate.py`
  passed.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/metric_records.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_ai_quality.py ../../scripts/eval_extraction_quality.py ../../scripts/eval_mcp_contract.py ../../scripts/eval_research_sprints.py`
  passed after extending metric-record aliases to the MCP contract and research
  sprint eval scripts.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/metric_records.py app/features/evals/gate_results.py app/features/evals/langsmith_export.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_ai_quality.py ../../scripts/eval_extraction_quality.py ../../scripts/eval_quality_gate.py -q`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/metric_records.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_ai_quality.py ../../scripts/eval_extraction_quality.py ../../scripts/eval_mcp_contract.py ../../scripts/eval_research_sprints.py -q`
  passed after extending metric-record aliases to the MCP contract and research
  sprint eval scripts.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the shared
  metric-record slice.
- [x] `git diff --check -- README.md IMPLEMENTATION_STATUS.md IMPLEMENTATION_BRIEF.md SPRINT_51_60_TODO.md docs/BACKEND_FEATURE_PACKAGE_MAP.md apps/api/app/features/evals/metric_records.py apps/api/app/features/evals/gate_results.py apps/api/app/features/evals/langsmith_export.py apps/api/app/tests/test_eval_reports.py apps/api/app/tests/test_feature_package_boundaries.py scripts/eval_ai_quality.py scripts/eval_extraction_quality.py scripts/eval_quality_gate.py`
  passed.
- [x] `rg -n "<{7}|={7}|>{7}" README.md IMPLEMENTATION_STATUS.md IMPLEMENTATION_BRIEF.md SPRINT_51_60_TODO.md docs/BACKEND_FEATURE_PACKAGE_MAP.md apps/api/app/features/evals/metric_records.py apps/api/app/features/evals/gate_results.py apps/api/app/features/evals/langsmith_export.py apps/api/app/tests/test_eval_reports.py apps/api/app/tests/test_feature_package_boundaries.py scripts/eval_ai_quality.py scripts/eval_extraction_quality.py scripts/eval_quality_gate.py`
  returned no conflict markers.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/gate_results.py app/features/evals/langsmith_export.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_quality_gate.py`
  passed after the eval gate result and LangSmith export slices.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/gate_results.py app/features/evals/langsmith_export.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_quality_gate.py -q`
  passed.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the eval gate
  result and LangSmith export slices.
- [x] `git diff --check -- README.md IMPLEMENTATION_STATUS.md IMPLEMENTATION_BRIEF.md SPRINT_51_60_TODO.md docs/BACKEND_FEATURE_PACKAGE_MAP.md apps/api/app/features/evals/gate_results.py apps/api/app/features/evals/langsmith_export.py apps/api/app/tests/test_eval_reports.py apps/api/app/tests/test_feature_package_boundaries.py scripts/eval_quality_gate.py`
  passed.
- [x] `rg -n "<{7}|={7}|>{7}" README.md IMPLEMENTATION_STATUS.md IMPLEMENTATION_BRIEF.md SPRINT_51_60_TODO.md docs/BACKEND_FEATURE_PACKAGE_MAP.md apps/api/app/features/evals/gate_results.py apps/api/app/features/evals/langsmith_export.py apps/api/app/tests/test_eval_reports.py apps/api/app/tests/test_feature_package_boundaries.py scripts/eval_quality_gate.py`
  returned no conflict markers.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/langsmith_export.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_quality_gate.py`
  passed.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/langsmith_export.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py ../../scripts/eval_quality_gate.py -q`
  passed.
- [x] `git diff --check -- README.md IMPLEMENTATION_STATUS.md IMPLEMENTATION_BRIEF.md SPRINT_51_60_TODO.md docs/BACKEND_FEATURE_PACKAGE_MAP.md apps/api/app/features/evals/langsmith_export.py apps/api/app/tests/test_eval_reports.py apps/api/app/tests/test_feature_package_boundaries.py scripts/eval_quality_gate.py`
  passed.
- [x] `rg -n "<{7}|={7}|>{7}" README.md IMPLEMENTATION_STATUS.md IMPLEMENTATION_BRIEF.md SPRINT_51_60_TODO.md docs/BACKEND_FEATURE_PACKAGE_MAP.md apps/api/app/features/evals/langsmith_export.py apps/api/app/tests/test_eval_reports.py apps/api/app/tests/test_feature_package_boundaries.py scripts/eval_quality_gate.py`
  returned no conflict markers.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the eval report
  summary feature slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`215 passed`) after the eval report
  summary feature slice.
- [x] `git diff --check` passed and `rg -n "<{7}|={7}|>{7}" .` returned no
  conflict markers after the eval report summary feature slice.
- [x] `cd apps/api && .venv/bin/ruff check ...` on current Sprint 59 common,
  feature, service, script, and characterization-test paths passed.
- [x] `cd apps/api && .venv/bin/python -m compileall ... -q` on current Sprint
  59 common, feature, service, script, and characterization-test paths passed.
- [x] `python3 scripts/eval_ai_quality.py --json` (`10/10` passed).
- [x] `python3 scripts/eval_retrieval_quality.py` (`7/7` passed).
- [x] `python3 scripts/eval_extraction_quality.py --json` (`7/7` passed with
  explicit live-provider-unavailable warnings).
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-current LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security` passed with warn status (`40/40`; warning gates: `mcp_contract`, `security_check`).
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_ai.py::test_schema_instruction_message_uses_shared_json_schema_prompt app/tests/test_feature_package_boundaries.py::test_guide_stream_schema_instruction_uses_shared_ai_gateway -q`
  (`2 passed`) after centralizing structured-output schema instruction
  assembly.
- [x] `cd apps/api && .venv/bin/ruff check app/ai/structured_output.py app/services/guide_service.py app/tests/test_ai.py app/tests/test_feature_package_boundaries.py`
  passed after the structured-output schema-instruction cleanup.
- [x] `cd apps/api && .venv/bin/python -m compileall app/ai/structured_output.py app/services/guide_service.py app/tests/test_ai.py app/tests/test_feature_package_boundaries.py -q`
  passed after the structured-output schema-instruction cleanup.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_ai.py app/tests/test_guide.py app/tests/test_feature_package_boundaries.py -q`
  (`54 passed`) after the structured-output schema-instruction cleanup.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the
  structured-output schema-instruction cleanup.
- [x] `cd apps/api && .venv/bin/pytest -q` (`217 passed`) after the
  structured-output schema-instruction cleanup.
- [x] `git diff --check` passed and `rg -n "<{7}|={7}|>{7}" .` returned no
  conflict markers after the structured-output schema-instruction cleanup.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_governance_tool_audit_helpers_are_feature_owned_and_service_compatible app/tests/test_security_governance.py::test_tool_denial_is_audited_and_persisted_proposals_are_redacted app/tests/test_tool_boundary.py::test_research_plan_proposal_is_audited_and_approvable -q`
  (`3 passed`) after moving governed-tool audit/proposal payload shaping.
- [x] `cd apps/api && .venv/bin/ruff check app/features/governance_tools/audit.py app/services/tool_service.py app/tests/test_feature_package_boundaries.py`
  passed after the governed-tool audit/proposal payload slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/governance_tools/audit.py app/services/tool_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the governed-tool audit/proposal payload slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py app/tests/test_security_governance.py app/tests/test_feature_package_boundaries.py -q`
  (`59 passed`) after the governed-tool audit/proposal payload slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the
  governed-tool audit/proposal payload slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`218 passed`) after the
  governed-tool audit/proposal payload slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_action_helpers_are_feature_owned_and_service_compatible app/tests/test_guide.py app/tests/test_nudges.py -q`
  (`21 passed`) after moving guide action-card DTO shaping.
- [x] `cd apps/api && .venv/bin/ruff check app/features/guide/actions.py app/services/guide_service.py app/tests/test_feature_package_boundaries.py`
  passed after the guide action-card feature slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/guide/actions.py app/services/guide_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the guide action-card feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_nudges.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  (`51 passed`) after the guide action-card feature slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the guide
  action-card feature slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`219 passed`) after the guide
  action-card feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_action_helpers_are_feature_owned_and_service_compatible app/tests/test_nudges.py app/tests/test_guide.py -q`
  (`21 passed`) after moving nudge action-card shaping behind
  `app.features.guide.actions.nudge_action`.
- [x] `cd apps/api && .venv/bin/ruff check app/features/guide/actions.py app/services/nudge_service.py app/tests/test_feature_package_boundaries.py`
  passed after the nudge action-card extraction.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/guide/actions.py app/services/nudge_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the nudge action-card extraction.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_nudges.py app/tests/test_context_compiler.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`53 passed`) after the nudge action-card extraction.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the nudge
  action-card extraction.
- [x] `git diff --check` passed after the nudge action-card extraction; conflict
  marker scan returned no matches.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_recommendation_helpers_preserve_stage_copy_and_followups -q`
  (`1 passed`) before moving guide recommendation copy.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_recommendation_helpers_are_feature_owned_and_service_compatible app/tests/test_guide.py::test_guide_context_and_recommendation_are_stage_aware app/tests/test_guide.py::test_guide_action_router_uses_specific_commands_and_aliases app/tests/test_guide.py::test_guide_chat_is_project_scoped_and_rejects_generic_questions app/tests/test_guide.py::test_guide_explains_idea_story_wedge_and_next_proof -q`
  (`5 passed`) after moving guide recommendation copy.
- [x] `cd apps/api && .venv/bin/ruff check app/features/guide/recommendations.py app/services/guide_service.py app/tests/test_feature_package_boundaries.py`
  passed after the guide recommendation feature slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/guide/recommendations.py app/services/guide_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the guide recommendation feature slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the guide
  recommendation feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py app/tests/test_guide.py app/tests/test_nudges.py -q`
  (`51 passed`) after the guide recommendation feature slice.
- [x] `cd apps/api && .venv/bin/ruff check app/features/guide app/services/guide_service.py app/tests/test_feature_package_boundaries.py`
  passed after the guide recommendation feature slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/guide app/services/guide_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the guide recommendation feature slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_eval_observability_metric_helpers_are_feature_owned_and_service_compatible app/tests/test_eval_reports.py -q`
  (`8 passed`) after moving audit-event denial counting into
  `app.features.evals.observability_metrics`.
- [x] `cd apps/api && .venv/bin/ruff check app/features/evals/observability_metrics.py app/services/eval_report_service.py app/tests/test_feature_package_boundaries.py`
  passed after the audit-event denial counting extraction.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/observability_metrics.py app/services/eval_report_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the audit-event denial counting extraction.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the
  audit-event denial counting extraction.
- [x] `git diff --check` passed after the audit-event denial counting
  extraction; conflict marker scan returned no matches.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py::test_context_pack_orders_items_by_priority_before_budgeting app/tests/test_context_compiler.py::test_context_pack_records_max_items_exceeded_after_thirty_items -q`
  (`2 passed`) before moving context packing helpers.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py::test_context_profiles_pin_policy_metadata_budget_and_drop_reasons app/tests/test_context_compiler.py::test_context_compiler_tracks_dropped_items_under_budget app/tests/test_context_compiler.py::test_context_pack_orders_items_by_priority_before_budgeting app/tests/test_context_compiler.py::test_context_pack_records_max_items_exceeded_after_thirty_items app/tests/test_feature_package_boundaries.py::test_memory_context_pack_helpers_are_feature_owned_and_service_compatible -q`
  (`5 passed`) after moving context packing helpers.
- [x] `cd apps/api && .venv/bin/ruff check app/features/context/packing.py app/services/context_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py`
  passed after the context packing extraction.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`41 passed`) after the context packing extraction.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/context/packing.py app/services/context_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  passed after the context packing extraction.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the context
  packing extraction.
- [x] `git diff --check` passed after the context packing extraction; conflict
  marker scan returned no matches.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py::test_memory_proposals_and_inspect_endpoint -q`
  (`1 passed`) before moving compacted-memory proposal shaping.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_memory_compaction_payload_helpers_are_feature_owned_and_service_compatible app/tests/test_memory_service.py::test_memory_proposals_and_inspect_endpoint -q`
  (`2 passed`) after moving compacted-memory proposal shaping.
- [x] `cd apps/api && .venv/bin/ruff check app/features/memory/compaction.py app/services/memory_service.py app/tests/test_memory_service.py app/tests/test_feature_package_boundaries.py`
  passed after the memory compaction extraction.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`42 passed`) after the memory compaction extraction.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/memory/compaction.py app/services/memory_service.py app/tests/test_memory_service.py app/tests/test_feature_package_boundaries.py -q`
  passed after the memory compaction extraction.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the memory
  compaction extraction.
- [x] `git diff --check` passed after the memory compaction extraction; conflict
  marker scan returned no matches.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py::test_context_evidence_items_preserve_citation_metadata_and_safety_flags app/tests/test_context_compiler.py::test_context_evidence_result_items_support_dict_and_object_inputs -q`
  (`2 passed`) before moving context evidence item shaping.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py::test_context_evidence_items_preserve_citation_metadata_and_safety_flags app/tests/test_context_compiler.py::test_context_evidence_result_items_support_dict_and_object_inputs app/tests/test_feature_package_boundaries.py::test_context_evidence_item_helpers_are_feature_owned_and_service_compatible -q`
  (`3 passed`) after moving context evidence item shaping.
- [x] `cd apps/api && .venv/bin/ruff check app/features/context/evidence_items.py app/services/context_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py`
  passed after the context evidence item extraction.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_guide.py::test_guide_chat_attaches_grounded_retrieval_metadata_and_trace app/tests/test_agentic_research.py::test_agentic_research_runs_multi_step_rag_and_writes_reviewable_memo app/tests/test_feature_package_boundaries.py -q`
  (`39 passed`) after the context evidence item extraction.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/context/evidence_items.py app/services/context_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q`
  passed after the context evidence item extraction.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the context
  evidence item extraction.
- [x] `git diff --check` passed after the context evidence item extraction;
  conflict marker scan returned no matches.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_mcp_protocol_helpers_are_feature_owned_and_adapter_compatible app/tests/test_mcp_adapter.py::test_mcp_jsonrpc_client_id_alias_and_redaction_are_preserved app/tests/test_mcp_adapter.py::test_mcp_read_tool_uses_existing_governance_and_audit -q`
  (`3 passed`) after moving MCP metadata payload shaping.
- [x] `cd apps/api && .venv/bin/ruff check app/features/mcp/protocol.py app/mcp/adapter.py app/tests/test_feature_package_boundaries.py`
  passed after the MCP metadata payload slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/mcp/protocol.py app/mcp/adapter.py app/tests/test_feature_package_boundaries.py -q`
  passed after the MCP metadata payload slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_security_governance.py app/tests/test_feature_package_boundaries.py -q`
  (`60 passed`) after the MCP metadata payload slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the MCP
  metadata payload slice.
- [x] `cd apps/api && .venv/bin/pytest -q` (`219 passed`) after the MCP metadata
  payload slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_helpers_validate_typed_dto_boundaries -q`
  (`1 passed`) after adding typed eval/report DTO boundary validation.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`53 passed`) after typed eval/report DTO boundary validation.
- [x] `cd apps/api && .venv/bin/ruff check app/schemas/evals.py app/features/evals/metric_records.py app/features/evals/gate_results.py app/features/evals/report_failures.py app/features/evals/langsmith_export.py app/features/evals/observability_metrics.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py`
  passed after typed eval/report DTO boundary validation.
- [x] `cd apps/api && .venv/bin/python -m compileall app/schemas/evals.py app/features/evals/metric_records.py app/features/evals/gate_results.py app/features/evals/report_failures.py app/features/evals/langsmith_export.py app/features/evals/observability_metrics.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  passed after typed eval/report DTO boundary validation.
- [x] `python3 scripts/check_feature_boundaries.py` passed after typed
  eval/report DTO boundary validation.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-typed-dtos LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-security`
  passed with warn status (`40/40`; warning gates: `mcp_contract`,
  `security_check`) after typed eval/report DTO boundary validation.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_research_history_eval.py app/tests/test_demo_eval_workflows.py app/tests/test_feature_package_boundaries.py -q`
  (`62 passed`) after typed eval/report DTO boundary validation.
- [x] `python3 scripts/eval_mcp_contract.py --help` passed after typed
  eval/report DTO boundary validation. Full MCP contract still requires
  `--project-id` and a running API project.
- [x] `git diff --check` passed and `rg -n "<{7}|={7}|>{7}" .` returned no
  conflict markers after typed eval/report DTO boundary validation.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py::test_mcp_stdio_bridge_returns_jsonrpc_error_on_http_failure -q`
  (`1 passed`) after pinning MCP stdio bridge HTTP failure behavior.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_security_governance.py app/tests/test_feature_package_boundaries.py -q`
  (`73 passed`) after pinning MCP stdio bridge HTTP failure behavior.
- [x] `cd apps/api && .venv/bin/ruff check app/tests/test_mcp_adapter.py`
  passed after pinning MCP stdio bridge HTTP failure behavior.
- [x] `cd apps/api && .venv/bin/python -m compileall app/tests/test_mcp_adapter.py -q`
  passed after pinning MCP stdio bridge HTTP failure behavior.
- [x] `python3 scripts/check_feature_boundaries.py` passed after pinning MCP
  stdio bridge HTTP failure behavior.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_summary_shapes_status_failures_and_live_cache app/tests/test_eval_reports.py::test_eval_helpers_validate_typed_dto_boundaries -q`
  (`2 passed`) after adding typed eval-run summary and cache diagnostic DTO
  validation.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`53 passed`) after adding typed eval-run summary and cache diagnostic DTO
  validation.
- [x] `cd apps/api && .venv/bin/ruff check app/schemas/evals.py app/features/evals/report_summary.py app/tests/test_eval_reports.py`
  passed after adding typed eval-run summary and cache diagnostic DTO
  validation.
- [x] `cd apps/api && .venv/bin/python -m compileall app/schemas/evals.py app/features/evals/report_summary.py app/tests/test_eval_reports.py -q`
  passed after adding typed eval-run summary and cache diagnostic DTO
  validation.
- [x] `python3 scripts/check_feature_boundaries.py` passed after adding typed
  eval-run summary and cache diagnostic DTO validation.
- [x] `THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s59-summary-dtos LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json --skip-pytest --skip-security`
  passed with warn status (`39/39`; warning gates: `mcp_contract`,
  `pytest_quality_slice`, `security_check`) after adding typed eval-run summary
  and cache diagnostic DTO validation.
- [x] `git diff --check -- README.md IMPLEMENTATION_STATUS.md IMPLEMENTATION_BRIEF.md SPRINT_51_60_TODO.md docs/BACKEND_FEATURE_PACKAGE_MAP.md apps/api/app/schemas/evals.py apps/api/app/features/evals/report_summary.py apps/api/app/tests/test_eval_reports.py`
  passed after adding typed eval-run summary and cache diagnostic DTO
  validation.
- [x] `rg -n "<{7}|={7}|>{7}" README.md IMPLEMENTATION_STATUS.md IMPLEMENTATION_BRIEF.md SPRINT_51_60_TODO.md docs/BACKEND_FEATURE_PACKAGE_MAP.md apps/api/app/schemas/evals.py apps/api/app/features/evals/report_summary.py apps/api/app/tests/test_eval_reports.py`
  returned no conflict markers after adding typed eval-run summary and cache
  diagnostic DTO validation.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py::test_eval_report_summary_shapes_status_failures_and_live_cache app/tests/test_eval_reports.py::test_eval_report_summary_falls_back_to_gate_id_for_partial_failures app/tests/test_feature_package_boundaries.py::test_eval_report_summary_helpers_are_feature_owned -q`
  (`3 passed`) after pinning partial gate failure summary fallback.
- [x] `cd apps/api && .venv/bin/python -m compileall app/features/evals/report_summary.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  passed after pinning partial gate failure summary fallback.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  (`54 passed`) after pinning partial gate failure summary fallback.
- [x] `cd apps/api && .venv/bin/ruff check app/schemas/evals.py app/features/evals/report_summary.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py`
  passed after pinning partial gate failure summary fallback.
- [x] `cd apps/api && .venv/bin/python -m compileall app/schemas/evals.py app/features/evals/report_summary.py app/tests/test_eval_reports.py app/tests/test_feature_package_boundaries.py -q`
  passed after pinning partial gate failure summary fallback.
- [x] `python3 scripts/check_feature_boundaries.py` passed after pinning partial
  gate failure summary fallback.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_ai.py -q` (`14 passed`)
  after centralizing provider timeout/fallback metadata, timeout/cause
  classification, token/cost defaults, and redacted trace/run metadata in
  `app.ai.fallback_completion`.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_ai.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`54 passed`) for the provider timeout/fallback metadata edge-case slice.
- [x] `cd apps/api && .venv/bin/ruff check app/ai/fallback_completion.py app/tests/test_ai.py`
  passed after the provider timeout/fallback metadata slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/ai/fallback_completion.py app/tests/test_ai.py -q`
  passed after the provider timeout/fallback metadata slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the provider
  timeout/fallback metadata slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_project_overview.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`55 passed`) after adding typed weak-evidence decision labels, route
  contract fields, suggested action-card assertions, linked evidence checks, and
  no-direct-mutation coverage for decision recommendation/chat.
- [x] `cd apps/api && .venv/bin/ruff check app/schemas/validation.py app/features/decisions/recommendation.py app/services/validation_service.py app/tests/test_validation.py app/tests/test_feature_package_boundaries.py app/tests/test_contract_shapes.py`
  passed after the weak-evidence decision-label slice.
- [x] `cd apps/api && .venv/bin/python -m compileall app/schemas/validation.py app/features/decisions/recommendation.py app/services/validation_service.py app/tests/test_validation.py app/tests/test_feature_package_boundaries.py app/tests/test_contract_shapes.py -q`
  passed after the weak-evidence decision-label slice.
- [x] `python3 scripts/check_feature_boundaries.py` passed after the
  weak-evidence decision-label slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py::test_validation_interpretation_rejection_does_not_write_memory_or_confidence app/tests/test_tool_boundary.py::test_tool_proposal_rejection_resolves_approval_and_writes_audit_event app/tests/test_memory_service.py::test_memory_proposals_and_inspect_endpoint app/tests/test_feature_package_boundaries.py::test_memory_review_payload_helpers_are_feature_owned_and_service_compatible -q`
  (`4 passed`) after the approval rejection/proposal-audit slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_validation.py app/tests/test_tool_boundary.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`65 passed`) after the approval rejection/proposal-audit slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py::test_context_compiler_serializes_memory_conflicts_compression_and_drops app/tests/test_context_compiler.py::test_context_profiles_pin_policy_metadata_budget_and_drop_reasons app/tests/test_memory_service.py::test_memory_context_selection_explains_exclusions_and_conflicts app/tests/test_feature_package_boundaries.py::test_memory_context_pack_helpers_are_feature_owned_and_service_compatible app/tests/test_feature_package_boundaries.py::test_memory_inspection_helpers_are_feature_owned_and_service_compatible -q`
  (`5 passed`) after the context compression/conflict/Inspect serialization slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`58 passed`) after the context compression/conflict/Inspect serialization slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_contract_shapes.py -q`
  (`4 passed`) after adding governance/tool/memory route contract parity
  coverage.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_contract_shapes.py app/tests/test_tool_boundary.py app/tests/test_memory_service.py app/tests/test_mcp_adapter.py app/tests/test_feature_package_boundaries.py -q`
  (`65 passed`) after the route contract parity slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py::test_mcp_jsonrpc_proposal_matches_http_approval_and_audit_contracts -q`
  (`1 passed`) after adding MCP proposal approval parity and redacted
  `output_summary` coverage.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_security_governance.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`80 passed`) after the MCP/stdout/HTTP approval parity slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_grounding_helpers_are_feature_owned_and_service_compatible -q`
  (`1 passed`) after moving grounded Ask Thesys draft/response DTO shaping into
  `app.features.guide.grounding`.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_guide_eval_helpers_are_feature_owned_and_service_compatible app/tests/test_guide.py::test_guide_eval_reports_grounding_and_proposal_governance -q`
  (`2 passed`) after moving Ask Thesys guide eval read-model shaping into
  `app.features.guide.evals`.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_nudges.py app/tests/test_context_compiler.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`75 passed`) after the guide grounding/eval shaping slice.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_feature_package_boundaries.py::test_retrieval_diagnostic_helpers_are_feature_owned_and_service_compatible app/tests/test_evidence.py::test_broad_evidence_retrieval_plans_reranks_and_assembles_context app/tests/test_retrieval_quality_eval.py -q`
  (`3 passed`) after moving retrieval diagnostic DTO shaping into
  `app.features.retrieval.diagnostics`.
- [x] `cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_retrieval_quality_eval.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q`
  (`61 passed`) after the retrieval diagnostics slice.

Sprint 59 closeout status:

- `S59-R8`, `S59-R9`, and `S59-R10` now have explicit package-map/status/TODO
  dispositions. Context/memory policy helpers, shared duplication decisions,
  intentionally centralized services/models, and the future cleanup backlog are
  recorded in `docs/BACKEND_FEATURE_PACKAGE_MAP.md`.
- The final Sprint 59 verification run is recorded in `SPRINT_51_60_TODO.md`:
  focused R8/R9 slices passed (`70 passed, 1 warning` and `68 passed,
  1 warning`), the full backend suite passed (`264 passed, 3 warnings`), ruff
  and compileall passed, `python3 scripts/check_feature_boundaries.py` passed,
  the quality gate completed with warn status (`40/40`, no failed checks), diff
  check passed, conflict-marker scan found no matches, and generated
  `__pycache__` directories were removed.
- The only Sprint 59 items that should remain visible are explicit future or
  Sprint 60 handoffs, not vague cleanup. Live MCP stdio read/proposal smoke is
  still assigned to `S60-P4/G44-C` because it needs a live API project. Final
  `G49-*` status rows, README navigation, code-doc/comment pass, and final
  portfolio-claim audit belong to `S60-P10`.
- Do not mark a carried Sprint 41-50 gap complete from an implementation sprint
  title alone. `SPRINT_51_60_TODO.md` now requires every `G41-*` through
  `G50-*` ID to receive a final row with status, owner item, source/doc links,
  exact verification output or blocker, future owner when deferred, and README
  portfolio-claim consequence.
- Sprint 60 has ordered closeout packages (`S60-P1` through `S60-P10`) for the
  remaining docs, browser QA, provider/audit smoke, security/deployment
  posture, source-intelligence dispositions, post-refactor navigation, targeted
  code docs, and honest limits. Those packages are the pickup contract for all
  remaining gaps after Sprint 59.
