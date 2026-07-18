"""Deterministic provider policy for sanitized model payloads."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.security.contracts import DataClassification
from app.services.data_protection_service import data_protection_service


@dataclass(frozen=True)
class ModelDataPolicy:
    provider: str
    model: str
    maximum_data_classification: DataClassification
    allows_pii: bool
    allows_provider_retention: bool
    approved_purposes: tuple[str, ...]


@dataclass(frozen=True)
class ModelPayloadDecision:
    policy: ModelDataPolicy
    original_data_classification: DataClassification
    outbound_data_classification: DataClassification
    messages: list[dict[str, Any]]


class ModelDataPolicyError(ValueError):
    pass


_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}

_LITELLM_POLICY = ModelDataPolicy(
    provider="litellm",
    model="*",
    maximum_data_classification=DataClassification.CONFIDENTIAL,
    allows_pii=False,
    allows_provider_retention=False,
    approved_purposes=("guided_reasoning", "structured_extraction", "reranking"),
)


def prepare_model_payload(
    *,
    provider: str,
    model: str,
    messages: Sequence[dict[str, Any]],
) -> ModelPayloadDecision:
    """Return the representation permitted to cross a model-provider boundary."""
    policy = resolve_policy(provider, model)
    original_classification = _maximum_classification(
        str(message.get("content") or "") for message in messages
    )
    sanitized_messages = [
        {
            **message,
            "content": data_protection_service.redact_for_model(str(message.get("content") or "")),
        }
        for message in messages
    ]
    outbound_classification = _maximum_classification(
        str(message["content"]) for message in sanitized_messages
    )
    if _CLASSIFICATION_RANK[outbound_classification] > _CLASSIFICATION_RANK[
        policy.maximum_data_classification
    ]:
        raise ModelDataPolicyError("Provider policy does not permit this payload classification.")
    return ModelPayloadDecision(
        policy=policy,
        original_data_classification=original_classification,
        outbound_data_classification=outbound_classification,
        messages=sanitized_messages,
    )


def resolve_policy(provider: str, model: str) -> ModelDataPolicy:
    if provider == "litellm":
        return replace(_LITELLM_POLICY, model=model)
    raise ModelDataPolicyError(f"No data policy is configured for provider: {provider}.")


def _maximum_classification(values: Iterable[str]) -> DataClassification:
    classifications = [data_protection_service.classify_text(value) for value in values]
    return max(
        classifications or [DataClassification.INTERNAL],
        key=_CLASSIFICATION_RANK.__getitem__,
    )
