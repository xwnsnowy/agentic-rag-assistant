"""Embeddings via an OpenAI-compatible API (default: OpenAI text-embedding-3-small).

Phase 0 only needs to prove the DB round-trip works, so we also provide a
deterministic fake-embedding fallback (used when no API key is configured) so
the cosine-similarity demo runs without spending tokens.
"""

import hashlib
import math

import httpx

from app.config import get_settings


def embed(text: str) -> list[float]:
    """Return an embedding vector for `text`.

    Uses the real embeddings API when EMBEDDING_API_KEY is set; otherwise falls
    back to a deterministic pseudo-embedding so Phase 0 can be demonstrated
    offline. The fallback is NOT semantically meaningful — it only exercises the
    insert + cosine-query path.
    """
    settings = get_settings()
    if settings.embedding_api_key:
        return _embed_remote(text)
    return fake_embed(text, settings.embedding_dim)


def embed_many(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Uses one API call per batch when a key is set."""
    if not texts:
        return []
    settings = get_settings()
    if settings.embedding_api_key:
        return _embed_remote(texts)
    return [fake_embed(t, settings.embedding_dim) for t in texts]


def _embed_remote(text_or_texts: str | list[str]) -> list:
    settings = get_settings()
    resp = httpx.post(
        f"{settings.embedding_api_base}/embeddings",
        headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
        json={"model": settings.embedding_model, "input": text_or_texts},
        timeout=60.0,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    embeddings = [d["embedding"] for d in data]
    return embeddings[0] if isinstance(text_or_texts, str) else embeddings


def fake_embed(text: str, dim: int) -> list[float]:
    """Deterministic unit-norm vector seeded from the text hash (offline demo)."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    values: list[float] = []
    x = seed
    for _ in range(dim):
        # Simple LCG to spread values; not cryptographic, just deterministic.
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        values.append((x / 0x7FFFFFFF) * 2.0 - 1.0)
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]
