from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.mcp_registry import (
    MCPServerRegistrationCreate,
    MCPServerRegistrationListRead,
    MCPServerRegistrationRead,
)
from app.services import mcp_registry_service

router = APIRouter(prefix="/api/mcp/servers", tags=["mcp-servers"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=MCPServerRegistrationListRead)
def list_mcp_servers(db: DbDep, auth: AuthContextDep) -> MCPServerRegistrationListRead:
    return MCPServerRegistrationListRead(
        registrations=[
            MCPServerRegistrationRead.model_validate(item)
            for item in mcp_registry_service.list_registrations(db, auth)
        ]
    )


@router.post("", response_model=MCPServerRegistrationRead, status_code=status.HTTP_201_CREATED)
def register_mcp_server(
    payload: MCPServerRegistrationCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> MCPServerRegistrationRead:
    return MCPServerRegistrationRead.model_validate(
        mcp_registry_service.register_server(db, auth, settings, payload)
    )
