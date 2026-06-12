import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "secret",
    "token",
    "master_key",
    "access_key",
    "private_key",
)

SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+\-/]+=*\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*"
        r"['\"]?[^'\"\s,;}]+"
    ),
)

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
MAX_STRING_LENGTH = 4000


def redact_text(
    value: str,
    *,
    redact_emails: bool = False,
    max_string_length: int = MAX_STRING_LENGTH,
) -> str:
    redacted = value
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    if redact_emails:
        redacted = EMAIL_PATTERN.sub("[redacted-email]", redacted)
    return (
        redacted
        if len(redacted) <= max_string_length
        else f"{redacted[:max_string_length]}..."
    )


def redact_payload(
    value: Any,
    *,
    key: str | None = None,
    redact_emails: bool = False,
    max_string_length: int = MAX_STRING_LENGTH,
) -> Any:
    if key and is_sensitive_key(key):
        return "[redacted]"
    if isinstance(value, BaseModel):
        return redact_payload(
            value.model_dump(mode="json"),
            redact_emails=redact_emails,
            max_string_length=max_string_length,
        )
    if isinstance(value, dict):
        return {
            str(item_key): redact_payload(
                item_value,
                key=str(item_key),
                redact_emails=redact_emails,
                max_string_length=max_string_length,
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [
            redact_payload(
                item,
                redact_emails=redact_emails,
                max_string_length=max_string_length,
            )
            for item in value[:100]
        ]
    if isinstance(value, (tuple, set)):
        return [
            redact_payload(
                item,
                redact_emails=redact_emails,
                max_string_length=max_string_length,
            )
            for item in list(value)[:100]
        ]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str):
        return redact_text(
            value,
            redact_emails=redact_emails,
            max_string_length=max_string_length,
        )
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(
        str(value),
        redact_emails=redact_emails,
        max_string_length=max_string_length,
    )


def is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
