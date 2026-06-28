import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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


class GuideEvalMetricRead(BaseModel):
    key: str
    label: str
    passed: bool
    observed: int | bool | str | None = None
    expected: str


class GuideEvalRead(BaseModel):
    project_id: uuid.UUID
    passed: bool
    score: int
    total: int
    metrics: list[GuideEvalMetricRead]


class ContextEvalMetricRead(BaseModel):
    key: str
    label: str
    passed: bool
    observed: int | bool | str | None = None
    expected: str


class ContextEvalRead(BaseModel):
    project_id: uuid.UUID
    passed: bool
    score: int
    total: int
    metrics: list[ContextEvalMetricRead]
    report: dict[str, object]


class AIEvalMetricRead(BaseModel):
    key: str
    label: str
    passed: bool
    observed: int | bool | str | None = None
    expected: str


class AIEvalRead(BaseModel):
    project_id: uuid.UUID
    passed: bool
    score: int
    total: int
    metrics: list[AIEvalMetricRead]
    report: dict[str, object]


class EvalGateMetricRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    label: str | None = None
    passed: bool | None = None
    observed: Any = None
    expected: Any = None
    warnings: list[str] | None = None


class EvalGateResultRead(BaseModel):
    name: str
    purpose: str
    status: Literal["pass", "fail", "warn"]
    passed: bool
    score: int
    total: int
    metrics: list[dict[str, Any]]
    command: list[str]
    returncode: int | None
    stdout_tail: str
    stderr_tail: str
    rerun: str


class EvalReportFailureRead(BaseModel):
    available: bool | None = None
    status: Literal["unavailable", "warning"]
    message: str


class EvalCacheDiagnosticRead(BaseModel):
    hits: int = 0
    misses: int = 0
    stale_denials: int = 0
    saved_tokens: int = 0
    saved_cost: str = "0"
    latency_saved_ms: int = 0


class EvalReportTokenCostRead(BaseModel):
    total_tokens: Any = None
    total_cost: Any = None


class EvalReportSummaryRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    available: bool
    passed: bool
    status: Literal["pass", "fail", "warn"]
    score: int
    total: int
    failed_check_ids: list[str]
    warning_gate_ids: list[str]
    gates: list[dict[str, Any]]
    reports: list[dict[str, Any]]
    cache: EvalCacheDiagnosticRead
    latency_ms: Any = None
    token_cost: EvalReportTokenCostRead
    trace_ids: list[str]
    changelog: str


class EvalExportResultRead(BaseModel):
    path: str
    uploaded: bool
    status: str
    message: str | None = None


class EvalReportRead(BaseModel):
    report: dict[str, Any]


class EvalTrendListRead(BaseModel):
    trends: list[dict[str, Any]]


class EvalMetricPointRead(BaseModel):
    name: str
    value: int | float
    unit: str
    attributes: dict[str, str]
    temporality: str


class EvalObservabilityMetricsRead(BaseModel):
    generated_at: str
    project_id: uuid.UUID
    metrics: list[EvalMetricPointRead]
