from app.services.langsmith_observability_service import sanitize_for_observability


def test_observability_sanitizer_redacts_sensitive_keys_and_bounds_payloads() -> None:
    sanitized = sanitize_for_observability(
        {
            "LANGSMITH_API_KEY": "lsv2-secret",
            "nested": {
                "authorization": "Bearer secret-token",
                "safe_value": "visible",
            },
            "long_text": "x" * 2500,
        }
    )

    assert sanitized["LANGSMITH_API_KEY"] == "[redacted]"
    assert sanitized["nested"]["authorization"] == "[redacted]"
    assert sanitized["nested"]["safe_value"] == "visible"
    assert len(sanitized["long_text"]) == 2003
    assert sanitized["long_text"].endswith("...")
