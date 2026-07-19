import pytest

from app.core.config import Settings
from app.services import embedding_service, model_data_policy_service


def test_embedding_provider_scope_is_explicitly_non_generating() -> None:
    scope = model_data_policy_service.EMBEDDING_PROVIDER_SCOPE

    assert scope.purpose == "embedding"
    assert scope.generates_content is False
    assert scope.requires_guardrail_gateway is False
    assert scope.required_controls == (
        "data_classification",
        "pii_and_secret_redaction",
        "provider_model_policy",
        "credential_resolution",
        "egress_policy",
        "vector_dimension_validation",
    )


def test_litellm_embedding_provider_parses_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        EMBEDDING_PROVIDER="litellm",
        EMBEDDING_MODEL="test-embedding-model",
        EMBEDDING_DIMENSION=3,
        EMBEDDING_VERSION="test-v1",
    )

    monkeypatch.setattr(
        embedding_service,
        "_embed_with_litellm",
        lambda _settings, _text: [1, 2, 3],
    )

    result = embedding_service.embed_text_with_metadata(settings, "customer pain")

    assert result.vector == [1.0, 2.0, 3.0]
    assert result.provider == "litellm"
    assert result.model == "test-embedding-model"
    assert result.dimension == 3
    assert result.version == "test-v1"


def test_embedding_dimension_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        EMBEDDING_PROVIDER="litellm",
        EMBEDDING_MODEL="test-embedding-model",
        EMBEDDING_DIMENSION=4,
    )
    monkeypatch.setattr(
        embedding_service,
        "_embed_with_litellm",
        lambda _settings, _text: [1, 2, 3],
    )

    with pytest.raises(embedding_service.EmbeddingProviderError):
        embedding_service.embed_text_with_metadata(settings, "customer pain")
