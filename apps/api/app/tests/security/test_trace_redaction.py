import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import SecurityEvent
from app.services import ai_run_service, langsmith_observability_service
from app.services.data_protection_service import data_protection_service
from app.services.identity_service import ensure_dev_identity
from app.services.langsmith_observability_service import TraceContext, sanitize_for_observability


def test_trace_payloads_redact_pii_and_secrets() -> None:
    raw_text = (
        "Jane Doe at jane.doe@example.com uses +1 (415) 555-0123 with "
        "api_key=sk-secretvalue123 and card 4111 1111 1111 1111."
    )

    sanitized = sanitize_for_observability({"source_text": raw_text, "trace_label": "Evidence"})

    for raw_value in (
        "Jane Doe",
        "jane.doe@example.com",
        "415) 555-0123",
        "sk-secretvalue123",
        "4111 1111 1111 1111",
    ):
        assert raw_value not in sanitized["source_text"]
    assert "[REDACTED_SECRET]" in sanitized["source_text"]


def test_trace_payload_inspection_returns_only_bounded_redaction_metadata() -> None:
    inspection = data_protection_service.inspect_trace_payload(
        {
            "source_text": "Jane Doe at jane.doe@example.com uses api_key=sk-secretvalue123.",
            "safe_value": "retained",
        }
    )

    assert inspection.pii_entity_types == ("API_KEY", "EMAIL", "PERSON")
    assert inspection.redacted_value_count == 1
    assert "Jane Doe" not in str(inspection.value)
    assert "jane.doe@example.com" not in str(inspection.value)
    assert "sk-secretvalue123" not in str(inspection.value)


def test_trace_bound_pii_is_recorded_before_external_trace_upload(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    project = client.post("/api/projects", json={"name": "Trace PII monitoring"}).json()
    project_id = uuid.UUID(project["id"])
    auth = ensure_dev_identity(
        db_session,
        email="dev@thesys.local",
        display_name="Dev User",
    )
    run = ai_run_service.start_run(
        db_session,
        auth,
        workflow_type="trace_pii_test",
        prompt_version="v1",
        input_summary="Trace PII test.",
        project_id=project_id,
    )
    step = ai_run_service.start_step(db_session, run, step_name="trace_pii_test")
    raw_text = "Jane Doe at jane.doe@example.com uses api_key=sk-secretvalue123."

    def assert_detection_before_upload(_settings: Settings, **_kwargs: object) -> None:
        event = db_session.scalar(
            select(SecurityEvent).where(
                SecurityEvent.event_type == "pii_redaction_in_trace_payload"
            )
        )
        assert event is not None
        assert event.ai_run_id == run.id
        assert event.langsmith_trace_id == "trace-pii-test"
        assert event.attributes == {
            "trace_destination": "langsmith",
            "pii_entity_types": ["API_KEY", "EMAIL", "PERSON"],
            "redacted_value_count": 1,
        }
        assert raw_text not in event.summary
        assert raw_text not in str(event.attributes)

    monkeypatch.setattr(
        langsmith_observability_service,
        "_safe_create_run",
        assert_detection_before_upload,
    )
    langsmith_observability_service.record_step_span(
        db_session,
        Settings(),
        run=run,
        step=step,
        trace=TraceContext(
            trace_id="trace-pii-test",
            trace_url="https://langsmith.example.test/trace-pii-test",
            enabled=True,
            metadata={},
        ),
        span_name="trace_pii_test",
        input_json={"source_text": raw_text},
    )
