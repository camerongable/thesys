# Governance and MCP Boundary

Thesys uses governed tools to keep agent behavior bounded and inspectable.

## Tool Lifecycle

```text
agent or MCP client
→ tool schema validation
→ permission and risk check
→ read execution or proposal creation
→ audit event
→ approval request when required
→ approved state mutation
```

## Access Modes

| Mode | Meaning |
|---|---|
| `read` | Inspect project state or retrieval results. |
| `proposal` | Create an approval request for a state-changing recommendation. |
| `write` | Mutate state directly only when policy and role allow it. |

The important invariant is that model-originated proposals do not silently mutate strategic project state.

## MCP Adapter

`app/mcp/adapter.py` exposes the existing governed tools through an MCP-shaped HTTP adapter:

- `/api/mcp/tools`
- `/api/mcp/projects/{project_id}/tools/{tool_name}/call`

The adapter is intentionally thin. It reuses `tool_service.py`, approval requests, project permissions, audit events, and redaction. It is not a separate ungoverned tool plane.

## Review Pointers

- Tool definitions: `apps/api/app/services/tool_service.py`
- Governance events: `apps/api/app/services/governance_service.py`
- Approval model: `apps/api/app/db/models/governance.py`
- MCP adapter: `apps/api/app/mcp/adapter.py`
- Tests: `apps/api/app/tests/test_tool_boundary.py`, `apps/api/app/tests/test_mcp_adapter.py`
