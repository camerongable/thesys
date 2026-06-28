"""Shared deterministic completion metadata for local fallback paths."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Any, Protocol

from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.core.config import Settings
from app.core.redaction import redact_payload, redact_text


class JSONDumpable(Protocol):
    def model_dump_json(self) -> str: ...


def fallback_completion(
    settings: Settings,
    messages: Sequence[ChatMessage],
    payload: JSONDumpable,
    fallback_name: str,
    error: BaseException | None = None,
    *,
    fallback_prefix: str | None = None,
    metadata: dict[str, Any] | None = None,
    use_stub_provider: bool = False,
) -> LLMCompletion:
    """Create an `LLMCompletion` for deterministic fallback payloads."""
    content = payload.model_dump_json()
    prompt_tokens = sum(len(message.content.split()) for message in messages)
    completion_tokens = len(content.split())
    provider_is_stub = use_stub_provider and settings.should_use_llm_stub
    model_provider = "stub" if provider_is_stub else "local-fallback"
    model_name = (
        f"deterministic-dev-stub:{settings.litellm_model}"
        if provider_is_stub
        else settings.litellm_model
    )
    fallback_key = _fallback_key(fallback_name, fallback_prefix=fallback_prefix)
    total_tokens = prompt_tokens + completion_tokens
    return LLMCompletion(
        content=content,
        model_provider=model_provider,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        total_cost=Decimal("0"),
        raw_response={
            "fallback": fallback_key,
            "fallback_reason": fallback_name,
            "provider_mode": "stub" if settings.should_use_llm_stub else "live",
            "model_provider": model_provider,
            "model_name": model_name,
            "error": _legacy_error(error),
            "provider_failure": provider_failure_metadata(error),
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "total_cost": "0",
            },
            "metadata": redact_payload(metadata or {}, redact_emails=True),
        },
        used_stub=True,
    )


def provider_failure_metadata(error: BaseException | None) -> dict[str, Any] | None:
    """Return redacted, typed provider-failure details for fallback completions."""
    if error is None:
        return None
    cause = _root_cause(error)
    return {
        "error_type": type(error).__name__,
        "message": _legacy_error(error),
        "is_timeout": _is_timeout_error(error),
        "cause_type": type(cause).__name__ if cause is not error else None,
        "cause_message": _legacy_error(cause) if cause is not error else None,
    }


def _fallback_key(fallback_name: str, *, fallback_prefix: str | None) -> str:
    return f"{fallback_prefix}_{fallback_name}" if fallback_prefix else fallback_name


def _legacy_error(error: BaseException | None) -> str | None:
    if error is None:
        return None
    return redact_text(str(error), redact_emails=True)[:500]


def _root_cause(error: BaseException) -> BaseException:
    current = error
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        next_error = current.__cause__ or current.__context__
        if next_error is None:
            return current
        current = next_error
    return current


def _is_timeout_error(error: BaseException) -> bool:
    for item in _exception_chain(error):
        name = type(item).__name__.casefold()
        message = str(item).casefold()
        if "timeout" in name or "timed out" in message or "timeout" in message:
            return True
    return False


def _exception_chain(error: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain
