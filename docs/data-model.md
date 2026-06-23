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
chunks, token counts, metadata, pgvector embeddings, and embedding provenance:
provider, model, dimension, version, `embedded_at`, and any embedding error.

Every tenant-scoped table should include `workspace_id` and backend queries must
enforce workspace membership.

Sprint 5 adds:

- artifacts
- artifact_versions
- claims
- claim_evidence_links
- assumptions
- risks

Artifacts store generated strategic outputs with immutable versions. Claims and
claim evidence links preserve citation provenance separately from markdown
content, while assumptions and risks remain structured project records.

Sprint 6 adds:

- competitors
- competitor_evidence_links

Competitor records store profile fields such as category, positioning, pricing,
features, strengths, weaknesses, differentiation notes, threat level, and
watchlist status. Competitor evidence links connect profiles to source records
and chunks; linked chunks also receive `competitor_id` metadata for filtered
retrieval.
