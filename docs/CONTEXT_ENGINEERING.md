# Context Engineering

Thesys compiles context as structured workflow input, not as a loose prompt
string. The goal is to make every model call inspectable: which sources were
included, which were dropped, what was treated as untrusted, and which workflow
profile controlled the budget.

## Source-Linked Flow

```text
workflow request
-> app.services.context_service.ContextCompiler
-> profile lookup in CONTEXT_PROFILES
-> domain state, memory, retrieval results, tool outputs, user inputs
-> app.features.context.evidence_items
-> app.features.memory.context_pack
-> app.features.context.packing
-> app.schemas.context.ContextPack
-> prompt builder or Inspect surface
```

Primary owners:

| Concern | Source |
|---|---|
| Profile selection and workflow compiler | `apps/api/app/services/context_service.py` |
| Context pack schema | `apps/api/app/schemas/context.py` |
| Evidence result item shaping | `apps/api/app/features/context/evidence_items.py` |
| Token-budget packing and dropped-item metadata | `apps/api/app/features/context/packing.py` |
| Memory-to-context serialization | `apps/api/app/features/memory/context_pack.py` |
| Memory selection policy | `apps/api/app/services/memory_service.py`, `apps/api/app/features/memory/selection_policy.py` |

## Context Profiles

Profiles live in `CONTEXT_PROFILES` in `context_service.py`.

| Profile | Token cap | Expected item types |
|---|---:|---|
| `assumption_extraction` | 2200 | project summary, memory, context summary |
| `guide_chat` | 3200 | project summary, thesis, memory, evidence, conversation turns, actions |
| `agentic_research` | 4500 | project summary, memory, tool output, evidence, gaps |
| `opportunity_brief` | 4200 | project summary, memory, evidence, safety instructions |
| `competitor_analysis` | 3800 | project summary, memory, evidence, tool output |
| `validation_plan` | 3200 | project summary, memory, assumptions, risks |
| `validation_result_interpretation` | 3600 | project summary, memory, validation, conversation turns |
| `decision_recommendation` | 3600 | project summary, memory, assumptions, risks, validation, decisions |

The effective budget is the lower of the profile cap and
`settings.retrieval_context_token_budget`.

## Inputs

The compiler accepts these context sources:

- Domain state from project, thesis, assumptions, risks, validation missions,
  decisions, and current workflow state.
- Selected memory from `select_memory_for_context`.
- Retrieved evidence from retrieval services and guide/research tool output.
- Untrusted user, fetched, or tool-provided text.
- Tool output dictionaries with tool names and provenance.
- Conflict metadata from memory selection.

Untrusted inputs are marked with `untrusted=True` and should be wrapped by
prompt builders as evidence, never as instructions. Research prompt builders
also use explicit trusted/untrusted splitting and
`<untrusted_retrieved_content>` wrappers.

## Included, Dropped, Compressed, Stale, And Conflict Examples

Context pack items carry source, priority, token estimate, metadata, and
untrusted flags. Packing records:

- selected items that fit the profile budget
- dropped items with reasons such as budget pressure or max-item caps
- stale memory excluded by memory policy
- conflicting memory IDs and conflict groups
- unsafe or unknown input coerced to a safe conversation-turn type
- compressed summaries when older context is condensed before prompt assembly
- tool-output items with `tool_name` metadata

Inspect payloads expose these details behind workflow inspection surfaces. They
should not be placed on the homepage or the primary project workflow.

## Tests And Evals

Core verification:

```bash
cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q
```

Broader closeout:

```bash
cd apps/api && .venv/bin/pytest app/tests/test_context_compiler.py app/tests/test_memory_service.py app/tests/test_contract_shapes.py app/tests/test_feature_package_boundaries.py -q
```

Quality-gate coverage:

```bash
LLM_STUB_MODE=always python3 scripts/eval_ai_quality.py --json
THESYS_EVAL_REPORT_DIR=/tmp/thesys-eval-report-s60 LLM_STUB_MODE=always python3 scripts/eval_quality_gate.py --json
```

Browser QA still belongs to Sprint 60 when web dependencies are available:
Context Inspect should show included, dropped, compressed, stale, conflicting,
unsafe, and tool-output rows with advanced details hidden by default.

## Adding A Context Profile

1. Add a `ContextProfile` entry to `CONTEXT_PROFILES`.
2. Decide the token cap, required item types, and allowed memory policy.
3. Add or update a workflow builder in `context_service.py`.
4. Use feature-owned helpers for evidence, memory, and packing shapes.
5. Add tests for profile metadata, token budget, dropped-item behavior,
   untrusted-content handling, stale/conflict policy, and Inspect output.
6. Add the profile to this document and to the relevant eval or quality gate.

## Current Limits

- `ContextCompiler` remains in `app.services.context_service` for V1 because it
  still owns profile selection, settings, workflow builders, DB-backed memory
  policy, and eval route orchestration.
- A typed internal `CompiledContext` object is future cleanup before moving the
  compiler under `app.features.context`.
- Browser QA for Context Inspect is environment-dependent and must be recorded
  in `IMPLEMENTATION_STATUS.md` when Sprint 60 is finalized.
