# MCP Integration

Thesys exposes its governed tool registry through project-scoped MCP JSON-RPC.
MCP clients do not bypass RBAC, approval gates, redaction, or audit logging.

## Lifecycle

```text
client initialize
-> capability negotiation
-> tools/list from governed registry
-> tools/call
-> schema and project-scope validation
-> RBAC and risk guard
-> read result or approval-required proposal
-> redacted audit event
-> approval route for state-changing proposals
```

Primary owners:

| Concern | Source |
|---|---|
| JSON-RPC adapter | `apps/api/app/mcp/adapter.py` |
| MCP protocol helpers | `apps/api/app/features/mcp/protocol.py` |
| MCP schemas | `apps/api/app/schemas/mcp.py` |
| Tool registry | `apps/api/app/features/governance_tools/registry.py` |
| Tool execution and approvals | `apps/api/app/services/tool_service.py` |
| Stdio bridge | `scripts/mcp_stdio_server.py` |
| HTTP routes | `apps/api/app/routers/mcp.py` |

## Endpoints

Project-scoped JSON-RPC:

```text
POST /api/mcp/projects/{project_id}/rpc
```

Global JSON-RPC for initialize/list:

```text
POST /api/mcp/rpc
```

Legacy HTTP-shaped compatibility routes remain:

```text
GET  /api/mcp/tools
POST /api/mcp/projects/{project_id}/tools/{tool_name}/call
```

## JSON-RPC Examples

Initialize:

```bash
curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"init","method":"initialize","params":{"protocolVersion":"2025-11-25"}}'
```

List read tools:

```bash
curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"list","method":"tools/list","params":{"includeProposals":false}}'
```

Call a read tool:

```bash
curl -X POST http://localhost:8000/api/mcp/projects/<project_id>/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"call","method":"tools/call","params":{"name":"get_project_summary","arguments":{},"_meta":{"client_id":"local-agent"}}}'
```

Approval-required proposal tools return structured content with proposal and
approval metadata instead of mutating state directly.

## Stdio Client Config

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

Use `--dev-role owner` only for local development against dev-auth mode.
Production-like auth should use the API auth headers documented in
`docs/DEPLOYMENT_SECURITY.md`.

## Error And Denial Behavior

The adapter returns structured JSON-RPC errors for:

- unknown methods
- invalid params
- missing project scope for `tools/call`
- missing required tool arguments
- RBAC or risk-policy denial
- stdio bridge HTTP forwarding failures

Request IDs are preserved. MCP-originated calls add MCP metadata to tool
invocations and audit events. Tool outputs and proposal summaries are redacted
before persistence.

## Verification

Automated contract tests:

```bash
cd apps/api && .venv/bin/pytest app/tests/test_mcp_adapter.py app/tests/test_tool_boundary.py app/tests/test_feature_package_boundaries.py -q
```

Live contract harness:

```bash
python3 scripts/eval_mcp_contract.py --project-id <project_id> --json
```

Sprint 60 should record exact output or an exact blocker for live read-tool,
proposal-tool, denied-write, invalid-param, and missing-scope smokes. If no
running API project exists, record that as the blocker under `G44-C`.

## Current Limits

- Stdio and HTTP/SSE client setup is local/developer oriented in V1.
- Live stdio read/proposal smoke requires a running API and seeded project.
- Advanced MCP settings should stay behind developer or integration settings,
  not in the homepage or primary workflow.
