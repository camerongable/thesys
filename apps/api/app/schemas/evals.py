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
    expected_competitor_types: list[str]
    expected_risky_assumptions: list[str]
    required_output_sections: list[str]
    unacceptable_claims: list[str]
    expected_next_action_type: str
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
