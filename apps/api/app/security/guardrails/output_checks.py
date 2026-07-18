"""Output safety and conservative Markdown link sanitization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.security.guardrails.classifiers import DetectionResult

_MARKDOWN_LINK = re.compile(r"(!?\[[^\]]*\])\(([^)]+)\)")
_HTML_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class OutputEvaluation:
    text: str
    detection: DetectionResult


def sanitize_markdown(value: str, *, allow_http: bool = False) -> str:
    """Remove raw HTML and unsafe/tracking links from model-rendered Markdown."""
    without_html = _HTML_TAG.sub("", value)

    def replace_link(match: re.Match[str]) -> str:
        label, destination = match.groups()
        candidate = destination.strip().strip("<>").split(maxsplit=1)[0]
        parsed = urlparse(candidate)
        allowed_schemes = {"https"} | ({"http"} if allow_http else set())
        if parsed.scheme.casefold() not in allowed_schemes or not parsed.hostname:
            return label
        if label.startswith("!"):
            return label[1:]
        return f"{label}({candidate})"

    return _MARKDOWN_LINK.sub(replace_link, without_html)
