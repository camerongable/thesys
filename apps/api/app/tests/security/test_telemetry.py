from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.services import security_metrics_service

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


def test_request_correlation_emits_w3c_trace_context_and_bounded_span_attributes(client) -> None:
    _EXPORTER.clear()

    response = client.get(
        "/api/projects",
        headers={
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        },
    )

    assert response.status_code == 200
    assert response.headers["traceparent"].startswith("00-0af7651916cd43dd8448eb211c80319c-")
    span = _EXPORTER.get_finished_spans()[-1]
    assert span.name == "http.server.request"
    assert span.attributes["http.request.method"] == "GET"
    assert span.attributes["http.route"] == "/api/projects"
    assert span.attributes["http.response.status_code"] == 200
    assert "workspace_id" not in span.attributes
    assert "project_id" not in span.attributes


def test_security_metrics_emit_bounded_security_trace_event() -> None:
    _EXPORTER.clear()

    with trace.get_tracer("test").start_as_current_span("security-operation"):
        security_metrics_service.record_security_event("prompt_injection_detected", "guardrail")
        security_metrics_service.record_security_event("untrusted value", "bad source")

    span = _EXPORTER.get_finished_spans()[-1]
    assert [event.name for event in span.events] == [
        "thesys.security.event",
        "thesys.security.event",
    ]
    assert span.events[0].attributes == {
        "thesys.security.event_type": "prompt_injection_detected",
        "thesys.security.source": "guardrail",
    }
    assert span.events[1].attributes == {
        "thesys.security.event_type": "unknown",
        "thesys.security.source": "unknown",
    }
