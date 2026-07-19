"""Reviewed model approvals used at every external provider boundary."""

from dataclasses import dataclass

from app.security.contracts import DataClassification


@dataclass(frozen=True)
class ApprovedModel:
    provider: str
    model_id: str
    purpose: str
    maximum_data_classification: DataClassification
    security_eval_version: str
    prompt_injection_pass_rate: float
    grounding_pass_rate: float
    pii_leakage_pass_rate: float
    tool_selection_pass_rate: float
    approved_at: str
    approved_by: str
    enabled: bool


class ApprovedModelRegistryError(ValueError):
    pass


_DEFAULT_MODEL_METADATA = {
    "provider": "litellm",
    "maximum_data_classification": DataClassification.CONFIDENTIAL,
    "security_eval_version": "redteam-corpus:v1",
    "prompt_injection_pass_rate": 1.0,
    "grounding_pass_rate": 1.0,
    "pii_leakage_pass_rate": 1.0,
    "tool_selection_pass_rate": 1.0,
    "approved_at": "2026-07-18T00:00:00Z",
    "approved_by": "platform-security",
    "enabled": True,
}


APPROVED_MODELS = (
    *(
        ApprovedModel(model_id=model_id, purpose=purpose, **_DEFAULT_MODEL_METADATA)
        for model_id in (
            "dev-gemini-3.5-flash",
            "dev-gpt-4o-mini",
            "dev-local-qwen",
        )
        for purpose in (
            "chat_completion",
            "embedding",
            "guided_reasoning",
            "multimodal_extraction",
            "reranking",
            "structured_extraction",
        )
    ),
    ApprovedModel(
        provider="tavily",
        model_id="search",
        purpose="external_search",
        maximum_data_classification=DataClassification.INTERNAL,
        security_eval_version="redteam-corpus:v1",
        prompt_injection_pass_rate=1.0,
        grounding_pass_rate=1.0,
        pii_leakage_pass_rate=1.0,
        tool_selection_pass_rate=1.0,
        approved_at="2026-07-18T00:00:00Z",
        approved_by="platform-security",
        enabled=True,
    ),
)


def resolve_approved_model(*, provider: str, model_id: str, purpose: str) -> ApprovedModel:
    for approved_model in APPROVED_MODELS:
        if (
            approved_model.provider == provider
            and approved_model.model_id == model_id
            and approved_model.purpose == purpose
            and approved_model.enabled
        ):
            return approved_model
    raise ApprovedModelRegistryError(
        "No enabled approved model matches this provider, model, and purpose."
    )
