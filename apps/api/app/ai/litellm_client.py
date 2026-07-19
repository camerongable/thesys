"""Small OpenAI-compatible LiteLLM client used by service-layer AI workflows."""

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.security.guardrails import GuardrailBlockedError, GuardrailGateway
from app.security.secrets import SecretName, SecretProviderError, resolve_secret
from app.services import (
    model_data_policy_service,
    security_metrics_service,
)
from app.services.data_protection_service import data_protection_service
from app.services.security_policy_service import (
    ProviderEgressDeniedError,
    enforce_provider_egress_policy,
)
from app.services.workflow_budget_service import (
    ModelCallRateContext,
    record_model_output_secret,
    record_model_usage,
    record_provider_failure,
    record_provider_prompt_pii,
    reserve_model_call,
)

ChatRole = Literal["system", "user", "assistant"]
_STREAM_OUTPUT_HOLDBACK_CHARS = 256


class ChatMessage(BaseModel):
    """Minimal chat-completions message schema used by internal prompts."""

    role: ChatRole
    content: str = Field(min_length=1)


@dataclass(frozen=True)
class LLMCompletion:
    """Normalized completion payload with provider usage and cost metadata."""

    content: str
    model_provider: str
    model_name: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    total_cost: Decimal | None
    raw_response: dict[str, Any]
    used_stub: bool


class LiteLLMClientError(RuntimeError):
    pass


class LiteLLMClient:
    """HTTP client for LiteLLM's OpenAI-compatible chat completions endpoint."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        response_format_json: bool = False,
        max_tokens: int | None = None,
    ) -> LLMCompletion:
        """Call chat completions and normalize the response for observability."""
        payload: dict[str, Any] = {
            "model": model or self.settings.litellm_model,
            "temperature": temperature,
        }
        gateway = GuardrailGateway(self.settings)
        decision = self._prepare_payload(
            gateway,
            model=str(payload["model"]),
            messages=messages,
        )
        record_provider_prompt_pii(
            pii_entity_types=decision.pii_entity_types,
            redacted_message_count=decision.redacted_message_count,
        )
        payload["messages"] = decision.messages
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = f"{self.settings.litellm_base_url.rstrip('/')}/v1/chat/completions"
        self._enforce_egress(url)
        reserve_model_call()
        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.settings.litellm_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            security_metrics_service.record_provider_error()
            record_provider_failure(
                failure_kind="http_status",
                status_code=exc.response.status_code,
            )
            raise LiteLLMClientError(
                f"LiteLLM request failed with status {exc.response.status_code}."
            ) from None
        except httpx.HTTPError:
            security_metrics_service.record_provider_error()
            record_provider_failure(failure_kind="transport")
            raise LiteLLMClientError("LiteLLM request failed.") from None

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LiteLLMClientError(
                "LiteLLM response did not match chat completions format."
            ) from exc
        usage = body.get("usage") or {}
        total_cost = _parse_cost_header(response.headers.get("x-litellm-response-cost"))
        record_model_usage(
            total_tokens=usage.get("total_tokens"),
            total_cost=total_cost,
        )
        security_metrics_service.record_model_usage(
            total_tokens=usage.get("total_tokens"),
            total_cost=total_cost,
        )
        try:
            safe_output = self._safe_model_output(gateway, str(content))
        except GuardrailBlockedError as exc:
            raise LiteLLMClientError("LiteLLM output blocked by guardrail.") from exc

        return LLMCompletion(
            content=safe_output.text,
            model_provider="litellm",
            model_name=str(body.get("model") or payload["model"]),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            total_cost=total_cost,
            raw_response=_redacted_response_body(body),
            used_stub=False,
        )

    def stream_complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        response_format_json: bool = False,
        max_tokens: int | None = None,
        model_call_rate_context: ModelCallRateContext | None = None,
    ) -> Iterator[str]:
        """Yield OpenAI-compatible streaming content deltas from LiteLLM."""
        payload: dict[str, Any] = {
            "model": model or self.settings.litellm_model,
            "temperature": temperature,
            "stream": True,
        }
        gateway = GuardrailGateway(self.settings)
        decision = self._prepare_payload(
            gateway,
            model=str(payload["model"]),
            messages=messages,
        )
        record_provider_prompt_pii(
            pii_entity_types=decision.pii_entity_types,
            redacted_message_count=decision.redacted_message_count,
        )
        payload["messages"] = decision.messages
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = f"{self.settings.litellm_base_url.rstrip('/')}/v1/chat/completions"
        self._enforce_egress(url)
        reserve_model_call(model_call_rate_context)
        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.settings.litellm_timeout_seconds) as client:
                with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    output_secret_reported = False
                    pending_output = ""
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload_text = line.removeprefix("data:").strip()
                        if payload_text == "[DONE]":
                            break
                        try:
                            body = json.loads(payload_text)
                            delta = body["choices"][0].get("delta", {}).get("content")
                        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                            continue
                        if delta:
                            pending_output += str(delta)
                            if len(pending_output) <= _STREAM_OUTPUT_HOLDBACK_CHARS:
                                continue
                            try:
                                secret_entity_types = (
                                    data_protection_service.detect_secret_entity_types(
                                        pending_output
                                    )
                                )
                                if secret_entity_types:
                                    safe_delta, output_secret_reported = self._safe_stream_delta(
                                        gateway,
                                        pending_output,
                                        output_secret_reported=output_secret_reported,
                                    )
                                    pending_output = ""
                                    yield safe_delta
                                    continue
                                flush_output = pending_output[:-_STREAM_OUTPUT_HOLDBACK_CHARS]
                                pending_output = pending_output[-_STREAM_OUTPUT_HOLDBACK_CHARS:]
                                safe_delta, output_secret_reported = self._safe_stream_delta(
                                    gateway,
                                    flush_output,
                                    output_secret_reported=output_secret_reported,
                                )
                                yield safe_delta
                            except GuardrailBlockedError as exc:
                                raise LiteLLMClientError(
                                    "LiteLLM stream output blocked by guardrail."
                                ) from exc
                    if pending_output:
                        try:
                            safe_delta, _ = self._safe_stream_delta(
                                gateway,
                                pending_output,
                                output_secret_reported=output_secret_reported,
                            )
                            yield safe_delta
                        except GuardrailBlockedError as exc:
                            raise LiteLLMClientError(
                                "LiteLLM stream output blocked by guardrail."
                            ) from exc
                    record_model_usage(
                        total_tokens=None,
                        total_cost=_parse_cost_header(
                            response.headers.get("x-litellm-response-cost")
                        ),
                    )
                    security_metrics_service.record_model_usage(
                        total_tokens=None,
                        total_cost=_parse_cost_header(
                            response.headers.get("x-litellm-response-cost")
                        ),
                    )
        except httpx.HTTPStatusError as exc:
            security_metrics_service.record_provider_error()
            record_provider_failure(
                failure_kind="http_status",
                status_code=exc.response.status_code,
            )
            raise LiteLLMClientError(
                f"LiteLLM stream failed with status {exc.response.status_code}."
            ) from None
        except httpx.HTTPError:
            security_metrics_service.record_provider_error()
            record_provider_failure(failure_kind="transport")
            raise LiteLLMClientError("LiteLLM stream failed.") from None

    def _enforce_egress(self, url: str) -> None:
        try:
            enforce_provider_egress_policy(self.settings, url)
        except ProviderEgressDeniedError as exc:
            raise LiteLLMClientError(f"LiteLLM provider egress denied: {exc}") from exc

    def _prepare_payload(
        self,
        gateway: GuardrailGateway,
        *,
        model: str,
        messages: Sequence[ChatMessage],
    ) -> model_data_policy_service.ModelPayloadDecision:
        try:
            secured_messages = gateway.build_secure_prompt(
                [message.model_dump() for message in messages],
                workflow="litellm_chat_completion",
            )
        except GuardrailBlockedError as exc:
            raise LiteLLMClientError("LiteLLM request blocked by guardrail.") from exc
        return model_data_policy_service.prepare_model_payload(
            provider="litellm",
            model=model,
            messages=secured_messages,
        )

    def _safe_model_output(self, gateway: GuardrailGateway, content: str):
        secret_entity_types = data_protection_service.detect_secret_entity_types(content)
        if secret_entity_types:
            record_model_output_secret(secret_entity_types=secret_entity_types)
            content = data_protection_service.redact_for_model(content)
        return gateway.evaluate_model_output(content)

    def _safe_stream_delta(
        self,
        gateway: GuardrailGateway,
        delta: str,
        *,
        output_secret_reported: bool,
    ) -> tuple[str, bool]:
        secret_entity_types = data_protection_service.detect_secret_entity_types(delta)
        if secret_entity_types:
            if not output_secret_reported:
                record_model_output_secret(secret_entity_types=secret_entity_types)
                output_secret_reported = True
            delta = data_protection_service.redact_for_model(delta)
        return gateway.evaluate_model_output(delta).text, output_secret_reported

    def _api_key(self) -> str:
        try:
            value = resolve_secret(self.settings, SecretName.LITELLM_API_KEY)
        except SecretProviderError:
            raise LiteLLMClientError("LiteLLM credentials are unavailable.") from None
        assert value is not None
        return value


def _parse_cost_header(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _redacted_response_body(body: dict[str, Any]) -> dict[str, Any]:
    redacted = data_protection_service.redact_for_trace(body)
    return redacted if isinstance(redacted, dict) else {}
