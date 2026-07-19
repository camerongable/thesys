import re
from decimal import Decimal

from fastapi.testclient import TestClient

from app.services import security_metrics_service


def _metric_value(payload: str, name: str) -> float:
    match = re.search(rf"^{re.escape(name)} ([0-9.e+-]+)$", payload, flags=re.MULTILINE)
    assert match is not None, f"Metric {name} was not exposed."
    return float(match.group(1))


def test_prometheus_metrics_endpoint_exposes_low_cardinality_security_counters(
    client: TestClient,
) -> None:
    before, _ = security_metrics_service.render_metrics()
    before_text = before.decode("utf-8")

    security_metrics_service.record_security_event("prompt_injection_detected", "guardrail")
    security_metrics_service.record_security_event("tool_invocation_denied", "tool")
    security_metrics_service.record_security_event("cross_tenant_access_attempt", "api")
    security_metrics_service.record_security_event("workflow_token_budget_exceeded", "workflow")
    security_metrics_service.record_security_event(
        "workflow_repeated_tool_invocation_detected",
        "workflow",
    )
    security_metrics_service.record_model_usage(
        total_tokens=17,
        total_cost=Decimal("0.125"),
    )
    security_metrics_service.record_provider_error()

    response = client.get("/api/security/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    payload = response.text
    assert "workspace_id" not in payload
    assert "project_id" not in payload
    assert _metric_value(payload, "ai_prompt_injection_total") == (
        _metric_value(before_text, "ai_prompt_injection_total") + 1
    )
    assert _metric_value(payload, "ai_guardrail_block_total") == (
        _metric_value(before_text, "ai_guardrail_block_total") + 1
    )
    assert _metric_value(payload, "ai_tool_denied_total") == (
        _metric_value(before_text, "ai_tool_denied_total") + 1
    )
    assert _metric_value(payload, "ai_cross_tenant_denial_total") == (
        _metric_value(before_text, "ai_cross_tenant_denial_total") + 1
    )
    assert _metric_value(payload, "ai_budget_exceeded_total") == (
        _metric_value(before_text, "ai_budget_exceeded_total") + 1
    )
    assert _metric_value(payload, "ai_loop_detected_total") == (
        _metric_value(before_text, "ai_loop_detected_total") + 1
    )
    assert (
        _metric_value(payload, "ai_token_total")
        == _metric_value(before_text, "ai_token_total") + 17
    )
    assert (
        _metric_value(payload, "ai_cost_usd_total")
        == _metric_value(before_text, "ai_cost_usd_total") + 0.125
    )
    assert _metric_value(payload, "ai_provider_error_total") == (
        _metric_value(before_text, "ai_provider_error_total") + 1
    )
