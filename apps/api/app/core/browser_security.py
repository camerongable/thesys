"""Response headers for the browser-to-API trust boundary."""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_API_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
_LOCAL_DOCS_CONTENT_SECURITY_POLICY = (
    "default-src 'self' https://cdn.jsdelivr.net; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'; "
    "img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
)


class BrowserSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply browser protections without enabling cookie-based API sessions."""

    def __init__(self, app, *, environment: str) -> None:
        super().__init__(app)
        self.environment = environment

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = self._content_security_policy(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
        )
        response.headers["X-Frame-Options"] = "DENY"
        if self.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    def _content_security_policy(self, request: Request) -> str:
        if self.environment == "local" and request.url.path in {"/docs", "/redoc"}:
            return _LOCAL_DOCS_CONTENT_SECURITY_POLICY
        return _API_CONTENT_SECURITY_POLICY
