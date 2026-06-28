"""MCP-shaped adapter over Thesys governed tool calls.

The adapter exposes the same read/proposal tools used by agents and the UI.
It does not bypass authorization, approvals, audit logging, or redaction; MCP
clients get a standard integration surface while policy stays centralized.
"""

import uuid
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.core.redaction import redact_payload
from app.db.models import ApprovalRequest, ToolInvocation
from app.schemas.mcp import MCPJSONRPCError, MCPJSONRPCRequest, MCPJSONRPCResponse, MCPToolCallRead, MCPToolRead
from app.services import governance_service, project_service, tool_service

ADAPTER_VERSION = "thesys-mcp-adapter:v1"
MCP_PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "thesys", "version": ADAPTER_VERSION}
READ_TOOL_LIMIT = 100
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_AUTHORIZATION_ERROR = -32001


@dataclass(frozen=True)
class MCPCallContext:
    """Minimal metadata captured for one MCP tool call."""

    client_id: str
    duration_ms: int


def list_tools(*, include_proposals: bool = True) -> list[MCPToolRead]:
    """Expose governed app tools in an MCP-shaped schema without bypassing policy."""
    definitions = tool_service.list_tool_definitions()
    if not include_proposals:
        definitions = [definition for definition in definitions if definition.access_mode == "read"]
    return [
        MCPToolRead(
            name=definition.name,
            title=definition.title,
            description=definition.description,
            input_schema=definition.input_schema,
            output_schema=definition.output_schema,
            access_mode=definition.access_mode,
            risk_level=definition.risk_level,
            approval_policy=definition.approval_policy,
        )
        for definition in definitions[:READ_TOOL_LIMIT]
    ]


def handle_jsonrpc(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    request: MCPJSONRPCRequest,
    project_id: uuid.UUID | None = None,
) -> MCPJSONRPCResponse:
    """Handle one MCP JSON-RPC request with structured protocol errors."""

    try:
        if request.method == "initialize":
            return _rpc_result(request.id, _initialize_result(request.params))
        if request.method == "notifications/initialized":
            return _rpc_result(request.id, {"accepted": True})
        if request.method == "tools/list":
            include_proposals = bool(request.params.get("includeProposals", True))
            return _rpc_result(
                request.id,
                {
                    "tools": [
                        _jsonrpc_tool_schema(tool)
                        for tool in list_tools(include_proposals=include_proposals)
                    ]
                },
            )
        if request.method == "tools/call":
            if project_id is None:
                return _rpc_error(
                    request.id,
                    JSONRPC_INVALID_PARAMS,
                    "tools/call requires a project-scoped MCP endpoint.",
                )
            return _rpc_result(
                request.id,
                _call_tool_result(db, auth, settings, project_id, request.params),
            )
        return _rpc_error(
            request.id,
            JSONRPC_METHOD_NOT_FOUND,
            f"Unsupported MCP method: {request.method}",
        )
    except ValueError as exc:
        return _rpc_error(request.id, JSONRPC_INVALID_PARAMS, str(exc))
    except HTTPException as exc:
        return _rpc_error(
            request.id,
            JSONRPC_AUTHORIZATION_ERROR if exc.status_code in {401, 403} else JSONRPC_INVALID_PARAMS,
            str(exc.detail),
            data={"status_code": exc.status_code},
        )
    except Exception as exc:
        return _rpc_error(request.id, JSONRPC_INTERNAL_ERROR, "MCP request failed.", data={"error": str(exc)})


def call_tool(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    *,
    tool_name: str,
    arguments: dict[str, Any],
    client_id: str,
) -> MCPToolCallRead:
    """Invoke a governed tool for an MCP client, preserving approvals and audit logs."""
    project_service.get_project(db, auth, project_id)
    definition = _definition(tool_name)
    started = perf_counter()
    if definition.access_mode == "proposal":
        invocation = tool_service.create_proposal(
            db,
            auth,
            project_id,
            tool_name,
            arguments,
            requested_by="agent",
            input_json={"mcp": {"client_id": client_id, "adapter_version": ADAPTER_VERSION}},
        )
        duration_ms = int((perf_counter() - started) * 1000)
        _attach_mcp_metadata(db, auth, project_id, invocation, client_id, duration_ms)
        approval = _approval_for_invocation(db, invocation)
        output = invocation.output_json or {}
        return _read(
            invocation,
            duration_ms=duration_ms,
            approval_request_id=str(approval.id) if approval else None,
            output=output,
        )

    result = tool_service.execute_tool(
        db,
        auth,
        settings,
        project_id,
        tool_name,
        arguments,
        requested_by="agent",
    )
    duration_ms = int((perf_counter() - started) * 1000)
    _attach_mcp_metadata(db, auth, project_id, result.invocation, client_id, duration_ms)
    return _read(
        result.invocation,
        duration_ms=duration_ms,
        approval_request_id=None,
        output=result.output,
    )


def _initialize_result(params: dict[str, Any]) -> dict[str, Any]:
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


def _jsonrpc_tool_schema(tool: MCPToolRead) -> dict[str, Any]:
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
            "adapterVersion": ADAPTER_VERSION,
        },
    }


def _call_tool_result(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    params: dict[str, Any],
) -> dict[str, Any]:
    tool_name = str(params.get("name") or "")
    if not tool_name:
        raise ValueError("tools/call params.name is required.")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("tools/call params.arguments must be an object.")
    metadata = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
    client_id = str(
        metadata.get("client_id")
        or metadata.get("clientId")
        or params.get("client_id")
        or "mcp-jsonrpc-client"
    )
    call = call_tool(
        db,
        auth,
        settings,
        project_id,
        tool_name=tool_name,
        arguments=arguments,
        client_id=client_id,
    )
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


def _rpc_result(request_id: str | int | None, result: dict[str, Any]) -> MCPJSONRPCResponse:
    return MCPJSONRPCResponse(id=request_id, result=result)


def _rpc_error(
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


def _attach_mcp_metadata(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    invocation: ToolInvocation,
    client_id: str,
    duration_ms: int,
) -> None:
    """Annotate the tool invocation and audit log with MCP client metadata."""

    mcp_metadata = {
        "client_id": client_id,
        "adapter_version": ADAPTER_VERSION,
        "duration_ms": duration_ms,
    }
    invocation.input_json = redact_payload(
        {
            "tool_input": invocation.input_json or {},
            "mcp": mcp_metadata,
        },
        redact_emails=True,
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="mcp_tool_invocation",
        actor_type="agent",
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        risk_level=invocation.risk_level,
        summary=f"MCP client invoked {invocation.tool_name}.",
        metadata={"tool_name": invocation.tool_name, **mcp_metadata},
    )
    db.commit()
    db.refresh(invocation)


def _read(
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


def _approval_for_invocation(db: Session, invocation: ToolInvocation) -> ApprovalRequest | None:
    return db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.entity_type == "tool_invocation",
            ApprovalRequest.entity_id == invocation.id,
            ApprovalRequest.status == "pending",
        )
    )


def _definition(tool_name: str):
    for definition in tool_service.list_tool_definitions():
        if definition.name == tool_name:
            return definition
    raise ValueError(f"Unsupported MCP tool: {tool_name}")
