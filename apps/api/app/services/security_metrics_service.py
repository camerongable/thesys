"""Low-cardinality Prometheus metrics for security operations."""

from decimal import Decimal
from math import isfinite

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

_REGISTRY = CollectorRegistry(auto_describe=True)

PROMPT_INJECTION_TOTAL = Counter(
    "ai_prompt_injection_total",
    "Prompt-injection attempts detected by security controls.",
    registry=_REGISTRY,
)
JAILBREAK_TOTAL = Counter(
    "ai_jailbreak_total",
    "Jailbreak attempts detected by security controls.",
    registry=_REGISTRY,
)
GUARDRAIL_BLOCK_TOTAL = Counter(
    "ai_guardrail_block_total",
    "Requests or outputs blocked by an AI guardrail.",
    registry=_REGISTRY,
)
TOOL_DENIED_TOTAL = Counter(
    "ai_tool_denied_total",
    "Governed tool invocations denied before execution.",
    registry=_REGISTRY,
)
TOOL_APPROVAL_TOTAL = Counter(
    "ai_tool_approval_total",
    "Governed tool invocations approved by a reviewer.",
    registry=_REGISTRY,
)
CROSS_TENANT_DENIAL_TOTAL = Counter(
    "ai_cross_tenant_denial_total",
    "Cross-tenant or cross-project access attempts denied by scope controls.",
    registry=_REGISTRY,
)
PII_REDACTION_TOTAL = Counter(
    "ai_pii_redaction_total",
    "PII redactions applied before an AI boundary.",
    registry=_REGISTRY,
)
MEMORY_QUARANTINE_TOTAL = Counter(
    "ai_memory_quarantine_total",
    "Memory or evidence items quarantined by security controls.",
    registry=_REGISTRY,
)
UNVERIFIED_CLAIM_TOTAL = Counter(
    "ai_unverified_claim_total",
    "Unverified claims surfaced by workflow controls.",
    registry=_REGISTRY,
)
COST_USD_TOTAL = Counter(
    "ai_cost_usd_total",
    "Reported provider cost in United States dollars.",
    registry=_REGISTRY,
)
TOKEN_TOTAL = Counter(
    "ai_token_total",
    "Reported provider token usage.",
    registry=_REGISTRY,
)
WORKFLOW_DURATION_SECONDS = Histogram(
    "ai_workflow_duration_seconds",
    "Elapsed wall-clock time for completed AI workflow runs.",
    buckets=(0.1, 1, 5, 30, 60, 300, 900, 1800, 3600, float("inf")),
    registry=_REGISTRY,
)
RETRIEVAL_SOURCE_COUNT = Histogram(
    "ai_retrieval_source_count",
    "Distinct evidence sources returned by a retrieval operation.",
    buckets=(0, 1, 2, 3, 5, 10, 20, 50, float("inf")),
    registry=_REGISTRY,
)
PROVIDER_ERROR_TOTAL = Counter(
    "ai_provider_error_total",
    "Provider request failures.",
    registry=_REGISTRY,
)
BUDGET_EXCEEDED_TOTAL = Counter(
    "ai_budget_exceeded_total",
    "Workflow budget exhaustion events.",
    registry=_REGISTRY,
)
LOOP_DETECTED_TOTAL = Counter(
    "ai_loop_detected_total",
    "Workflow loops detected and stopped by security controls.",
    registry=_REGISTRY,
)

_PROMPT_INJECTION_EVENTS = {"prompt_injection_detected"}
_JAILBREAK_EVENTS = {"jailbreak_detected"}
_LOOP_EVENT_SUFFIXES = ("_loop_detected", "_cycle_detected")
_LOOP_EVENTS = {
    "workflow_no_progress_detected",
    "workflow_repeated_memory_proposal_rejection_detected",
    "workflow_repeated_retrieval_query_detected",
    "workflow_repeated_source_fetch_failure_detected",
    "workflow_repeated_tool_invocation_detected",
}


def record_security_event(event_type: str, source: str) -> None:
    """Increment non-sensitive counters from one normalized security event."""
    if event_type in _PROMPT_INJECTION_EVENTS:
        PROMPT_INJECTION_TOTAL.inc()
    if event_type in _JAILBREAK_EVENTS:
        JAILBREAK_TOTAL.inc()
    if source == "guardrail":
        GUARDRAIL_BLOCK_TOTAL.inc()
    if event_type == "tool_invocation_denied":
        TOOL_DENIED_TOTAL.inc()
    if event_type == "tool_invocation_approved":
        TOOL_APPROVAL_TOTAL.inc()
    if event_type == "cross_tenant_access_attempt":
        CROSS_TENANT_DENIAL_TOTAL.inc()
    if "pii" in event_type and "redact" in event_type:
        PII_REDACTION_TOTAL.inc()
    if "quarantin" in event_type:
        MEMORY_QUARANTINE_TOTAL.inc()
    if "unverified_claim" in event_type:
        UNVERIFIED_CLAIM_TOTAL.inc()
    if event_type.endswith("_budget_exceeded"):
        BUDGET_EXCEEDED_TOTAL.inc()
    if event_type in _LOOP_EVENTS or event_type.endswith(_LOOP_EVENT_SUFFIXES):
        LOOP_DETECTED_TOTAL.inc()


def record_model_usage(*, total_tokens: int | None, total_cost: Decimal | None) -> None:
    """Record provider-reported cost and token totals when present."""
    if isinstance(total_tokens, int) and not isinstance(total_tokens, bool) and total_tokens >= 0:
        TOKEN_TOTAL.inc(total_tokens)
    if total_cost is not None and total_cost.is_finite() and total_cost >= 0:
        COST_USD_TOTAL.inc(float(total_cost))


def record_workflow_duration(duration_seconds: float) -> None:
    """Observe one terminal AI-run duration without workflow identity labels."""
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, (int, float)):
        return
    if not isfinite(duration_seconds) or duration_seconds < 0:
        return
    WORKFLOW_DURATION_SECONDS.observe(duration_seconds)


def record_retrieval_source_count(source_count: int) -> None:
    """Observe distinct returned sources without recording their identities."""
    if isinstance(source_count, bool) or not isinstance(source_count, int) or source_count < 0:
        return
    RETRIEVAL_SOURCE_COUNT.observe(source_count)


def record_unverified_claims(unverified_claim_count: int) -> None:
    """Count claims rejected or downgraded by citation verification."""
    if (
        isinstance(unverified_claim_count, bool)
        or not isinstance(unverified_claim_count, int)
        or unverified_claim_count < 1
    ):
        return
    UNVERIFIED_CLAIM_TOTAL.inc(unverified_claim_count)


def record_provider_error() -> None:
    """Record one provider transport or protocol failure."""
    PROVIDER_ERROR_TOTAL.inc()


def render_metrics() -> tuple[bytes, str]:
    """Render the isolated registry without tenant identifiers or content labels."""
    return generate_latest(_REGISTRY), CONTENT_TYPE_LATEST
