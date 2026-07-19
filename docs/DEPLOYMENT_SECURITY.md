# Deployment And Security

This document describes the current portfolio-project posture and the path to a
production-like deployment. It is intentionally explicit about what is local,
demo-safe, production-shaped, and still future owner work.

## Kubernetes Baseline

`infra/k8s/base` provides a restricted API and worker deployment baseline with
separate service accounts, non-root and read-only filesystems, dropped
capabilities, RuntimeDefault seccomp, resource limits, disruption budgets,
default-deny networking, and digest-only image admission. A release must replace
the intentionally non-deployable zero digest with a signed immutable image,
provide `thesys-runtime` through the cluster secret store, and configure
approved egress gateways for managed infrastructure and providers.

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

`POST /api/session/revoke` invalidates the authenticated OIDC `sid` or JWT
`jti`. The database stores a SHA-256 digest of that identifier, scoped to the
user and workspace; it never stores the raw session or token identifier. Every
authenticated request checks the digest before route handling, and successful
self-revocation creates a `session_revoked` audit event. Service accounts and
tokens without a `sid` or `jti` cannot use this endpoint.

`PATCH /api/workspace/members/{user_id}/role` is owner-only and preserves at
least one workspace owner. A successful change emits a fixed `role_change`
authentication event attributed to the actor and a redacted governance event
for the affected membership. Requests for a member outside the caller's
workspace return the same 404 as an unknown member while recording a
tenant-scoped `cross_tenant_access_attempt` without the target identifier.

All project-scoped services resolve the project through the shared workspace
filter. A failed project lookup returns `404 Project not found` and emits a
tenant-attributable `cross_tenant_access_attempt` with reason
`project_scope_denied`. Forced RLS intentionally makes unknown and
other-workspace UUIDs indistinguishable, so the event contains neither the
requested identifier nor a claim that it belongs to another tenant.

Direct decision and tool-invocation routes apply the same non-enumerating 404
behavior when their resource IDs are outside the current workspace. They emit
fixed `decision_scope_denied` or `tool_invocation_scope_denied` reasons through
the same attributed `cross_tenant_access_attempt` event and never store either
requested identifier.

The standalone workflow-run API protects AI execution and trace metadata with
the same pattern. An out-of-workspace `run_id` returns `404 Workflow run not
found` and records `workflow_run_scope_denied` without persisting that ID.

Research-plan editing and research-sprint approval also use direct resource
IDs. Their scoped lookup failures return the existing 404 responses and record
fixed `research_plan_scope_denied` or `research_sprint_scope_denied` reasons
without persisting the requested IDs.

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
  checks. Local/test settings use a process-local limiter; staging and production
  require the Redis-backed backend during settings validation.

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

## Release And Nightly Security Gates

Version tags invoke the release gate, which publishes digest-pinned API and web
images with provenance, CycloneDX SBOMs, keyless Cosign signatures, Trivy scan
evidence, and a fail-closed security report. The report requires a named SBOM
and verified digest signature for every release image.

Nightly security also runs the full deterministic Promptfoo corpus, broad API
security regressions, local API/web image scans, and a Trivy scan of
`infra/k8s/base`. Garak probes a dedicated HTTPS scan proxy rather than a
public production route. Configure `GARAK_TARGET_URI` and, when required,
`GARAK_TARGET_AUTHORIZATION` as protected CI secrets; the endpoint accepts
`{"prompt": "..."}` and returns `{"text": "..."}`. It must enforce the
same model allowlist and egress policy as the target application and be scoped
to the red-team environment only.

All third-party Actions are commit-pinned and reviewed through weekly Dependabot
pull requests for Actions, Python, and npm. The repository administrator must
also enforce branch protection for the default branch: require pull-request
reviews, require the Security workflow, dismiss stale approvals, and restrict
direct pushes. Those GitHub-hosted repository settings cannot be enforced from
this repository, so they remain a deployment prerequisite rather than an
in-repository claim.

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
