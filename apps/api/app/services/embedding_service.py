"""Embedding provider boundary for deterministic and LiteLLM-backed vectors."""

import hashlib
import math
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import Settings

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*")


class EmbeddingProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingResult:
    """Embedding vector plus version metadata stored on each evidence chunk."""

    vector: list[float]
    provider: str
    model: str
    dimension: int
    version: str
    embedded_at: datetime


def embed_text(settings: Settings, text: str) -> list[float]:
    return embed_text_with_metadata(settings, text).vector


def embed_text_with_metadata(settings: Settings, text: str) -> EmbeddingResult:
    """Embed text and return provider/model/version metadata for auditability."""
    if settings.embedding_provider == "deterministic":
        vector = deterministic_hash_embedding(settings.embedding_dimension, text)
        return _result(settings, vector, provider="deterministic")
    if settings.embedding_provider == "litellm":
        vector = _embed_with_litellm(settings, text)
        return _result(settings, vector, provider="litellm")
    raise EmbeddingProviderError(f"Unsupported embedding provider: {settings.embedding_provider}")


def deterministic_hash_embedding(dimension: int, text: str) -> list[float]:
    """Return a deterministic local embedding for dev/test-safe retrieval.

    This keeps Sprint 4 demoable without external API keys. The vector is stored
    in pgvector and can be swapped for a hosted embedding model behind the same
    service boundary later.
    """

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


def _embed_with_litellm(settings: Settings, text: str) -> list[float]:
    payload = {"model": settings.embedding_model, "input": text}
    url = f"{settings.litellm_base_url.rstrip('/')}/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.litellm_api_key}",
        "Content-Type": "application/json",
    }
    attempts = settings.embedding_retry_attempts + 1
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            with httpx.Client(timeout=settings.embedding_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            body = response.json()
            vector = body["data"][0]["embedding"]
            if not isinstance(vector, list) or not all(
                isinstance(value, int | float) for value in vector
            ):
                raise EmbeddingProviderError("LiteLLM embedding response did not include a vector.")
            return [float(value) for value in vector]
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            last_error = EmbeddingProviderError(
                f"LiteLLM embedding request failed with status {exc.response.status_code}: {detail}"
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            last_error = EmbeddingProviderError(f"LiteLLM embedding request failed: {exc}")

        if attempt < attempts - 1:
            time.sleep(0.25 * (attempt + 1))

    raise last_error or EmbeddingProviderError("LiteLLM embedding request failed.")


def _result(settings: Settings, vector: list[float], *, provider: str) -> EmbeddingResult:
    dimension = len(vector)
    if dimension != settings.embedding_dimension:
        raise EmbeddingProviderError(
            f"Embedding dimension mismatch: provider returned {dimension}, "
            f"configured dimension is {settings.embedding_dimension}."
        )
    return EmbeddingResult(
        vector=vector,
        provider=provider,
        model=settings.embedding_model,
        dimension=dimension,
        version=settings.embedding_version,
        embedded_at=datetime.now(UTC),
    )


def embedding_metadata(settings: Settings) -> dict[str, Any]:
    """Return embedding settings suitable for chunk metadata and diagnostics."""
    return {
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": settings.embedding_dimension,
        "embedding_version": settings.embedding_version,
    }


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    """Compute cosine similarity while tolerating missing vectors."""
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
