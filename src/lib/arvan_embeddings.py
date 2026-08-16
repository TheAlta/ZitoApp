"""OpenAI-compatible embedding client for Zito-owned course retrieval."""

import hashlib
import math
import re
from typing import Any

import httpx

from src.config import get_settings


class ArvanEmbeddingError(RuntimeError):
    pass


_TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


def _mock_embedding(text: str, *, dimensions: int) -> list[float]:
    """Stable local vectors make retrieval tests meaningful without external calls."""
    vector = [0.0] * dimensions
    tokens = _TOKEN_PATTERN.findall(text.lower()) or [text.lower()]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for offset in range(0, 12, 2):
            index = int.from_bytes(digest[offset:offset + 2], "big") % dimensions
            vector[index] += 1.0 if digest[offset] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _parse_embeddings(data: Any, expected_count: int, expected_dimensions: int) -> list[list[float]]:
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list) or len(items) != expected_count:
        raise ArvanEmbeddingError("Unexpected Arvan embedding response shape.")

    parsed: list[tuple[int, list[float]]] = []
    for position, item in enumerate(items):
        embedding = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(embedding, list) or not embedding:
            raise ArvanEmbeddingError("Arvan embedding response contains an empty vector.")
        try:
            vector = [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise ArvanEmbeddingError("Arvan embedding response contains a non-numeric vector.") from exc
        if len(vector) != expected_dimensions:
            raise ArvanEmbeddingError(
                f"Arvan embedding dimension mismatch: expected {expected_dimensions}, received {len(vector)}."
            )
        if not all(math.isfinite(value) for value in vector):
            raise ArvanEmbeddingError("Arvan embedding response contains a non-finite value.")
        index = item.get("index", position) if isinstance(item, dict) else position
        parsed.append((int(index), vector))

    parsed.sort(key=lambda item: item[0])
    return [vector for _, vector in parsed]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    normalized = [text.strip() for text in texts]
    if not normalized or any(not text for text in normalized):
        raise ArvanEmbeddingError("Embedding input must contain non-empty text values.")

    settings = get_settings()
    if settings.arvan_mock_ai:
        return [
            _mock_embedding(text, dimensions=settings.arvan_embedding_dimensions)
            for text in normalized
        ]
    if not settings.has_embedding_configuration:
        raise ArvanEmbeddingError(
            "Arvan embeddings are not configured. Set ARVAN_EMBEDDING_API_BASE_URL and an API key."
        )

    url = f"{settings.arvan_embedding_api_base_url.rstrip('/')}/embeddings"
    payload = {"model": settings.arvan_embedding_model, "input": normalized}
    headers = {
        "Authorization": f"Bearer {settings.effective_embedding_api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(
            timeout=settings.arvan_embedding_timeout_seconds,
            trust_env=False,
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response is not None else ""
        raise ArvanEmbeddingError(
            f"Arvan embeddings returned HTTP {exc.response.status_code}: {body}"
        ) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise ArvanEmbeddingError(f"Could not call Arvan embeddings ({type(exc).__name__}): {exc}") from exc

    return _parse_embeddings(data, len(normalized), settings.arvan_embedding_dimensions)
