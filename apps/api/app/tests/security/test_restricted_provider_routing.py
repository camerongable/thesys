from app.services import model_data_policy_service


def test_restricted_content_uses_a_sanitized_provider_representation() -> None:
    decision = model_data_policy_service.prepare_model_payload(
        provider="litellm",
        model="enterprise-model",
        messages=[
            {
                "role": "user",
                "content": (
                    "Contact Jane Doe at jane.doe@example.com with "
                    "api_key=sk-secretvalue123."
                ),
            }
        ],
    )

    outbound = decision.messages[0]["content"]
    assert decision.original_data_classification.value == "restricted"
    assert decision.outbound_data_classification.value == "internal"
    assert decision.policy.allows_pii is False
    assert decision.policy.allows_provider_retention is False
    assert "Jane Doe" not in outbound
    assert "jane.doe@example.com" not in outbound
    assert "sk-secretvalue123" not in outbound
    assert "[REDACTED_SECRET]" in outbound
