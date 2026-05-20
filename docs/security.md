# Security

Sprint 0 security posture:

- secrets are represented through environment variables
- local services are isolated through Docker Compose
- CORS is limited to the local web origin by default

Sprint 1 must add authenticated request boundaries and workspace authorization.
Retrieved evidence must always be treated as data, not instructions, once RAG
workflows are introduced.
