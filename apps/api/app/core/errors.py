from app.core.redaction import redact_text


class AppError(Exception):
    """Base exception for application-level errors."""


def public_error_detail(summary: str, exc: BaseException) -> str:
    cause = exc.__cause__ or exc
    detail = redact_text(str(cause), redact_emails=True).strip()
    if detail and detail != summary:
        return f"{summary}: {detail}"
    return summary
