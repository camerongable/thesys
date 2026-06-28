from typing import Any, Literal

from pydantic import BaseModel, Field


class MCPToolRead(BaseModel):
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    access_mode: Literal["read", "write", "proposal"]
    risk_level: Literal["low", "medium", "high"]
    approval_policy: Literal["never_required", "required_for_write", "always_required"]


class MCPToolListRead(BaseModel):
    protocol: str = "mcp"
    adapter_version: str = "thesys-mcp-adapter:v1"
    tools: list[MCPToolRead] = Field(default_factory=list)


class MCPToolCallCreate(BaseModel):
    client_id: str = Field(default="local-codex", min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)


class MCPToolCallRead(BaseModel):
    tool_name: str
    access_mode: Literal["read", "write", "proposal"]
    risk_level: Literal["low", "medium", "high"]
    status: str
    invocation_id: str
    approval_required: bool
    approval_request_id: str | None = None
    duration_ms: int
    output: dict[str, Any]
    trace: dict[str, Any]
