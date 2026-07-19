"""Top-level eval quality report summary shaping."""

from typing import Any

from app.schemas.evals import EvalCacheDiagnosticRead, EvalReportSummaryRead

CACHE_METRIC_NAMES = {
    "thesys.ai.cache.hits": "hits",
    "thesys.ai.cache.misses": "misses",
    "thesys.ai.cache.stale_denials": "stale_denials",
    "thesys.ai.cache.saved_tokens": "saved_tokens",
    "thesys.ai.cache.saved_cost": "saved_cost",
    "thesys.ai.cache.latency_saved": "latency_saved_ms",
}


def summary(
    metadata: dict[str, Any],
    gates: list[dict[str, Any]],
    *,
    live_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the aggregate local quality-gate summary."""

    failed = [gate for gate in gates if gate["status"] == "fail"]
    warnings = [gate for gate in gates if gate["status"] == "warn"]
    score = sum(int(gate.get("score") or 0) for gate in gates)
    total = sum(int(gate.get("total") or 0) for gate in gates)
    failed_check_ids = failed_gate_or_metric_ids(gates)
    live_ai_report = as_dict(live_snapshot.get("ai_report")) if live_snapshot else {}
    cache_snapshot = cache_from_live_snapshot(live_snapshot)
    payload = {
        **metadata,
        "available": True,
        "passed": not failed,
        "status": "pass" if not failed and not warnings else ("fail" if failed else "warn"),
        "score": score,
        "total": total,
        "failed_check_ids": failed_check_ids,
        "warning_gate_ids": [gate["name"] for gate in warnings],
        "gates": gates,
        "reports": gates,
        "cache": cache_snapshot,
        "latency_ms": live_ai_report.get("average_step_latency_ms"),
        "token_cost": {
            "total_tokens": live_ai_report.get("total_tokens"),
            "total_cost": live_ai_report.get("total_cost"),
        },
        "trace_ids": live_snapshot.get("trace_ids", []) if live_snapshot else [],
        "changelog": "docs/AI_CHANGELOG.md",
    }
    return EvalReportSummaryRead.model_validate(payload).model_dump()


def cache_from_live_snapshot(live_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Extract cache metrics from a live observability snapshot."""

    cache = {
        "hits": 0,
        "misses": 0,
        "stale_denials": 0,
        "saved_tokens": 0,
        "saved_cost": "0",
        "latency_saved_ms": 0,
    }
    if not live_snapshot:
        return EvalCacheDiagnosticRead.model_validate(cache).model_dump()
    observability = as_dict(live_snapshot.get("observability"))
    metrics = observability.get("metrics", [])
    if not isinstance(metrics, list):
        return EvalCacheDiagnosticRead.model_validate(cache).model_dump()
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        target = CACHE_METRIC_NAMES.get(str(metric.get("name")))
        if not target:
            continue
        value = metric.get("value", 0)
        cache[target] = str(value) if target == "saved_cost" else int(float(value or 0))
    return EvalCacheDiagnosticRead.model_validate(cache).model_dump()


def failed_gate_or_metric_ids(gates: list[dict[str, Any]]) -> list[str]:
    """Return metric IDs for failures, falling back to gate IDs when needed."""

    failed_ids: list[str] = []
    for gate in gates:
        gate_name = str(gate.get("name") or "unknown_gate")
        metrics = gate.get("metrics", [])
        metric_failures = [
            str(metric.get("key") or gate_name)
            for metric in metrics
            if isinstance(metric, dict) and not bool(metric.get("passed", False))
        ]
        if metric_failures:
            failed_ids.extend(metric_failures)
        elif gate.get("status") == "fail" or gate.get("passed") is False:
            failed_ids.append(gate_name)
    return failed_ids


def as_dict(value: Any) -> dict[str, Any]:
    """Return dictionaries unchanged and coerce all other values to empty dicts."""

    return value if isinstance(value, dict) else {}
