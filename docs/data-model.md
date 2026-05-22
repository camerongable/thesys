# Data Model

Sprint 0 includes shared SQLAlchemy model infrastructure and an initial Alembic
migration that enables `pgvector`.

Sprint 1 adds:

- users
- workspaces
- workspace_members
- projects
- project_theses

Sprint 2 adds:

- ai_runs
- ai_steps

Sprint 3 adds:

- project_intakes
- customer_segments
- problems

Sprint 4 adds:

- evidence_sources
- evidence_chunks

`evidence_sources` stores URL, note, transcript, manual, and file-level source
metadata, parsed text, summary, classification, ingestion status, and object
storage keys for uploads. `evidence_chunks` stores project-scoped parsed text
chunks, token counts, metadata, and 1536-dimensional pgvector embeddings.

Every tenant-scoped table should include `workspace_id` and backend queries must
enforce workspace membership.
