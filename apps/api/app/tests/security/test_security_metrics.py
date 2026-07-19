import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.db.models import AIRun
from app.services import ai_run_service, security_metrics_service


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
    security_metrics_service.record_security_event("pii_redaction_applied", "api")
    security_metrics_service.record_security_event("evidence_source_quarantined", "guardrail")
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
        _metric_value(before_text, "ai_guardrail_block_total") + 2
    )
    assert _metric_value(payload, "ai_tool_denied_total") == (
        _metric_value(before_text, "ai_tool_denied_total") + 1
    )
    assert _metric_value(payload, "ai_cross_tenant_denial_total") == (
        _metric_value(before_text, "ai_cross_tenant_denial_total") + 1
    )
    assert _metric_value(payload, "ai_pii_redaction_total") == (
        _metric_value(before_text, "ai_pii_redaction_total") + 1
    )
    assert _metric_value(payload, "ai_memory_quarantine_total") == (
        _metric_value(before_text, "ai_memory_quarantine_total") + 1
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


def test_security_metrics_observe_duration_and_retrieval_source_count() -> None:
    before, _ = security_metrics_service.render_metrics()
    before_text = before.decode("utf-8")

    security_metrics_service.record_workflow_duration(2.5)
    security_metrics_service.record_retrieval_source_count(3)
    security_metrics_service.record_unverified_claims(4)
    security_metrics_service.record_workflow_duration(float("inf"))
    security_metrics_service.record_retrieval_source_count(-1)
    security_metrics_service.record_unverified_claims(0)

    payload, _ = security_metrics_service.render_metrics()
    payload_text = payload.decode("utf-8")
    assert _metric_value(payload_text, "ai_workflow_duration_seconds_count") == (
        _metric_value(before_text, "ai_workflow_duration_seconds_count") + 1
    )
    assert _metric_value(payload_text, "ai_workflow_duration_seconds_sum") == (
        _metric_value(before_text, "ai_workflow_duration_seconds_sum") + 2.5
    )
    assert _metric_value(payload_text, "ai_retrieval_source_count_count") == (
        _metric_value(before_text, "ai_retrieval_source_count_count") + 1
    )
    assert _metric_value(payload_text, "ai_retrieval_source_count_sum") == (
        _metric_value(before_text, "ai_retrieval_source_count_sum") + 3
    )
    assert _metric_value(payload_text, "ai_unverified_claim_total") == (
        _metric_value(before_text, "ai_unverified_claim_total") + 4
    )


def test_terminal_ai_run_records_duration_once(monkeypatch) -> None:
    observed: list[float] = []
    monkeypatch.setattr(security_metrics_service, "record_workflow_duration", observed.append)
    run = AIRun(
        status="running",
        started_at=datetime.now(UTC) - timedelta(seconds=4),
    )
    db = Mock()

    ai_run_service.complete_run(
        db,
        run,
        output_summary="Completed.",
        total_tokens=3,
        total_cost=Decimal("0.01"),
        model_provider="deterministic",
        model_name="test",
    )
    ai_run_service.complete_run(
        db,
        run,
        output_summary="Completed again.",
        total_tokens=3,
        total_cost=Decimal("0.01"),
        model_provider="deterministic",
        model_name="test",
    )

    assert len(observed) == 1
    assert observed[0] >= 4
