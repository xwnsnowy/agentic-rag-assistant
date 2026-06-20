"""Reranking via Cohere Rerank API.

A reranker is a cross-encoder: it scores (query, document) pairs jointly, which
is more accurate than the bi-encoder cosine similarity used for first-stage
retrieval — but too slow to run over the whole corpus. So the pattern is:
retrieve a larger pool cheaply (hybrid), then rerank that pool and keep top-k.

If COHERE_API_KEY is unset, this is a no-op passthrough (returns the input order
truncated to top_k) so the pipeline still runs end-to-end without a key.
"""

from __future__ import annotations

import time

import httpx

from app.config import get_settings
from app.retrieval import Result

_MAX_RETRIES = 6


def rerank(query: str, results: list[Result], top_k: int = 5) -> list[Result]:
    settings = get_settings()
    if not results:
        return []
    if not settings.cohere_api_key:
        return results[:top_k]  # passthrough when no key

    # Reranking is a best-effort enhancement. If Cohere is unavailable (bad key,
    # rate limit, outage), degrade to the input (hybrid) order instead of failing
    # the whole request.
    try:
        resp = _post_with_backoff(
            settings,
            {
                "model": settings.rerank_model,
                "query": query,
                "documents": [r.content for r in results],
                "top_n": top_k,
            },
        )
        out: list[Result] = []
        for item in resp.json()["results"]:
            r = results[item["index"]]
            r.rerank_score = float(item["relevance_score"])
            out.append(r)
        return out
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        print(f"[rerank] Cohere unavailable, falling back to hybrid order: {type(exc).__name__}")
        return results[:top_k]


def _post_with_backoff(settings, payload: dict) -> httpx.Response:
    """POST to Cohere, retrying on 429/5xx with backoff (free trial keys are
    rate-limited to ~10 req/min)."""
    for attempt in range(_MAX_RETRIES):
        resp = httpx.post(
            "https://api.cohere.com/v2/rerank",
            headers={"Authorization": f"Bearer {settings.cohere_api_key}"},
            json=payload,
            timeout=60.0,
        )
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == _MAX_RETRIES - 1:
                resp.raise_for_status()
            wait = float(resp.headers.get("retry-after", 2 ** attempt))
            time.sleep(min(wait, 30.0))
            continue
        resp.raise_for_status()
        return resp
    return resp  # unreachable, keeps type-checkers happy
