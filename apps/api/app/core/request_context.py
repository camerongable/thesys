"""Request-scoped correlation identifiers for API audit records."""

import uuid
from contextvars import ContextVar, Token

_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """Return the current API request correlation identifier, when available."""
    return _request_id_context.get()


def reset_request_id(token: Token[str | None]) -> None:
    """Clear a request correlation identifier after response handling completes."""
    _request_id_context.reset(token)


def set_request_id(request_id: str) -> Token[str | None]:
    """Bind a trusted request correlation identifier to the current execution context."""
    return _request_id_context.set(request_id)


def resolve_request_id(value: str | None) -> str:
    """Accept canonical UUID request IDs and replace all other client-provided values."""
    if value:
        try:
            return str(uuid.UUID(value))
        except ValueError:
            pass
    return str(uuid.uuid4())
