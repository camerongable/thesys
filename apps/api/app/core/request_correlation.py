"""HTTP middleware that establishes a safe request correlation identifier."""

from collections.abc import Awaitable, Callable

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core import telemetry
from app.core.request_context import reset_request_id, resolve_request_id, set_request_id


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Expose and retain one UUID correlation ID for each API request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = resolve_request_id(request.headers.get("X-Request-ID"))
        token = set_request_id(request_id)
        try:
            with telemetry.start_request_span(dict(request.headers)) as span:
                span.set_attribute("http.request.method", request.method)
                span.set_attribute("thesys.request_id", request_id)
                try:
                    response = await call_next(request)
                except Exception:
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                    raise
                route = request.scope.get("route")
                route_path = getattr(route, "path", None)
                if isinstance(route_path, str):
                    span.set_attribute("http.route", route_path)
                span.set_attribute("http.response.status_code", response.status_code)
                if response.status_code >= 500:
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                traceparent = telemetry.inject_trace_context()
        finally:
            reset_request_id(token)
        response.headers["X-Request-ID"] = request_id
        if traceparent:
            response.headers.setdefault("traceparent", traceparent)
        return response
