# Data Retention

`app.services.retention_service` is the authoritative retention registry. Each
duration is configured through an environment variable so deployments can meet
their own legal and contractual obligations.

| Asset | Default | Enforcement boundary |
| --- | ---: | --- |
| Raw source objects | 30 days | Object-storage lifecycle |
| Sanitized text | 90 days | Evidence cleanup |
| Embeddings | 90 days | Evidence cleanup |
| PII token maps | 30 days | Database cleanup |
| Model prompts | 14 days | Workspace-scoped local-record cleanup |
| Model outputs | 30 days | Workspace-scoped local-record cleanup |
| LangSmith traces | 14 days | LangSmith project retention setting |
| Audit events | 365 days | Workspace-scoped local-record cleanup |
| Security events | 730 days | Workspace-scoped local-record cleanup |
| Temporal history | 30 days | Temporal namespace retention setting |

Raw and reversible restricted data use shorter defaults than redacted audit and
security metadata. Expired evidence is deleted through the source-deletion
propagation path, so objects, chunks, embeddings, derived evidence links, and
dependent memory are removed together. Expired PII token maps are purged within
their workspace. The Temporal worker exposes
`run_workspace_retention_cleanup_activity` for a per-workspace maintenance
schedule. It retains run status, timing, token, and cost fields while removing
expired prompts, outputs, errors, local LangSmith references, and
workspace-attributable audit/security events. Active session revocations and
unscoped pre-authentication failures are intentionally excluded: the former
remain authentication controls, and the latter require a separately authorized
platform-maintenance path. External LangSmith and Temporal retention must still
be configured in those providers; the application does not claim to delete
provider-owned history itself.
