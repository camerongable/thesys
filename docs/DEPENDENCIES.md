# Dependencies And Tooling

## Scope

This guide explains Thesys's direct dependencies and operational tools. It is
not a copy of `uv.lock` or `pnpm-lock.yaml`: those files record the complete
resolved dependency graph. This guide covers the packages and tools that shape
architecture, security, development, CI, and deployment choices.

Versions and version ranges remain authoritative in `apps/api/pyproject.toml`,
`apps/web/package.json`, and the root `package.json`.

## Python Application Dependencies

| Dependency | Why Thesys uses it | Primary entry point | Environment |
|---|---|---|---|
| FastAPI and Uvicorn | Typed HTTP API, OpenAPI contracts, dependency injection, and an ASGI server for local and hosted API execution. | `apps/api/app/main.py`, `apps/api/app/routers/` | Runtime |
| Pydantic Settings and email-validator | Validated configuration, typed request/response schemas, and reliable email validation. | `apps/api/app/core/config.py`, `apps/api/app/schemas/` | Runtime |
| SQLAlchemy, psycopg, pgvector, and Alembic | Durable strategic state, PostgreSQL access, vector similarity types, and schema migrations. PostgreSQL is the source of truth; pgvector supports evidence retrieval. | `apps/api/app/db/`, `apps/api/alembic/` | Runtime and migrations |
| Temporal | Durable research-sprint execution across retries, worker restarts, and approval waits. It is deliberately separate from LangGraph's in-process reasoning state. | `apps/api/app/temporal/` | Runtime when durable workflows are enabled |
| LangGraph | Bounded multi-step agent reasoning for research planning, retrieval, synthesis, and critique. Application services retain authority over persistence and side effects. | `apps/api/app/services/agentic_research_service.py` | Runtime |
| httpx | Explicit outbound HTTP boundary for search, providers, OIDC metadata/JWKS, and integrations; timeouts and policy checks live around this boundary. | `apps/api/app/services/`, `apps/api/app/core/oidc.py` | Runtime |
| PyJWT with cryptography | OIDC JWT signature/claim validation and vetted cryptographic primitives. `cryptography` also implements envelope encryption; application code does not invent encryption algorithms. | `apps/api/app/core/auth.py`, `apps/api/app/security/encryption.py` | Hosted/runtime security |
| boto3 | S3-compatible private object storage for evidence files and presigned download flows. It is optional for local demonstrations that do not use cloud storage. | `apps/api/app/services/object_storage_service.py` | Hosted/runtime |
| Redis | Atomic, hashed rate-limit counters in hosted environments. Local and test settings deliberately use an in-memory adapter instead. | `apps/api/app/services/security_policy_service.py` | Hosted/runtime |
| Presidio analyzer and anonymizer | Rule-based PII detection, classification, and redaction before persistence, embeddings, traces, or provider egress. | `apps/api/app/services/data_protection_service.py` | Runtime |
| python-magic, pypdf, Pillow, and python-multipart | Content-type detection, bounded PDF handling, safe image decoding/re-encoding, and multipart uploads. These reduce the risk of treating a claimed file type as trustworthy. | `apps/api/app/services/secure_file_parser_service.py`, `apps/api/app/services/secure_image_service.py` | Runtime |
| LangSmith | Optional external AI tracing and evaluation export. It remains configuration-gated and receives redacted payloads. | `apps/api/app/services/langsmith_observability_service.py` | Optional hosted/runtime |
| OpenTelemetry SDK and OTLP exporter | Vendor-neutral request and security tracing. Only bounded, non-sensitive attributes are exported. | `apps/api/app/core/telemetry.py` | Optional hosted/runtime |
| prometheus-client | Low-cardinality operational and security metrics exposed by the application. | `apps/api/app/services/security_metrics_service.py` | Runtime |

## Python Development Dependencies

| Tool | Why it is used | When to run it |
|---|---|---|
| pytest | Behavioral, integration-contract, and regression coverage. The security suite proves deterministic boundaries rather than only unit-level helpers. | Local development and CI |
| Ruff | Fast linting and import/style checks. It catches common Python errors before tests. | Local development and CI |
| PyYAML | Loads deterministic red-team corpus fixtures and other YAML-backed test configuration. | Development, test, and CI |

## Web Dependencies

| Dependency | Why Thesys uses it | Primary entry point | Environment |
|---|---|---|---|
| Next.js, React, and React DOM | Application router, server/client rendering, and the interactive project workspace. | `apps/web/src/app/`, `apps/web/src/features/` | Runtime |
| TanStack React Query | Client-side server-state fetching, caching, invalidation, and retry state for API-backed views. | `apps/web/src/` API consumers | Runtime |
| TypeScript and React/Node types | Static contracts across the API client and UI, especially useful for streamed guide payloads. | `apps/web/tsconfig.json`, `apps/web/src/lib/api.ts` | Development and CI |
| Lucide React | Consistent accessible UI icons rather than hand-drawn SVG controls. | UI components | Runtime |
| class-variance-authority, clsx, and tailwind-merge | Controlled class composition and component variants without conflicting Tailwind classes. | UI components | Runtime |
| Tailwind CSS, PostCSS, and Autoprefixer | Build-time design tokens/utilities and browser-compatible generated CSS. | `apps/web` styling configuration | Development and build |
| pnpm | Reproducible JavaScript package manager; the repository pins `pnpm@10.12.1`. | Root `package.json`, workspace config | Development and CI |
| Sharp build approval | Next.js's image toolchain requires its native package build. `pnpm-workspace.yaml` explicitly allows only this known build step. | `pnpm-workspace.yaml` | Install/build |

## Security And CI Tools

| Tool | What it checks | Why it exists here | Cadence |
|---|---|---|---|
| Promptfoo | Deterministic direct, indirect, retrieval, memory, tool, PII, encoded, multimodal, output, and consumption adversarial cases. | It exercises application boundaries with repeatable fixtures rather than relying on model behavior alone. | Fast suite on PR; full suite nightly/release/local before major demo |
| Garak | Endpoint/model vulnerability probes such as prompt injection and encoding attacks. | Complementary black-box scan for a protected hosted test target; it is not needed for an offline portfolio demo. | Manual or scheduled hosted CI |
| Bandit | Python source-pattern security linting. | Catches common risky constructs that behavioral tests may not cover. | PR CI |
| Semgrep | Broader static-analysis rules across source. | Adds security-pattern coverage beyond Python-specific linting. | PR CI |
| pip-audit | Known-vulnerability scan for resolved Python dependencies. | Detects published advisories in the production dependency set. | PR and release CI |
| pnpm audit and OSV-Scanner | Known-vulnerability scans for JavaScript and repository lockfiles. | Covers the web dependency graph and multiple package ecosystems. | PR and release CI |
| Gitleaks | Secret-pattern scan of repository history/diffs. | Prevents accidentally committing credentials or tokens. | PR CI |
| CycloneDX SBOM via Anchore action | Machine-readable inventory of the software components in a build. | Provides release evidence and an input to supply-chain review. | PR/release CI |
| Trivy | High/critical image and dependency vulnerability scan. | Validates built API/web images rather than only source manifests. | Nightly/release CI |
| Cosign | Keyless signing and verification of immutable image digests. | Connects released container images to GitHub Actions identity and evidence. | Release CI |
| Dependabot | Proposed dependency updates for Actions, Python, and npm. | Keeps updates reviewable instead of silently changing locked dependencies. | Weekly GitHub automation |

The workflow definitions are [Security](../.github/workflows/security.yml) and
[Release Security](../.github/workflows/release-security.yml). They define
execution; GitHub repository settings still control whether Actions is enabled
and whether checks are required for merges.

## External Services And Policy Engines

| Service or tool | Role | Important limit |
|---|---|---|
| PostgreSQL with pgvector | Durable state, RLS tenant isolation, vector retrieval, and audit-chain storage. | Local tests exercise the contract; hosting must use the required runtime roles and TLS settings. |
| OPA | External policy decision point for tool, memory, model-routing, egress, and data-access rules expressed in `policies/*.rego`. | Policy availability is fail-closed for governed actions; the OPA service is not a Python package. |
| ClamAV-compatible scanner | Streaming malware scan before file storage/parsing in hosted mode. | Disabled or unavailable scanners quarantine rather than accept evidence. |
| S3-compatible object storage | Private evidence-object storage with scoped keys and presigned downloads. | Hosted bucket controls and credentials are deployment work. |
| LiteLLM-compatible provider | Model and embedding gateway chosen by configuration and approved-model policy. | A local deterministic fallback supports tests and demos; no provider credential is required for that mode. |
| Tavily-compatible search | Optional external source discovery. | Live provider use is egress- and configuration-gated; deterministic local data remains available. |

## Verification Commands

These are the most useful owner-level commands. See the README for environment
setup and [Deployment And Security](DEPLOYMENT_SECURITY.md) for hosted-only
requirements.

```bash
# Backend lint and tests
uv run --project apps/api ruff check apps/api/app
uv run --project apps/api pytest apps/api/app/tests -q

# Web checks
pnpm --filter thesys-web test
pnpm --filter thesys-web typecheck

# Deterministic adversarial checks
pnpm security:redteam:fast
pnpm security:redteam:full
```

These commands assume `uv` is on `PATH`, as configured by the project's setup
instructions.

## Selection Principles

Thesys prefers typed contracts, mature protocol implementations, and explicit
boundaries over custom security primitives or opaque agent frameworks. A
dependency is justified when it either supports a core product capability
(FastAPI, PostgreSQL, LangGraph, Temporal, Next.js) or moves a security concern
to a maintained implementation (PyJWT, cryptography, Presidio, Trivy, Cosign).
Optional external services remain configuration-gated so the portfolio demo can
be deterministic and credential-free.
