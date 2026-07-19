import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.mcp_registry import (
    MCPServerCredentialConfigure,
    MCPServerCredentialRead,
    MCPServerRegistrationCreate,
    MCPServerRegistrationListRead,
    MCPServerRegistrationRead,
)
from app.services import mcp_credential_service, mcp_registry_service

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


@router.post("/{registration_id}/enable", response_model=MCPServerRegistrationRead)
def enable_mcp_server(
    registration_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> MCPServerRegistrationRead:
    return MCPServerRegistrationRead.model_validate(
        mcp_registry_service.enable_server(db, auth, settings, registration_id)
    )


@router.put("/{registration_id}/credentials", response_model=MCPServerCredentialRead)
def configure_mcp_server_credential(
    registration_id: uuid.UUID,
    payload: MCPServerCredentialConfigure,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> MCPServerCredentialRead:
    return MCPServerCredentialRead.model_validate(
        mcp_credential_service.configure_credential(db, auth, settings, registration_id, payload)
    )


@router.get("/{registration_id}/credentials", response_model=MCPServerCredentialRead)
def get_mcp_server_credential(
    registration_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> MCPServerCredentialRead:
    return MCPServerCredentialRead.model_validate(
        mcp_credential_service.get_credential_metadata(db, auth, registration_id)
    )


@router.delete("/{registration_id}/credentials", status_code=status.HTTP_204_NO_CONTENT)
def revoke_mcp_server_credential(
    registration_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> Response:
    mcp_credential_service.revoke_credential(db, auth, registration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
