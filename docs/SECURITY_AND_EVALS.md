# Security And Evals

The AI surfaces are designed to fail closed around untrusted content, state
mutation, and secrets. This is a concise bridge between the product/evaluation
documentation and the authoritative security material; it is not the complete
security architecture.

For the full control set, start with [Security Overview](security.md),
[Security Documentation Guide](security/README.md),
[Security Architecture](security/SECURITY_ARCHITECTURE.md), and
[Dependencies And Tooling](DEPENDENCIES.md).

## Security Boundaries

| Boundary | Implementation |
|---|---|
| URL ingestion | `core/security.py` validates scheme, host, redirect targets, and response size to reduce SSRF risk. |
| Upload ingestion | File names, content types, byte limits, and simple magic-byte checks are validated before parsing. |
| Retrieved content | Prompt builders treat retrieved text as untrusted evidence, not instructions. |
| Tool calls | Tool schemas, project permissions, risk levels, and approval policies are enforced before execution. |
| Secret handling | Audit logs, tool payloads, workflow records, LangSmith metadata, and errors are redacted. |
| Fetched-page injection | `source_provenance_service.py` records prompt-injection markers as source risk metadata. |

## Eval Gates

Run from the repo root:

```bash
pnpm eval:research
pnpm eval:ai
```

The research eval checks source discovery, duplicate detection, provenance, citation coverage, unsupported claims, gap detection, agent traceability, retrieval diagnostics, cost visibility, LangSmith trace IDs, and redaction.

The AI eval gate checks static and optional live project gates for:

- context packs
- citation verifier
- memory service
- security URL/upload tests
- guide eval endpoint
- AI accounting
- source provenance
- prompt-injection marker coverage
- multimodal lineage

## Security Verification

The deterministic security suite lives under `apps/api/app/tests/security/`.
Promptfoo provides fast and full adversarial suites through
`pnpm security:redteam:fast` and `pnpm security:redteam:full`. Pull-request,
nightly, and release behavior is defined in `.github/workflows/security.yml`
and `.github/workflows/release-security.yml`.

Local tests prove implementation contracts. Hosted OIDC, object storage,
Garak-target, signed-release, and branch-protection claims require their
separate deployment/repository evidence; see
[Deployment And Security](DEPLOYMENT_SECURITY.md).

Live project evals are available at:

```text
/api/projects/{project_id}/evals/mvp
/api/projects/{project_id}/evals/v1-research
/api/projects/{project_id}/evals/guide
/api/projects/{project_id}/evals/ai
```
