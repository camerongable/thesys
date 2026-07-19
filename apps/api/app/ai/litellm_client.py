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
from app.services import model_data_policy_service
from app.services.security_policy_service import (
    ProviderEgressDeniedError,
    enforce_provider_egress_policy,
)
from app.services.workflow_budget_service import reserve_model_call

ChatRole = Literal["system", "user", "assistant"]


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
            raise LiteLLMClientError(
                f"LiteLLM request failed with status {exc.response.status_code}."
            ) from None
        except httpx.HTTPError:
            raise LiteLLMClientError("LiteLLM request failed.") from None

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LiteLLMClientError(
                "LiteLLM response did not match chat completions format."
            ) from exc
        try:
            safe_output = gateway.evaluate_model_output(str(content))
        except GuardrailBlockedError as exc:
            raise LiteLLMClientError("LiteLLM output blocked by guardrail.") from exc

        usage = body.get("usage") or {}
        return LLMCompletion(
            content=safe_output.text,
            model_provider="litellm",
            model_name=str(body.get("model") or payload["model"]),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            total_cost=_parse_cost_header(response.headers.get("x-litellm-response-cost")),
            raw_response=body,
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
                with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
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
                            try:
                                yield gateway.evaluate_model_output(str(delta)).text
                            except GuardrailBlockedError as exc:
                                raise LiteLLMClientError(
                                    "LiteLLM stream output blocked by guardrail."
                                ) from exc
        except httpx.HTTPStatusError as exc:
            raise LiteLLMClientError(
                f"LiteLLM stream failed with status {exc.response.status_code}."
            ) from None
        except httpx.HTTPError:
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
