# Memory Model

Thesys stores durable project memory as domain objects, not as a long chat transcript.

## Memory Types

| Type | Use |
|---|---|
| `working` | Short-horizon context for an active guide or workflow. |
| `semantic` | Stable facts, assumptions, risks, and evidence-backed knowledge. |
| `episodic` | Events such as research sprints, validation results, and decisions. |
| `procedural` | Reusable process guidance, validation methods, and workflow preferences. |
| `preference` | User or project preferences that should steer future recommendations. |
| `project` | Current project thesis, stage, and strategic state. |

## Selection

`memory_service.select_memory_for_workflow` chooses memory types by workflow. For example, agentic research favors episodic, semantic, project, and procedural memory, while Ask Thesys can use working, semantic, project, and preference memory.

## Governance

Memory records include write policy, source entity, provenance metadata, status, confidence, expiration, and created-by fields. Agent-generated memory updates can be proposed and require approval before they are accepted as active project state.

## Review Pointers

- Model: `apps/api/app/db/models/memory.py`
- API schemas: `apps/api/app/schemas/memory.py`
- Service: `apps/api/app/services/memory_service.py`
- Router: `apps/api/app/routers/memory.py`
- Tool access: `list_project_memory` in `apps/api/app/services/tool_service.py`
