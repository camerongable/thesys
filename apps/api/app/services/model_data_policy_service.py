"""Deterministic provider policy for sanitized model payloads."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from app.security.contracts import DataClassification
from app.security.model_registry import ApprovedModelRegistryError, resolve_approved_model
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
    pii_entity_types: tuple[str, ...]
    redacted_message_count: int
    messages: list[dict[str, Any]]


@dataclass(frozen=True)
class ProviderTextDecision:
    policy: ModelDataPolicy
    original_data_classification: DataClassification
    outbound_data_classification: DataClassification
    pii_entity_types: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class EmbeddingProviderScope:
    """Controls for non-generative vectorization provider requests."""

    purpose: Literal["embedding"]
    generates_content: bool
    requires_guardrail_gateway: bool
    required_controls: tuple[str, ...]


EMBEDDING_PROVIDER_SCOPE = EmbeddingProviderScope(
    purpose="embedding",
    generates_content=False,
    requires_guardrail_gateway=False,
    required_controls=(
        "data_classification",
        "pii_and_secret_redaction",
        "provider_model_policy",
        "credential_resolution",
        "egress_policy",
        "vector_dimension_validation",
    ),
)


class ModelDataPolicyError(ValueError):
    pass


_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


def prepare_model_payload(
    *,
    provider: str,
    model: str,
    messages: Sequence[dict[str, Any]],
) -> ModelPayloadDecision:
    """Return the representation permitted to cross a model-provider boundary."""
    policy = resolve_policy(provider=provider, model=model, purpose="chat_completion")
    decisions = [
        prepare_provider_text(
            provider=provider,
            model=model,
            text=str(message.get("content") or ""),
            purpose="chat_completion",
        )
        for message in messages
    ]
    original_classification = max(
        (decision.original_data_classification for decision in decisions),
        default=DataClassification.INTERNAL,
        key=_CLASSIFICATION_RANK.__getitem__,
    )
    sanitized_messages = [
        {**message, "content": decision.text}
        for message, decision in zip(messages, decisions, strict=True)
    ]
    outbound_classification = _maximum_classification(
        str(message["content"]) for message in sanitized_messages
    )
    if (
        _CLASSIFICATION_RANK[outbound_classification]
        > _CLASSIFICATION_RANK[policy.maximum_data_classification]
    ):
        raise ModelDataPolicyError("Provider policy does not permit this payload classification.")
    return ModelPayloadDecision(
        policy=policy,
        original_data_classification=original_classification,
        outbound_data_classification=outbound_classification,
        pii_entity_types=tuple(
            sorted(
                {entity_type for decision in decisions for entity_type in decision.pii_entity_types}
            )
        ),
        redacted_message_count=sum(bool(decision.pii_entity_types) for decision in decisions),
        messages=sanitized_messages,
    )


def prepare_provider_text(
    *,
    provider: str,
    model: str,
    text: str,
    purpose: str,
) -> ProviderTextDecision:
    """Sanitize one text payload for an approved non-local provider purpose."""
    policy = resolve_policy(provider=provider, model=model, purpose=purpose)
    if purpose not in policy.approved_purposes:
        raise ModelDataPolicyError(f"Provider policy does not permit purpose: {purpose}.")
    original_classification = _maximum_classification([text])
    sanitized = data_protection_service.create_searchable_copy(text)
    outbound_classification = _maximum_classification([sanitized.text])
    if (
        _CLASSIFICATION_RANK[outbound_classification]
        > _CLASSIFICATION_RANK[policy.maximum_data_classification]
    ):
        raise ModelDataPolicyError("Provider policy does not permit this payload classification.")
    return ProviderTextDecision(
        policy=policy,
        original_data_classification=original_classification,
        outbound_data_classification=outbound_classification,
        pii_entity_types=sanitized.pii_entity_types,
        text=sanitized.text,
    )


def prepare_embedding_provider_text(
    *,
    provider: str,
    model: str,
    text: str,
) -> ProviderTextDecision:
    """Prepare text for vectorization without treating it as an instruction prompt."""
    return prepare_provider_text(
        provider=provider,
        model=model,
        text=text,
        purpose=EMBEDDING_PROVIDER_SCOPE.purpose,
    )


def permit_binary_provider_payload(
    *,
    provider: str,
    model: str,
    inspection_text: str,
    purpose: str,
) -> ProviderTextDecision:
    """Reject a raw binary upload whenever local inspection requires redaction."""
    decision = prepare_provider_text(
        provider=provider,
        model=model,
        text=inspection_text,
        purpose=purpose,
    )
    if decision.text != inspection_text:
        raise ModelDataPolicyError(
            "Raw binary payload contains values that require redaction before provider transit."
        )
    return decision


def resolve_policy(*, provider: str, model: str, purpose: str) -> ModelDataPolicy:
    try:
        approved_model = resolve_approved_model(
            provider=provider,
            model_id=model,
            purpose=purpose,
        )
    except ApprovedModelRegistryError as exc:
        raise ModelDataPolicyError(str(exc)) from None
    return ModelDataPolicy(
        provider=approved_model.provider,
        model=approved_model.model_id,
        maximum_data_classification=approved_model.maximum_data_classification,
        allows_pii=False,
        allows_provider_retention=False,
        approved_purposes=(approved_model.purpose,),
    )


def _maximum_classification(values: Iterable[str]) -> DataClassification:
    classifications = [data_protection_service.classify_text(value) for value in values]
    return max(
        classifications or [DataClassification.INTERNAL],
        key=_CLASSIFICATION_RANK.__getitem__,
    )
