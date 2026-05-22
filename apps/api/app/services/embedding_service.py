import hashlib
import math
import re

from app.core.config import Settings

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*")


def embed_text(settings: Settings, text: str) -> list[float]:
    """Return a deterministic local embedding for dev/test-safe retrieval.

    This keeps Sprint 4 demoable without external API keys. The vector is stored
    in pgvector and can be swapped for a hosted embedding model behind the same
    service boundary later.
    """

    dimension = settings.embedding_dimension
    values = [0.0] * dimension
    tokens = _tokens(text)
    if not tokens:
        return values

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        values[bucket] += sign

    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if left is None or right is None:
        return 0.0
    left_values = list(left)
    right_values = list(right)
    limit = min(len(left), len(right))
    if limit == 0:
        return 0.0
    dot = sum(left_values[index] * right_values[index] for index in range(limit))
    left_norm = math.sqrt(sum(value * value for value in left_values[:limit]))
    right_norm = math.sqrt(sum(value * value for value in right_values[:limit]))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, dot / (left_norm * right_norm))


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_RE.finditer(text)]
