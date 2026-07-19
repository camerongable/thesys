"""Minimal, privacy-safe OpenTelemetry tracing for API and security operations."""

import logging
from threading import Lock

from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import Settings

logger = logging.getLogger(__name__)

_TRACER_NAME = "thesys.api"
_configured = False
_configure_lock = Lock()


def configure_telemetry(settings: Settings) -> None:
    """Configure OTLP export only when a trusted deployment endpoint is supplied."""
    global _configured

    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint:
        return

    with _configure_lock:
        if _configured:
            return

        provider = TracerProvider(
            resource=Resource.create({SERVICE_NAME: settings.otel_service_name})
        )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _configured = True
        logger.info("OpenTelemetry OTLP tracing enabled for service %s", settings.otel_service_name)


def start_request_span(headers: dict[str, str]):
    """Start a server span using only standard W3C trace context from the request."""
    parent_context = propagate.extract(headers)
    return trace.get_tracer(_TRACER_NAME).start_as_current_span(
        "http.server.request",
        context=parent_context,
        kind=trace.SpanKind.SERVER,
    )


def inject_trace_context() -> str | None:
    """Return the active W3C traceparent header without exposing other span data."""
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier.get("traceparent")


def record_security_event(event_type: str, source: str) -> None:
    """Attach bounded security metadata to the active trace, never event content."""
    span = trace.get_current_span()
    if not span.is_recording():
        return
    span.add_event(
        "thesys.security.event",
        attributes={
            "thesys.security.event_type": _bounded_attribute(event_type),
            "thesys.security.source": _bounded_attribute(source),
        },
    )


def _bounded_attribute(value: str) -> str:
    normalized = value.casefold().strip()
    if not normalized or len(normalized) > 100:
        return "unknown"
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_.-" for character in normalized):
        return "unknown"
    return normalized
