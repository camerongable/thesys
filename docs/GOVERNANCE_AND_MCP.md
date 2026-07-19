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

## MCP JSON-RPC Adapter

`app/mcp/adapter.py` exposes the existing governed tools through MCP JSON-RPC:

- `/api/mcp/rpc` for `initialize` and `tools/list`
- `/api/mcp/projects/{project_id}/rpc` for project-scoped `initialize`, `tools/list`, and `tools/call`

The JSON-RPC endpoint supports:

- `initialize` with protocol/capability negotiation
- `tools/list` generated from the internal tool registry
- `tools/call` mapped to governed read/proposal tool execution
- structured JSON-RPC errors for unknown methods, invalid params, and denied calls
- request ID preservation

Legacy compatibility routes are still available:

- `/api/mcp/tools`
- `/api/mcp/projects/{project_id}/tools/{tool_name}/call`

The adapter is intentionally thin. It reuses `tool_service.py`, approval requests, project permissions, audit events, and redaction. It is not a separate ungoverned tool plane.

## Local Client Examples

Project-scoped streamable HTTP JSON-RPC:

```bash
curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"init","method":"initialize","params":{"protocolVersion":"2025-11-25"}}'

curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"list","method":"tools/list","params":{"includeProposals":false}}'

curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"call","method":"tools/call","params":{"name":"get_project_summary","arguments":{},"_meta":{"client_id":"local-agent"}}}'
```

Stdio bridge for local IDE/developer-agent configs:

```json
{
  "mcpServers": {
    "thesys-local": {
      "command": "python3",
      "args": [
        "scripts/mcp_stdio_server.py",
        "--api-base",
        "http://localhost:8000",
        "--project-id",
        "<project_id>"
      ]
    }
  }
}
```

Use `scripts/eval_mcp_contract.py --project-id <project_id> --json` to run a live initialize/list/read/proposal contract check.

## Review Pointers

- Tool definitions: `apps/api/app/services/tool_service.py`
- Governance events: `apps/api/app/services/governance_service.py`
- Approval model: `apps/api/app/db/models/governance.py`
- MCP adapter: `apps/api/app/mcp/adapter.py`
- Tests: `apps/api/app/tests/test_tool_boundary.py`, `apps/api/app/tests/test_mcp_adapter.py`
