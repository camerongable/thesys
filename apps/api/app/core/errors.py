import re


class AppError(Exception):
    """Base exception for application-level errors."""


SECRET_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,})\b")


def public_error_detail(summary: str, exc: BaseException) -> str:
    cause = exc.__cause__ or exc
    detail = _redact_secrets(str(cause)).strip()
    if detail and detail != summary:
        return f"{summary}: {detail}"
    return summary


def _redact_secrets(value: str) -> str:
    return SECRET_PATTERN.sub("[redacted]", value)
