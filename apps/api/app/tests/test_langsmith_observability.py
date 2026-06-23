from app.services.langsmith_observability_service import sanitize_for_observability


def test_observability_sanitizer_redacts_sensitive_keys_and_bounds_payloads() -> None:
    sanitized = sanitize_for_observability(
        {
            "LANGSMITH_API_KEY": "lsv2-secret",
            "nested": {
                "access_token": "secret-access-token",
                "authorization": "Bearer secret-token",
                "context_token_count": 47,
                "safe_value": "visible",
                "token_budget": 3500,
                "token_count": 47,
            },
            "long_text": "x" * 2500,
        }
    )

    assert sanitized["LANGSMITH_API_KEY"] == "[redacted]"
    assert sanitized["nested"]["access_token"] == "[redacted]"
    assert sanitized["nested"]["authorization"] == "[redacted]"
    assert sanitized["nested"]["context_token_count"] == 47
    assert sanitized["nested"]["safe_value"] == "visible"
    assert sanitized["nested"]["token_budget"] == 3500
    assert sanitized["nested"]["token_count"] == 47
    assert len(sanitized["long_text"]) == 2003
    assert sanitized["long_text"].endswith("...")
