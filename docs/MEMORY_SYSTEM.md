# Memory System

Thesys stores durable project memory as typed domain state. It is deliberately
separate from chat history so AI workflows can select, inspect, compact, and
approve memory with provenance.

## Source-Linked Lifecycle

```text
workflow insight or user input
-> proposed memory item
-> approval request when write policy requires review
-> accepted active memory or rejected archived memory
-> workflow-specific selection
-> context pack
-> compaction, conflict detection, supersession, or archive
-> audit and Inspect records
```

Primary owners:

| Concern | Source |
|---|---|
| Memory service and DB orchestration | `apps/api/app/services/memory_service.py` |
| Memory DB model | `apps/api/app/db/models/memory.py` |
| Memory API schema | `apps/api/app/schemas/memory.py` |
| Context pack serialization | `apps/api/app/features/memory/context_pack.py` |
| Selection and conflict helpers | `apps/api/app/features/memory/selection_policy.py` |
| Inspect and explanation payloads | `apps/api/app/features/memory/inspection.py` |
| Review and audit metadata | `apps/api/app/features/memory/review.py` |
| Compaction payload shaping | `apps/api/app/features/memory/compaction.py` |

## Memory Types

| Type | Purpose |
|---|---|
| `working` | Short-horizon state for active guide or workflow context. |
| `semantic` | Stable facts, assumptions, risks, and evidence-backed knowledge. |
| `episodic` | Events such as research sprints, validation results, and decisions. |
| `procedural` | Reusable process guidance and validation methods. |
| `preference` | User or project preferences that should steer recommendations. |
| `project` | Current thesis, stage, and strategic state. |

Workflow selection is controlled by `WORKFLOW_MEMORY_TYPES` in
`memory_service.py`. Research favors episodic, semantic, project, and
procedural memory. Ask Thesys favors working, semantic, project, and preference
memory. Validation and decision workflows include episodic history when stale
history is useful for strategic decisions.

## States And Review Flow

Memory states used by V1 include:

- `proposed`: generated or suggested memory waiting for review
- `active`: eligible for workflow selection
- `stale` or expired: excluded by default unless the workflow allows stale
  historical context
- `compacted`: condensed from multiple prior memories with source provenance
- `conflict`: marked when memory appears to disagree with another item
- `superseded`: replaced by a newer memory item
- `archived`: rejected, retired, or no longer selected

Proposal review is approval-gated when model-generated memory would mutate
project state. Rejection archives proposed memory, removes it from Inspect
selection/proposal surfaces, writes reviewer provenance, and emits
`memory_update_rejected` audit metadata.

## Compaction And Conflict Policy

Compaction is used to reduce repeated or aging context while preserving source
IDs. Conflict detection groups related memory by normalized text/entity keys.
Conflict resolution supports keep, supersede, archive, and merge actions. The
service owns DB mutations and approval/audit persistence; feature modules own
pure payload shaping.

## Context-Pack Eligibility

`select_memory_for_context` returns selected memory, excluded memory, conflict
metadata, and policy details. Exclusions include wrong memory type, stale or
expired records, proposed records not yet approved, and workflow-specific
limits. Context packs preserve selected IDs, excluded IDs, conflict IDs, and
selection reasons for Inspect.

## Adding A Memory Type

1. Add the enum/schema value in `apps/api/app/schemas/memory.py`.
2. Confirm model and persistence behavior in `ProjectMemoryItem`.
3. Add the type to the appropriate `WORKFLOW_MEMORY_TYPES` profiles.
4. Update selection/exclusion tests for stale, conflict, and workflow behavior.
5. Add Inspect serialization and explanation coverage when new metadata is
   introduced.
6. Update this document and README navigation.

## Verification

```bash
cd apps/api && .venv/bin/pytest app/tests/test_memory_service.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q
```

Browser QA for Sprint 60 should cover Memory Inspect filters, proposal review,
compaction records, selection reasons, conflict keep/supersede/archive/merge
actions, and hidden-by-default advanced details.

## Current Limits

- DB reads/writes, approval gates, conflict mutations, and audit persistence
  remain service-owned in V1.
- Larger compaction source-selection DTOs and conflict-resolution command DTOs
  are future cleanup.
- Browser QA must be retried in an environment where web dependencies install
  and the IDE browser can run the app.
