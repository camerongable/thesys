from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings

ChatRole = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1)


@dataclass(frozen=True)
class LLMCompletion:
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
        payload: dict[str, Any] = {
            "model": model or self.settings.litellm_model,
            "messages": [message.model_dump() for message in messages],
            "temperature": temperature,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = f"{self.settings.litellm_base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.litellm_api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.settings.litellm_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise LiteLLMClientError(
                f"LiteLLM request failed with status {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LiteLLMClientError(f"LiteLLM request failed: {exc}") from exc

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LiteLLMClientError(
                "LiteLLM response did not match chat completions format."
            ) from exc

        usage = body.get("usage") or {}
        return LLMCompletion(
            content=content,
            model_provider="litellm",
            model_name=str(body.get("model") or payload["model"]),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            total_cost=_parse_cost_header(response.headers.get("x-litellm-response-cost")),
            raw_response=body,
            used_stub=False,
        )


def _parse_cost_header(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
