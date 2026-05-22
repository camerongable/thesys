import uuid

from pydantic import BaseModel


class MvpEvalCheckRead(BaseModel):
    key: str
    label: str
    passed: bool
    observed: int | bool | str | None = None
    expected: str


class MvpEvalRead(BaseModel):
    project_id: uuid.UUID
    passed: bool
    score: int
    total: int
    checks: list[MvpEvalCheckRead]
