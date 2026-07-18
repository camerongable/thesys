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
| `oidc` | Asymmetric JWT verification through JWKS followed by strict active user, workspace membership, and role resolution. |

Production-like auth should use OIDC/JWKS rotation, token revocation, service
account scopes, workspace membership checks, and audit attribution. Some of
that shape exists in V1; managed OIDC/JWKS operations remain future owner work.

The API is deliberately stateless: it authenticates with bearer or API-key
headers and does not issue browser cookies. CORS must therefore keep
`allow_credentials` disabled. Every API response carries a restrictive CSP with
`frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy:
no-referrer`, a restrictive permissions policy, and `X-Frame-Options: DENY`.
Production also sends HSTS for one year with subdomains. If a later web-auth flow
uses cookies, it must introduce secure/HttpOnly/SameSite cookies, short session
lifetime, rotation, logout invalidation, and CSRF validation as one design.

Authentication outcomes use the immutable `authentication_events` table.
Successful authentication events carry the resolved workspace/user IDs; failed
pre-authentication events carry neither ID. The schema contains only a fixed
event type, authentication method, fixed reason code, IDs, and timestamp, so it
cannot persist bearer tokens, API keys, or arbitrary request metadata. Forced
RLS scopes attributed events to their workspace, and a separate insert-only
policy permits only null-identity pre-authentication failures.

## Database Roles And RLS

| Role | Runtime use | Privileges |
|---|---|---|
| `thesys_migration` | Migration command only | Schema create/alter and `BYPASSRLS`; never inherited by API or worker |
| `thesys_api` | FastAPI process | Identity and tenant-table DML; no schema create, ownership, superuser, or RLS bypass |
| `thesys_worker` | Temporal worker | Identity reads and tenant-table DML; no identity mutation, schema create, ownership, superuser, or RLS bypass |
| `thesys_readonly` | Operator/reporting access | `SELECT` only and still subject to tenant context/RLS |

The API container runs Alembic with `MIGRATION_DATABASE_URL`, unsets that
credential, and then execs Uvicorn with `DATABASE_URL` for `thesys_api`.
Production deployments should run migrations as a separate job so migration
credentials never enter the API container.

The local passwords in `infra/postgres/init.sql` are development-only. Existing
Docker volumes created before the role bootstrap must be recreated before using
the new URLs:

```bash
docker compose down -v
docker compose up --build
```

RLS is enabled and forced for all currently modeled tenant tables. API and
worker sessions bind validated workspace/user IDs transaction-locally and
reapply them after each commit or rollback. Run direct policy verification on a
migrated Postgres instance:

```bash
cd apps/api
RLS_TEST_DATABASE_URL=postgresql+psycopg://thesys_api:<password>@<host>/<database> \
  .venv/bin/pytest app/tests/security/test_postgres_rls.py -q
```

## Object Storage

Hosted profiles require `OBJECT_STORAGE_MODE=s3`, an HTTPS
`S3_ENDPOINT_URL`, disabled application bucket creation, and
`S3_VERIFY_BUCKET_SECURITY=true`. Startup configuration and the first storage
operation fail closed if these requirements are absent. Runtime verification
requires all public-access blocks, bucket-owner-enforced object ownership,
configured AES256 or KMS default encryption, the configured workspace-prefix
retention rule, and a bucket policy denying insecure transport.

Evidence keys are scoped as
`workspaces/{workspace_id}/projects/{project_id}/sources/{source_id}/...`.
Application authorization loads that exact tenant resource before issuing a
GET URL, and presigns expire in 30-900 seconds. Writes set explicit content type,
safe attachment disposition, and server-side encryption without object ACLs.
Source and project deletion remove stored objects and record redacted audit
metadata. Bucket provisioning is an infrastructure responsibility in hosted
environments; `S3_AUTO_CREATE_BUCKET=true` is only for local MinIO setup.

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
- Private evidence-object controls have deterministic coverage, but live
  production-bucket policy and local MinIO auto-configuration checks remain
  deployment-owner verification. Local V1 may not persist screenshots/page
  artifacts.
- Hosted smoke checks require deployed infrastructure and seeded demo data.
