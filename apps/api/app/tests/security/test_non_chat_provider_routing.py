from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services import embedding_service, external_search_service, multimodal_extraction_service
from app.services.identity_service import ensure_dev_identity


def test_litellm_embedding_sends_sanitized_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"data": [{"embedding": [0.1, 0.2]}]}

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

    monkeypatch.setattr(embedding_service.httpx, "Client", FakeClient)
    settings = Settings(
        embedding_provider="litellm",
        embedding_model="dev-gpt-4o-mini",
        embedding_dimension=2,
        litellm_api_key="test-key",
        provider_egress_policy_enabled=False,
    )

    embedding_service.embed_text_with_metadata(
        settings,
        "Email Jane Doe at jane.doe@example.com with api_key=sk-secretvalue123.",
    )

    outbound = captured["json"]["input"]
    assert "Jane Doe" not in outbound
    assert "jane.doe@example.com" not in outbound
    assert "sk-secretvalue123" not in outbound
    assert "[REDACTED_SECRET]" in outbound


def test_tavily_search_sends_sanitized_queries(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    outbound_queries: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"query": "sanitized", "results": []}

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, _url: str, **kwargs: object) -> FakeResponse:
            outbound_queries.append(str(kwargs["json"]["query"]))
            return FakeResponse()

    monkeypatch.setattr(external_search_service.httpx, "Client", FakeClient)
    settings = Settings(
        external_search_enabled=True,
        external_search_provider="tavily",
        tavily_api_key="test-key",
        provider_egress_policy_enabled=False,
    )

    auth = ensure_dev_identity(
        db_session,
        email=settings.dev_auth_default_email,
        display_name=settings.dev_auth_default_name,
        role="owner",
    )
    external_search_service.search_many(
        db_session,
        auth,
        settings,
        ["Find competitors for Jane Doe jane.doe@example.com api_key=sk-secretvalue123"],
    )

    assert len(outbound_queries) == 1
    outbound = outbound_queries[0]
    assert "Jane Doe" not in outbound
    assert "jane.doe@example.com" not in outbound
    assert "sk-secretvalue123" not in outbound
    assert "[REDACTED_SECRET]" in outbound


def test_multimodal_upload_with_detected_sensitive_text_never_reaches_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingClient:
        def __init__(self, **_kwargs: object) -> None:
            raise AssertionError("Sensitive multimodal data must not reach LiteLLM.")

    monkeypatch.setattr(multimodal_extraction_service.httpx, "Client", FailingClient)
    settings = Settings(
        multimodal_extraction_provider="litellm",
        litellm_api_key="test-key",
        provider_egress_policy_enabled=False,
    )

    with pytest.raises(
        multimodal_extraction_service.MultimodalExtractionError,
        match="Raw binary payload",
    ):
        multimodal_extraction_service.extract_file(
            settings,
            filename="interview.pdf",
            content_type="application/pdf",
            body=b"Contact Jane Doe at jane.doe@example.com api_key=sk-secretvalue123.",
            media_type="pdf",
        )
