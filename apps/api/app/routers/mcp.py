import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.mcp import adapter
from app.schemas.mcp import MCPToolCallCreate, MCPToolCallRead, MCPToolListRead

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/tools", response_model=MCPToolListRead)
def list_mcp_tools(include_proposals: bool = True) -> MCPToolListRead:
    return MCPToolListRead(tools=adapter.list_tools(include_proposals=include_proposals))


@router.post("/projects/{project_id}/tools/{tool_name}/call", response_model=MCPToolCallRead)
def call_mcp_tool(
    project_id: uuid.UUID,
    tool_name: str,
    payload: MCPToolCallCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> MCPToolCallRead:
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
