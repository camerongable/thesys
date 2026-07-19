import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class MCPServerRegistrationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: HttpUrl
    transport: Literal["streamable_http", "sse"]
    server_fingerprint: str = Field(min_length=64, max_length=64)
    approved_version: str = Field(min_length=1, max_length=120)
    allowed_tools: list[str] = Field(default_factory=list, max_length=100)
    oauth_issuer: HttpUrl | None = None


class MCPServerRegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_url: str
    transport: str
    server_fingerprint: str
    approved_version: str
    allowed_tools: list[str]
    tool_schema_snapshot: dict[str, object]
    oauth_issuer: str | None
    enabled: bool
    reviewed_at: datetime
    reviewed_by: uuid.UUID


class MCPServerRegistrationListRead(BaseModel):
    registrations: list[MCPServerRegistrationRead]
