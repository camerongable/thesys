import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

KillSwitchName = Literal[
    "disable_all_agent_writes",
    "disable_external_mcp",
    "disable_external_egress",
    "disable_model_provider",
    "disable_memory_writes",
    "disable_source_fetching",
]


class KillSwitchUpdate(BaseModel):
    disable_all_agent_writes: bool | None = None
    disable_external_mcp: bool | None = None
    disable_external_egress: bool | None = None
    disable_model_provider: bool | None = None
    disable_memory_writes: bool | None = None
    disable_source_fetching: bool | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> "KillSwitchUpdate":
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one kill switch must be supplied.")
        return self


class KillSwitchStatusRead(BaseModel):
    name: KillSwitchName
    enabled: bool
    workspace_enabled: bool
    environment_enabled: bool


class WorkspaceKillSwitchStateRead(BaseModel):
    switches: list[KillSwitchStatusRead]
    updated_at: datetime | None = None
    updated_by: uuid.UUID | None = None
