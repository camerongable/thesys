import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

WorkspaceRole = Literal["owner", "admin", "editor", "viewer"]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    created_at: datetime


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class MeRead(BaseModel):
    user: UserRead
    workspace: WorkspaceRead
    role: str


class WorkspaceMemberRoleUpdate(BaseModel):
    role: WorkspaceRole


class WorkspaceMemberRead(BaseModel):
    user_id: uuid.UUID
    role: WorkspaceRole
