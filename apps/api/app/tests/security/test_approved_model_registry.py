import pytest

from app.security.contracts import DataClassification
from app.security.model_registry import (
    APPROVED_MODELS,
    ApprovedModelRegistryError,
    resolve_approved_model,
)
from app.services import model_data_policy_service


def test_approved_models_have_complete_security_evaluation_metadata() -> None:
    assert APPROVED_MODELS
    for model in APPROVED_MODELS:
        assert model.provider
        assert model.model_id
        assert model.purpose
        assert model.maximum_data_classification in DataClassification
        assert model.security_eval_version
        assert model.approved_at
        assert model.approved_by
        assert model.enabled
        assert all(
            0.0 <= rate <= 1.0
            for rate in (
                model.prompt_injection_pass_rate,
                model.grounding_pass_rate,
                model.pii_leakage_pass_rate,
                model.tool_selection_pass_rate,
            )
        )


def test_approved_model_requires_an_exact_provider_model_and_purpose() -> None:
    approval = resolve_approved_model(
        provider="litellm",
        model_id="dev-gpt-4o-mini",
        purpose="chat_completion",
    )

    assert approval.maximum_data_classification is DataClassification.CONFIDENTIAL
    with pytest.raises(ApprovedModelRegistryError):
        resolve_approved_model(
            provider="litellm",
            model_id="unreviewed-model",
            purpose="chat_completion",
        )


def test_provider_routing_denies_an_unapproved_model() -> None:
    with pytest.raises(
        model_data_policy_service.ModelDataPolicyError,
        match="No enabled approved model",
    ):
        model_data_policy_service.prepare_model_payload(
            provider="litellm",
            model="unreviewed-model",
            messages=[{"role": "user", "content": "Summarize customer interviews."}],
        )
