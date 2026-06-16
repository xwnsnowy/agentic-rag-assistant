"""Reranking via Cohere Rerank API.

A reranker is a cross-encoder: it scores (query, document) pairs jointly, which
is more accurate than the bi-encoder cosine similarity used for first-stage
retrieval — but too slow to run over the whole corpus. So the pattern is:
retrieve a larger pool cheaply (hybrid), then rerank that pool and keep top-k.

If COHERE_API_KEY is unset, this is a no-op passthrough (returns the input order
truncated to top_k) so the pipeline still runs end-to-end without a key.
"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.retrieval import Result


def rerank(query: str, results: list[Result], top_k: int = 5) -> list[Result]:
    settings = get_settings()
    if not results:
        return []
    if not settings.cohere_api_key:
        return results[:top_k]  # passthrough when no key

    resp = httpx.post(
        "https://api.cohere.com/v2/rerank",
        headers={"Authorization": f"Bearer {settings.cohere_api_key}"},
        json={
            "model": settings.rerank_model,
            "query": query,
            "documents": [r.content for r in results],
            "top_n": top_k,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    out: list[Result] = []
    for item in resp.json()["results"]:
        r = results[item["index"]]
        r.rerank_score = float(item["relevance_score"])
        out.append(r)
    return out
