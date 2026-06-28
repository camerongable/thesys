# Deployment And Security

This document describes the current portfolio-project posture and the path to a
production-like deployment. It is intentionally explicit about what is local,
demo-safe, production-shaped, and still future owner work.

## Environment Profiles

| Profile | Intended use | Auth | Providers | Notes |
|---|---|---|---|---|
| local/dev | Developer machine | `AUTH_MODE=dev` | deterministic stubs by default | Dev headers allowed only in this mode. |
| deterministic demo | Portfolio demo without credentials | dev or API key | `LLM_STUB_MODE=always` | No paid provider egress required. |
| provider-backed demo | Local/staging demo with model/search credentials | API key or JWT | LiteLLM/OpenAI-compatible, optional search/multimodal | Requires egress allowlists and redaction. |
| staging-like | Hosted rehearsal | JWT or API key | configured provider allowlists | Should disable dev headers. |
| production-like | Future hosted product | JWT/OIDC/JWKS plus service keys | explicit provider allowlists | Needs managed secrets, backups, retention, and monitoring. |

## Auth Modes

| Mode | Behavior |
|---|---|
| `dev` | Local headers can identify workspace/user/role. Must not be used for hosted production. |
| `jwt` | Signed JWTs with issuer, audience, expiry, active key IDs, and revoked-token checks. |
| `api_key` | SHA-256 hashed service keys with active/revoked key checks. |

Production-like auth should use OIDC/JWKS rotation, token revocation, service
account scopes, workspace membership checks, and audit attribution. Some of
that shape exists in V1; managed OIDC/JWKS operations remain future owner work.

## Provider Egress And SSRF Controls

Security boundaries:

- URL ingestion validates scheme, host, redirect targets, unsafe ports, private
  address ranges, content type, and response size.
- Provider egress is constrained by configured LiteLLM, embedding, search, and
  multimodal provider settings.
- Prompt-injection markers from fetched content are provenance metadata, not
  instructions.
- Redaction runs before audit/tool/trace/LangSmith payloads are persisted or
  exported.
- Expensive workflows use rate limits, concurrency limits, and pre-call budget
  checks.

## Dependency And Security Audit Commands

```bash
python3 scripts/security_check.py
python3 scripts/audit_dependencies.py
pip-audit
pnpm audit --prod
```

If `pip-audit`, npm registry access, or hosted infrastructure is unavailable,
record the exact command, error, retry condition, and next owner in
`IMPLEMENTATION_STATUS.md`.

## Backup And Restore Boundaries

Production-like deployments should back up:

- Postgres application database, including pgvector embeddings
- object storage for uploaded files and future screenshot/page artifacts
- eval reports and trend artifacts
- audit logs and approval records
- AI run/step traces and redacted LangSmith export payloads
- Temporal workflow state if Temporal is deployed outside local dev

Restore testing should verify project load, evidence retrieval, memory/context
Inspect, Ask Thesys, validation, decision records, MCP read tools, and eval
report access after restore.

## Hosted Smoke Checklist

Run or explicitly block these smoke checks for a hosted demo:

- project load
- evidence ingestion and retrieval
- Ask Thesys deterministic and provider-backed answer path
- validation plan generation
- decision recommendation
- Memory and Context Inspect
- MCP read tool
- eval report load
- provider-egress denial path
- budget-denial path

## Verification

Backend security and governance tests:

```bash
cd apps/api && .venv/bin/pytest app/tests/test_security_governance.py app/tests/test_tool_boundary.py app/tests/test_mcp_adapter.py -q
```

Aggregate quality/security gate:

```bash
THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60 LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json
```

## Current Limits

- OIDC/JWKS provider operations, hosted key rotation runbooks, and managed
  tenant membership are production hardening work.
- Object-storage backup/restore is documented, but local V1 may not persist
  screenshots/page artifacts.
- Hosted smoke checks require deployed infrastructure and seeded demo data.
