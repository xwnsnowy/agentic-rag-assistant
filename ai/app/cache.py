"""In-memory semantic cache for answers.

A repeated (or near-duplicate) question shouldn't re-run retrieval + rerank +
generation. We embed the query and return a cached answer when an earlier query
is above a cosine-similarity threshold — so "what is a reducer?" and "what's a
reducer" hit the same entry. Bounded LRU-ish; process-local (a Redis/pg cache is
the production swap-in).
"""

from __future__ import annotations

import math

from app.embeddings import embed
from app.generation import Answer

_MAX_ENTRIES = 128
_THRESHOLD = 0.90
# entries: list of (embedding, answer)
_entries: list[tuple[list[float], Answer]] = []


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def get(query: str, threshold: float = _THRESHOLD) -> Answer | None:
    """Return a cached answer for a semantically-similar query, else None."""
    if not _entries:
        return None
    qv = embed(query)
    best, best_sim = None, threshold
    for emb, ans in _entries:
        sim = _cosine(qv, emb)
        if sim >= best_sim:
            best, best_sim = ans, sim
    return best


def put(query: str, answer: Answer) -> None:
    _entries.append((embed(query), answer))
    if len(_entries) > _MAX_ENTRIES:
        _entries.pop(0)


def clear() -> None:
    _entries.clear()
