"""Immutable per-workflow resource budget snapshots."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.config import Settings

WORKFLOW_BUDGET_EXHAUSTED_DETAIL = (
    "The workflow was stopped because it exceeded its safe execution budget. "
    "No external write was performed."
)


@dataclass(frozen=True)
class WorkflowSecurityBudget:
    max_model_calls: int
    max_tool_calls: int
    max_external_queries: int
    max_retrieved_chunks: int
    max_tokens: int
    max_cost_usd: Decimal
    max_duration_seconds: int
    max_memory_proposals: int
    max_structured_output_repairs: int
    max_critique_loops: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "WorkflowSecurityBudget":
        return cls(
            max_model_calls=settings.security_workflow_max_model_calls,
            max_tool_calls=settings.security_workflow_max_tool_calls,
            max_external_queries=settings.security_workflow_max_external_queries,
            max_retrieved_chunks=settings.security_workflow_max_retrieved_chunks,
            max_tokens=settings.ai_workflow_max_tokens,
            max_cost_usd=Decimal(str(settings.ai_workflow_max_cost_usd)),
            max_duration_seconds=settings.security_workflow_max_duration_seconds,
            max_memory_proposals=settings.security_workflow_max_memory_proposals,
            max_structured_output_repairs=settings.security_workflow_max_structured_output_repairs,
            max_critique_loops=settings.security_workflow_max_critique_loops,
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WorkflowSecurityBudget":
        try:
            return cls(
                max_model_calls=_positive_int(payload, "max_model_calls"),
                max_tool_calls=_positive_int(payload, "max_tool_calls"),
                max_external_queries=_positive_int(payload, "max_external_queries"),
                max_retrieved_chunks=_positive_int(payload, "max_retrieved_chunks"),
                max_tokens=_positive_int(payload, "max_tokens"),
                max_cost_usd=_nonnegative_decimal(payload, "max_cost_usd"),
                max_duration_seconds=_positive_int(payload, "max_duration_seconds"),
                max_memory_proposals=_positive_int(payload, "max_memory_proposals"),
                max_structured_output_repairs=_nonnegative_int(
                    payload,
                    "max_structured_output_repairs",
                ),
                max_critique_loops=_nonnegative_int(payload, "max_critique_loops"),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("Workflow security budget is invalid.") from exc

    def as_payload(self) -> dict[str, int | float]:
        return {
            "max_model_calls": self.max_model_calls,
            "max_tool_calls": self.max_tool_calls,
            "max_external_queries": self.max_external_queries,
            "max_retrieved_chunks": self.max_retrieved_chunks,
            "max_tokens": self.max_tokens,
            "max_cost_usd": float(self.max_cost_usd),
            "max_duration_seconds": self.max_duration_seconds,
            "max_memory_proposals": self.max_memory_proposals,
            "max_structured_output_repairs": self.max_structured_output_repairs,
            "max_critique_loops": self.max_critique_loops,
        }


def _positive_int(payload: dict[str, Any], field: str) -> int:
    raw_value = payload[field]
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError(field)
    value = raw_value
    if value < 1:
        raise ValueError(field)
    return value


def _nonnegative_int(payload: dict[str, Any], field: str) -> int:
    raw_value = payload[field]
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError(field)
    value = raw_value
    if value < 0:
        raise ValueError(field)
    return value


def _nonnegative_decimal(payload: dict[str, Any], field: str) -> Decimal:
    raw_value = payload[field]
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float, str)):
        raise ValueError(field)
    value = Decimal(str(raw_value))
    if not value.is_finite() or value < 0:
        raise ValueError(field)
    return value
