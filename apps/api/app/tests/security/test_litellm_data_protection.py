from typing import Any

import httpx
import pytest

from app.ai import litellm_client
from app.ai.litellm_client import ChatMessage, LiteLLMClient, LiteLLMClientError
from app.core.config import Settings


def test_litellm_client_sends_sanitized_payload(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    recorded_pii: list[dict[str, object]] = []

    class FakeResponse:
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "model": "enterprise-model",
                "choices": [{"message": {"content": "safe response"}}],
                "usage": {},
            }

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, _url: str, **kwargs: object) -> FakeResponse:
            captured.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr(litellm_client.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        litellm_client,
        "record_provider_prompt_pii",
        lambda **kwargs: recorded_pii.append(kwargs),
    )
    client = LiteLLMClient(
        Settings(
            llm_stub_mode="never",
            litellm_api_key="test-key",
            provider_egress_policy_enabled=False,
        )
    )

    client.complete(
        [
            ChatMessage(
                role="user",
                content="Email Jane Doe at jane.doe@example.com with api_key=sk-secretvalue123.",
            )
        ]
    )

    outbound_messages = captured["json"]["messages"]
    outbound = "\n".join(message["content"] for message in outbound_messages)
    assert outbound_messages[0]["role"] == "system"
    assert "Security boundary:" in outbound_messages[0]["content"]
    assert "Jane Doe" not in outbound
    assert "jane.doe@example.com" not in outbound
    assert "sk-secretvalue123" not in outbound
    assert "[REDACTED_SECRET]" in outbound
    assert recorded_pii == [
        {
            "pii_entity_types": ("API_KEY", "EMAIL", "PERSON"),
            "redacted_message_count": 1,
        }
    ]


def test_litellm_client_reports_bounded_http_failure_metadata(monkeypatch) -> None:
    recorded: list[dict[str, object]] = []

    class FailingResponse:
        def raise_for_status(self) -> None:
            request = httpx.Request("POST", "https://models.example.test/v1/chat/completions")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("service unavailable", request=request, response=response)

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, _url: str, **_kwargs: object) -> FailingResponse:
            return FailingResponse()

    monkeypatch.setattr(litellm_client.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        litellm_client,
        "record_provider_failure",
        lambda **kwargs: recorded.append(kwargs),
    )
    client = LiteLLMClient(
        Settings(
            llm_stub_mode="never",
            litellm_api_key="test-key",
            provider_egress_policy_enabled=False,
        )
    )

    with pytest.raises(LiteLLMClientError, match="status 503"):
        client.complete([ChatMessage(role="user", content="Return a safe response.")])

    assert recorded == [{"failure_kind": "http_status", "status_code": 503}]
