from app.services.langsmith_observability_service import sanitize_for_observability


def test_trace_payloads_redact_pii_and_secrets() -> None:
    raw_text = (
        "Jane Doe at jane.doe@example.com uses +1 (415) 555-0123 with "
        "api_key=sk-secretvalue123 and card 4111 1111 1111 1111."
    )

    sanitized = sanitize_for_observability({"source_text": raw_text, "trace_label": "Evidence"})

    for raw_value in (
        "Jane Doe",
        "jane.doe@example.com",
        "415) 555-0123",
        "sk-secretvalue123",
        "4111 1111 1111 1111",
    ):
        assert raw_value not in sanitized["source_text"]
    assert "[REDACTED_SECRET]" in sanitized["source_text"]
