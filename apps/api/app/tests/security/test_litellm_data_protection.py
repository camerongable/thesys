from typing import Any

from app.ai import litellm_client
from app.ai.litellm_client import ChatMessage, LiteLLMClient
from app.core.config import Settings


def test_litellm_client_sends_sanitized_payload(monkeypatch) -> None:
    captured: dict[str, Any] = {}

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

    outbound = captured["json"]["messages"][0]["content"]
    assert "Jane Doe" not in outbound
    assert "jane.doe@example.com" not in outbound
    assert "sk-secretvalue123" not in outbound
    assert "[REDACTED_SECRET]" in outbound
