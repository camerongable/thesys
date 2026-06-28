# Security and Evals

The AI surfaces are designed to fail closed around untrusted content, state mutation, and secrets.

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

Live project evals are available at:

```text
/api/projects/{project_id}/evals/mvp
/api/projects/{project_id}/evals/v1-research
/api/projects/{project_id}/evals/guide
/api/projects/{project_id}/evals/ai
```
