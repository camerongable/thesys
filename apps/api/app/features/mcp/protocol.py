"""Pure MCP protocol serialization helpers."""

import json
from typing import Any

from app.db.models import ToolInvocation
from app.schemas.mcp import (
    MCPJSONRPCError,
    MCPJSONRPCResponse,
    MCPToolCallRead,
    MCPToolRead,
)

ADAPTER_VERSION = "thesys-mcp-adapter:v1"
MCP_PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "thesys", "version": ADAPTER_VERSION}
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_AUTHORIZATION_ERROR = -32001


def initialize_result(params: dict[str, Any]) -> dict[str, Any]:
    client_protocol = params.get("protocolVersion")
    protocol_version = (
        client_protocol if client_protocol == MCP_PROTOCOL_VERSION else MCP_PROTOCOL_VERSION
    )
    return {
        "protocolVersion": protocol_version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": SERVER_INFO,
        "instructions": (
            "Thesys MCP tools are project-scoped and governed by the same RBAC, "
            "approval, audit, and redaction policies as the web app."
        ),
    }


def jsonrpc_tool_schema(tool: MCPToolRead) -> dict[str, Any]:
    return {
        "name": tool.name,
        "title": tool.title,
        "description": tool.description,
        "inputSchema": tool.input_schema,
        "outputSchema": tool.output_schema,
        "annotations": {
            "accessMode": tool.access_mode,
            "riskLevel": tool.risk_level,
            "approvalPolicy": tool.approval_policy,
            "manifestVersion": tool.version,
            "requiredScopes": tool.required_scopes,
            "allowedDataClassifications": tool.allowed_data_classifications,
            "allowedNetworkDestinations": tool.allowed_network_destinations,
            "timeoutSeconds": tool.timeout_seconds,
            "maxOutputBytes": tool.max_output_bytes,
            "maxAffectedRecords": tool.max_affected_records,
            "reversible": tool.reversible,
            "owner": tool.owner,
            "adapterVersion": ADAPTER_VERSION,
        },
    }


def client_id_from_tool_call_params(params: dict[str, Any]) -> str:
    metadata = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
    return str(
        metadata.get("client_id")
        or metadata.get("clientId")
        or params.get("client_id")
        or "mcp-jsonrpc-client"
    )


def tool_arguments_from_params(params: dict[str, Any]) -> dict[str, Any]:
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("tools/call params.arguments must be an object.")
    return arguments


def jsonrpc_tool_call_result(call: MCPToolCallRead) -> dict[str, Any]:
    structured = call.model_dump(mode="json")
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(call.output, default=str, sort_keys=True),
            }
        ],
        "structuredContent": structured,
        "isError": False,
    }


def rpc_result(request_id: str | int | None, result: dict[str, Any]) -> MCPJSONRPCResponse:
    return MCPJSONRPCResponse(id=request_id, result=result)


def rpc_error(
    request_id: str | int | None,
    code: int,
    message: str,
    *,
    data: dict[str, Any] | None = None,
) -> MCPJSONRPCResponse:
    return MCPJSONRPCResponse(
        id=request_id,
        error=MCPJSONRPCError(code=code, message=message, data=data),
    )


def mcp_invocation_metadata(client_id: str, duration_ms: int) -> dict[str, Any]:
    return {
        "client_id": client_id,
        "adapter_version": ADAPTER_VERSION,
        "duration_ms": duration_ms,
    }


def mcp_tool_input_payload(
    tool_input: dict[str, Any] | None,
    mcp_metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "tool_input": tool_input or {},
        "mcp": mcp_metadata,
    }


def mcp_audit_metadata(tool_name: str, mcp_metadata: dict[str, Any]) -> dict[str, Any]:
    return {"tool_name": tool_name, **mcp_metadata}


def mcp_audit_summary(tool_name: str) -> str:
    return f"MCP client invoked {tool_name}."


def tool_call_read(
    invocation: ToolInvocation,
    *,
    duration_ms: int,
    approval_request_id: str | None,
    output: dict[str, Any],
) -> MCPToolCallRead:
    return MCPToolCallRead(
        tool_name=invocation.tool_name,
        access_mode=invocation.access_mode,  # type: ignore[arg-type]
        risk_level=invocation.risk_level,  # type: ignore[arg-type]
        status=invocation.status,
        invocation_id=str(invocation.id),
        approval_required=invocation.access_mode == "proposal",
        approval_request_id=approval_request_id,
        duration_ms=duration_ms,
        output=output,
        trace={
            "tool_invocation_id": str(invocation.id),
            "requested_by": invocation.requested_by,
            "mcp_adapter_version": ADAPTER_VERSION,
        },
    )
