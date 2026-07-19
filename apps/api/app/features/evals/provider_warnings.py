"""Provider-unavailable warning payloads for local eval gates."""

from typing import Any

from app.features.evals import metric_records


def live_provider_warning_messages(
    *,
    multimodal_provider: str,
    litellm_key_configured: bool,
    tavily_key_configured: bool,
) -> list[str]:
    """Build visible warnings for skipped live-provider extraction checks."""

    warnings: list[str] = []
    if multimodal_provider == "litellm" and not litellm_key_configured:
        warnings.append(
            "multimodal live provider skipped: LITELLM_API_KEY missing; "
            "rerun with provider credentials and egress allowlist"
        )
    if not tavily_key_configured:
        warnings.append(
            "Tavily live source QA skipped: TAVILY_API_KEY missing; "
            "rerun with search credentials and egress allowlist"
        )
    if multimodal_provider != "litellm":
        warnings.append(
            f"multimodal live provider skipped: provider is {multimodal_provider}; "
            "set MULTIMODAL_EXTRACTION_PROVIDER=litellm for live QA"
        )
    return warnings


def live_provider_unavailable_metric(
    *,
    multimodal_provider: str,
    litellm_key_configured: bool,
    tavily_key_configured: bool,
) -> dict[str, Any]:
    """Build the extraction eval metric for skipped live-provider QA."""

    warnings = live_provider_warning_messages(
        multimodal_provider=multimodal_provider,
        litellm_key_configured=litellm_key_configured,
        tavily_key_configured=tavily_key_configured,
    )
    return metric_records.metric(
        "live_provider_unavailable_warning",
        "Live provider unavailable warnings",
        True,
        {
            "multimodal_provider": multimodal_provider,
            "litellm_key_configured": litellm_key_configured,
            "tavily_key_configured": tavily_key_configured,
            "warning_count": len(warnings),
        },
        "missing or disabled live providers are visible warnings, not silent passes",
        warnings=warnings,
    )
