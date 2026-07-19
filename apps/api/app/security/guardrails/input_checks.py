"""Low-level normalization and suspicious-input inspection helpers."""

from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass

from app.core.redaction import SECRET_VALUE_PATTERNS

MAX_GUARDRAIL_INPUT_CHARS = 50_000
_INVISIBLE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_BASE64_CANDIDATE = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{80,}={0,2}(?![A-Za-z0-9+/=])")


@dataclass(frozen=True)
class InputInspection:
    normalized_text: str
    reasons: tuple[str, ...]
    has_encoded_payload: bool
    has_credential_like_content: bool


def inspect_text(text: str) -> InputInspection:
    """Normalize untrusted text and expose non-content-changing safety signals."""
    normalized = unicodedata.normalize("NFKC", text)
    reasons: list[str] = []
    if len(normalized) > MAX_GUARDRAIL_INPUT_CHARS:
        normalized = normalized[:MAX_GUARDRAIL_INPUT_CHARS]
        reasons.append("input_truncated")
    if _INVISIBLE.search(normalized):
        normalized = _INVISIBLE.sub("", normalized)
        reasons.append("invisible_characters_removed")
    encoded = _has_base64_like_payload(normalized)
    if encoded:
        reasons.append("base64_like_payload")
    credentials = any(pattern.search(normalized) for pattern in SECRET_VALUE_PATTERNS)
    return InputInspection(
        normalized_text=normalized,
        reasons=tuple(reasons),
        has_encoded_payload=encoded,
        has_credential_like_content=credentials,
    )


def _has_base64_like_payload(text: str) -> bool:
    for candidate in _BASE64_CANDIDATE.findall(text):
        try:
            decoded = base64.b64decode(candidate, validate=True)
        except ValueError:
            continue
        if not decoded:
            continue
        printable_ratio = sum(
            byte in b"\t\n\r" or 32 <= byte < 127 for byte in decoded
        ) / len(decoded)
        if printable_ratio > 0.85:
            return True
    return False
