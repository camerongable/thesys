# Threat Model

This threat model tracks the current portfolio-project implementation and the
production shape it is moving toward.

## Assets

- Workspace-scoped project strategy, evidence, memory, artifacts, decisions, and
  validation results.
- Uploaded files, fetched source snapshots, extracted text, chunks, embeddings,
  and object-storage keys.
- AI prompts, structured outputs, tool payloads, approval requests, audit events,
  LangSmith metadata, eval reports, and provider credentials.
- Auth tokens, API keys, service-account identities, workspace membership, and
  role assignments.

## Trust Boundaries

- Browser to FastAPI API.
- FastAPI to database, object storage, Temporal, LiteLLM, embedding/search/OCR
  providers, and LangSmith.
- User-supplied uploads, notes, URLs, fetched pages, and generated source
  candidates to AI prompts.
- MCP/agent tool calls to governed state-changing services.
- Local development auth headers to production auth modes.

## Attack Surfaces And Controls

| Surface | Risk | Current controls | Future hardening |
| --- | --- | --- | --- |
| Local dev auth | Dev headers accepted in production | `AUTH_MODE=dev` only; dev headers rejected in `jwt` and `api_key` modes | OIDC/JWKS, token revocation, tenant-managed membership |
| JWT/API key auth | Forged identities or stale service keys | HS256 JWT signature, issuer, audience, expiry, active key IDs, revoked JWT IDs; SHA-256 API key hashes and revoked hashes | JWKS rotation, revocation table, service-account scopes |
| Workspace data | Cross-tenant access | `AuthContext.workspace_id` scoping on project services and route permissions | Postgres RLS for hosted multi-tenancy |
| URL fetching | SSRF, metadata service access, DNS rebinding, unsafe redirects | Scheme checks, no credentials, port/domain policy, DNS private-address blocks, redirect revalidation, max redirects, size caps | Connection-time DNS pinning, egress proxy, per-domain allowlists |
| Fetched content | Parser abuse, prompt injection, oversized responses | content-type allowlist, content-length/body caps, prompt-injection marker detection, untrusted-content prompt wrappers | sandboxed parsers, MIME sniffing, malware scan |
| Uploads | Path traversal, type confusion, oversized files, parser/OCR abuse | filename sanitization, extension/content-type allowlist, size caps, magic-byte checks | malware scanning, file quarantine, async extraction isolation |
| Model egress | Prompt/data sent to unapproved providers | provider host allowlist for LiteLLM, embeddings, search, multimodal, health checks | provider-specific policies, egress proxy, DLP filters |
| Agent/MCP tools | Unauthorized state changes or over-broad tool input | tool registry, role gates, input guards, scope guards, approval requests, audit events | per-tool quotas, client identity scopes, MCP session policy |
| Human approvals | Silent memory or decision mutation | approval gates for governed proposals and high-risk actions | signed approval records, expiry policy, reviewer separation |
| Temporal workflows | Duplicate or stuck long-running work | workflow IDs, status endpoints, retry/cancel routes, policy guard on starts/retries | deterministic activity audit, distributed concurrency limits |
| Object storage | Sensitive artifacts leaked or overwritten | local/S3 abstraction, sanitized metadata paths | bucket policies, KMS, signed URL expiry, backup/restore tests |
| Database | Sensitive logs and AI traces persisted | workspace scoping, redaction before audit/tool/trace persistence | encryption at rest, RLS, retention controls |
| LangSmith/logs | Secrets in traces or errors | metadata and error redaction helpers, tests | provider-side retention policy, trace sampling controls |
| Evals/reports | Eval artifacts expose sensitive prompt/source data | redacted eval metadata, local scripts, bounded reports | artifact retention policy, private CI storage |
| Rate/cost abuse | Expensive repeated AI or extraction calls | per-user/workspace rate limits, concurrency guards, budget preflight | Redis-backed distributed limiter, billing-account budgets |

## Security Regression Commands

```bash
python3 scripts/security_check.py
python3 scripts/security_check.py --strict-audit
```

The security check covers auth/RBAC, SSRF/upload guards, tool-boundary tests,
MCP contract behavior, redaction, provider egress, budget preflight, and
dependency audit commands.
