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


class ResearchEvalCaseRead(BaseModel):
    id: str
    idea_type: str
    idea: str
    expected_outputs: list[str]
    unacceptable_failures: list[str]
    demo_ready: bool = False


class V1ResearchEvalMetricRead(BaseModel):
    key: str
    label: str
    passed: bool
    observed: int | bool | str | None = None
    expected: str


class V1ResearchEvalRead(BaseModel):
    project_id: uuid.UUID
    passed: bool
    score: int
    total: int
    metrics: list[V1ResearchEvalMetricRead]
    dataset_cases: list[ResearchEvalCaseRead]
    dataset_case_count: int
    demo_ready_case_count: int
