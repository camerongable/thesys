import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.guide import GuideActionRead

ProjectNudgeSeverity = Literal["info", "warning", "action_required"]


class ProjectNudgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    severity: ProjectNudgeSeverity
    title: str
    message: str
    why_it_matters: str
    action: GuideActionRead
    dismissed: bool
    created_at: datetime


class ProjectNudgeListRead(BaseModel):
    nudges: list[ProjectNudgeRead]
