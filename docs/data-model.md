# Data Model

Sprint 0 includes shared SQLAlchemy model infrastructure and an initial Alembic
migration that enables `pgvector`.

Sprint 1 should add:

- users
- workspaces
- workspace_members
- projects
- project_theses

Every tenant-scoped table should include `workspace_id` and backend queries must
enforce workspace membership.
