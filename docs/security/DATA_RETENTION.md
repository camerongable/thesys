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
| Model prompts | 14 days | Local AI-record retention policy; cleanup job pending |
| Model outputs | 30 days | Local AI-record retention policy; cleanup job pending |
| LangSmith traces | 14 days | LangSmith project retention setting |
| Audit events | 365 days | Database retention policy; cleanup job pending |
| Security events | 730 days | Database retention policy; cleanup job pending |
| Temporal history | 30 days | Temporal namespace retention setting |

Raw and reversible restricted data use shorter defaults than redacted audit and
security metadata. Expired evidence is deleted through the source-deletion
propagation path, so objects, chunks, embeddings, derived evidence links, and
dependent memory are removed together. Expired PII token maps are purged within
their workspace. Local AI, audit, and security record policies are registered
but require a scheduled purge job before they are enforced. External LangSmith
and Temporal retention must be configured in those providers; the application
does not claim to delete provider-owned history itself.
