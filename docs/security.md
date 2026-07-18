# Security

Thesys treats the AI layer as a security boundary, not just a model-calling
utility. The current branch includes controls for local development, portfolio
demo use, and the production shape that a hosted version would need.

## Security Contract

The Sprint 61 security contract is maintained across:

- [Threat model](security/THREAT_MODEL.md)
- [Data classification](security/DATA_CLASSIFICATION.md)
- [Control matrix](security/CONTROL_MATRIX.md)
- [Security architecture and trust boundaries](security/SECURITY_ARCHITECTURE.md)
- [Abuse cases](security/ABUSE_CASES.md)

The code-owned data types, tenant paths, memory-write paths, and twelve security
invariants live in `apps/api/app/security/contracts.py`. Automated checks in
`apps/api/app/tests/security/test_security_invariants.py` keep the contract tied
to mapped tables and governed tool/memory surfaces. The older
`docs/THREAT_MODEL.md` remains a concise Sprint 54 implementation snapshot; the
files above are authoritative for the Sprint 61-68 hardening phase.

## Auth And Authorization

- `AUTH_MODE=dev` uses `X-Dev-User-*` headers for local-only identity setup.
- `AUTH_MODE=jwt` verifies HS256 bearer tokens with issuer, audience, expiry,
  active key IDs, revoked token IDs, role, and workspace-name claims.
- `AUTH_MODE=api_key` verifies SHA-256 API key hashes and maps accepted keys to
  a service-account workspace membership. Revoked key hashes are denied even if
  they remain present in the accepted-key set.
- Dev auth headers are rejected outside `AUTH_MODE=dev`.
- Project routes still enforce workspace scoping and role permissions through
  `AuthContext`, `WorkspaceMember`, and `require_permission`.

The JWT verifier is a production-auth shape for this portfolio project. A real
hosted deployment should replace the shared-secret verifier with OIDC/JWKS,
provider-managed workspace membership, and database-backed revocation state.

## Expensive Workflow Policy

`security_policy_service.guarded_workflow` protects AI-heavy routes before they
start work:

- per-user and per-workspace rate limits
- per-user and per-workspace concurrency limits
- pre-call token and cost budget checks against persisted `AIRun` usage
- provider egress allowlist checks for live LLM, embedding, search, and
  multimodal endpoints
- denied-call audit events with redacted metadata

The guard is applied to Ask Thesys, research sprint planning, source discovery,
agentic research, evidence ingestion/retrieval/reembedding, opportunity briefs,
competitor analysis, assumption/risk extraction, validation planning,
validation interpretation, decision guidance, MCP tool calls, eval endpoints,
and AI smoke tests.

## URL Fetching And Uploads

URL evidence ingestion validates each initial and redirected URL:

- only `http` and `https` schemes
- no embedded credentials
- configured port allowlist
- optional domain denylist and allowlist
- DNS resolution blocks loopback, private, link-local, multicast, reserved, and
  unspecified addresses
- redirect revalidation on each hop
- content-length and final response-size caps
- fetched response content-type allowlist

Uploads validate filenames, extensions, content types, file size, UTF-8 text,
and lightweight magic bytes for PDF, PNG, JPEG, and WebP before storage or
model/OCR processing.

## Provider Egress

Live provider clients fail closed unless their endpoint host is allowlisted:

- LiteLLM chat completions and streaming
- LiteLLM embeddings
- LiteLLM multimodal extraction
- Tavily external search
- LiteLLM health checks

Defaults permit local LiteLLM plus common hosted provider domains. Production
deployments should narrow `PROVIDER_EGRESS_ALLOWED_HOSTS` to the actual gateway
and provider endpoints in use.

## Prompt Injection And Redaction

Retrieved evidence is treated as untrusted source data. RAG and guide prompts
wrap retrieved content in untrusted-content blocks and instruct models not to
follow source instructions. Source provenance records prompt-injection markers.

Logs, audit events, tool payloads, LangSmith metadata, approval requests, and
UI-facing error paths use redaction helpers for API keys, bearer tokens,
authorization headers, emails, and other sensitive strings.

## Local Checks

Run focused security checks:

```bash
python3 scripts/security_check.py
```

Run dependency audits:

```bash
python3 scripts/audit_dependencies.py
python3 scripts/audit_dependencies.py --strict
```

The non-strict audit mode is useful on local machines where `pip-audit`, `pnpm`,
or registry access may be unavailable. CI should use strict mode once those tools
are installed and network policy is stable.

## Remaining Production Work

- Replace HS256 JWT demo verifier with OIDC/JWKS validation.
- Move rate/concurrency counters to Redis or another shared store for multi-node
  deployments.
- Add token rotation/revocation tables for API keys and service accounts.
- Add provider-specific response-size enforcement where SDKs expose streaming
  byte counters.
- Add row-level security if the product becomes multi-tenant SaaS.
