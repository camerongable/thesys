"""HTTP routes exposing the governed MCP tool adapter."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.mcp import adapter
from app.schemas.mcp import (
    MCPJSONRPCRequest,
    MCPJSONRPCResponse,
    MCPToolCallCreate,
    MCPToolCallRead,
    MCPToolListRead,
)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/tools", response_model=MCPToolListRead)
def list_mcp_tools(include_proposals: bool = True) -> MCPToolListRead:
    """Return the MCP-shaped tool registry."""

    return MCPToolListRead(tools=adapter.list_tools(include_proposals=include_proposals))


@router.post("/rpc")
def mcp_jsonrpc(
    payload: MCPJSONRPCRequest,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> JSONResponse:
    """Handle non-project MCP JSON-RPC lifecycle and tool-list requests."""

    response = adapter.handle_jsonrpc(db, auth, settings, request=payload)
    return _jsonrpc_response(response, include_session_header=payload.method == "initialize")


@router.post("/projects/{project_id}/rpc")
def project_mcp_jsonrpc(
    project_id: uuid.UUID,
    payload: MCPJSONRPCRequest,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> JSONResponse:
    """Handle project-scoped MCP JSON-RPC requests, including governed tool calls."""

    response = adapter.handle_jsonrpc(
        db,
        auth,
        settings,
        request=payload,
        project_id=project_id,
    )
    return _jsonrpc_response(response, include_session_header=payload.method == "initialize")


@router.post("/projects/{project_id}/tools/{tool_name}/call", response_model=MCPToolCallRead)
def call_mcp_tool(
    project_id: uuid.UUID,
    tool_name: str,
    payload: MCPToolCallCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> MCPToolCallRead:
    """Invoke a governed MCP tool for one project."""

    try:
        return adapter.call_tool(
            db,
            auth,
            settings,
            project_id,
            tool_name=tool_name,
            arguments=payload.arguments,
            client_id=payload.client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _jsonrpc_response(
    response: MCPJSONRPCResponse,
    *,
    include_session_header: bool,
) -> JSONResponse:
    headers = {"MCP-Protocol-Version": adapter.MCP_PROTOCOL_VERSION}
    if include_session_header:
        headers["Mcp-Session-Id"] = str(uuid.uuid4())
    return JSONResponse(content=response.model_dump(mode="json", exclude_none=True), headers=headers)
