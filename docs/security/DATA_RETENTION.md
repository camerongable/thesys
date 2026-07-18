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
their workspace. When `RETENTION_CLEANUP_SCHEDULE_ENABLED=true`, the Temporal
worker creates or reconciles the global `retention-cleanup-v1` schedule at the
configured interval. Its workflow selects one active principal per workspace
and invokes the tenant-bound cleanup activity separately for each workspace, so
RLS remains in force for every destructive operation. It retains run status,
timing, token, and cost fields while removing expired prompts, outputs, errors,
local LangSmith references, and workspace-attributable audit/security events.
Active session revocations and unscoped pre-authentication failures are
intentionally excluded: the former remain authentication controls, and the
latter require a separately authorized platform-maintenance path.

Temporal namespace history is reconciled to `RETENTION_TEMPORAL_HISTORY_DAYS`
when `TEMPORAL_NAMESPACE_RETENTION_RECONCILE_ENABLED=true`; the worker fails
startup if that configured reconciliation cannot be performed. LangSmith
project retention is configured by the LangSmith administrator. When tracing is
enabled, `LANGSMITH_PROVIDER_RETENTION_DAYS` must explicitly equal
`RETENTION_LANGSMITH_TRACE_DAYS`, preventing the application from emitting
traces when the deployment has not confirmed the provider setting.
