from app.core.config import Settings


def should_use_fallback_without_model(settings: Settings) -> bool:
    return not settings.should_use_llm_stub and settings.llm_fallback_policy == "always"


def should_use_fallback_after_error(settings: Settings) -> bool:
    return (
        not settings.should_use_llm_stub
        and settings.llm_fallback_policy in {"always", "emergency"}
    )
