"""Embedding provider boundary for deterministic and LiteLLM-backed vectors."""

import hashlib
import math
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.security.secrets import SecretName, SecretProviderError, resolve_secret
from app.services import model_data_policy_service
from app.services.security_policy_service import (
    ProviderEgressDeniedError,
    enforce_provider_egress_policy,
)

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


def embed_text_with_metadata_cached(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    text: str,
    *,
    project_id: Any | None = None,
) -> EmbeddingResult:
    """Embed text with a workspace-scoped cache keyed by text hash and provider version."""

    from app.services import ai_cache_service

    key, family, versions = ai_cache_service.embedding_cache_payloads(auth, settings, text)
    lookup = ai_cache_service.lookup(
        db,
        auth,
        settings,
        cache_type="embedding",
        key_payload=key,
        family_payload=family,
        version_payload=versions,
        project_id=project_id,
        latency_saved_ms=50,
    )
    if lookup.value is not None:
        value = lookup.value
        embedded_at_raw = value.get("embedded_at")
        embedded_at = (
            datetime.fromisoformat(str(embedded_at_raw))
            if embedded_at_raw
            else datetime.now(UTC)
        )
        return EmbeddingResult(
            vector=[float(item) for item in value.get("vector", [])],
            provider=str(value.get("provider") or settings.embedding_provider),
            model=str(value.get("model") or settings.embedding_model),
            dimension=int(value.get("dimension") or settings.embedding_dimension),
            version=str(value.get("version") or settings.embedding_version),
            embedded_at=embedded_at,
        )

    result = embed_text_with_metadata(settings, text)
    ai_cache_service.store(
        db,
        auth,
        cache_type="embedding",
        key_payload=key,
        family_payload=family,
        version_payload=versions,
        value_payload={
            "vector": result.vector,
            "provider": result.provider,
            "model": result.model,
            "dimension": result.dimension,
            "version": result.version,
            "embedded_at": result.embedded_at.isoformat(),
        },
        project_id=project_id,
    )
    return result


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
    try:
        api_key = resolve_secret(settings, SecretName.LITELLM_API_KEY)
    except SecretProviderError:
        raise EmbeddingProviderError("LiteLLM embedding credentials are unavailable.") from None
    try:
        decision = model_data_policy_service.prepare_embedding_provider_text(
            provider="litellm",
            model=settings.embedding_model,
            text=text,
        )
    except model_data_policy_service.ModelDataPolicyError as exc:
        raise EmbeddingProviderError(str(exc)) from None
    payload = {"model": settings.embedding_model, "input": decision.text}
    url = f"{settings.litellm_base_url.rstrip('/')}/v1/embeddings"
    try:
        enforce_provider_egress_policy(settings, url)
    except ProviderEgressDeniedError as exc:
        raise EmbeddingProviderError(f"LiteLLM embedding egress denied: {exc}") from exc
    headers = {
        "Authorization": f"Bearer {api_key}",
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
            last_error = EmbeddingProviderError(
                f"LiteLLM embedding request failed with status {exc.response.status_code}."
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            last_error = EmbeddingProviderError("LiteLLM embedding request failed.")

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
