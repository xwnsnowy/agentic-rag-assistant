"""Retrieval over the chunks table.

Three strategies, so the eval harness can compare them with real numbers:
  - vector_search   : semantic, pgvector cosine distance (<=>)
  - keyword_search  : lexical, Postgres full-text (tsvector + websearch_to_tsquery)
  - hybrid_search   : fuse the two rankings with Reciprocal Rank Fusion (RRF)

Why RRF: it merges rankings using only rank position, so we don't have to
calibrate cosine scores against ts_rank scores (different scales). Robust and
the standard baseline for hybrid search.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db import get_connection, vector_literal
from app.embeddings import embed


@dataclass
class Result:
    chunk_id: int
    content: str
    metadata: dict
    vector_rank: int | None = None
    keyword_rank: int | None = None
    vector_score: float | None = None  # cosine similarity (higher = closer)
    keyword_score: float | None = None  # ts_rank
    rrf_score: float | None = None

    @property
    def citation(self) -> str:
        m = self.metadata or {}
        return f"{m.get('page_title', '?')} — {m.get('heading', '')} <{m.get('source_url', '')}>"


def vector_search(query: str, k: int = 5) -> list[Result]:
    """Top-k by cosine similarity in pgvector."""
    qv = vector_literal(embed(query))
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, content, metadata,
                   1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (qv, qv, k),
        )
        rows = cur.fetchall()
    return [
        Result(chunk_id=r[0], content=r[1], metadata=r[2],
               vector_rank=i + 1, vector_score=float(r[3]))
        for i, r in enumerate(rows)
    ]


def keyword_search(query: str, k: int = 5) -> list[Result]:
    """Top-k by Postgres full-text rank. websearch_to_tsquery handles plain user
    queries (phrases, operators) gracefully."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, content, metadata,
                   ts_rank(tsv, websearch_to_tsquery('english', %s)) AS rank
            FROM chunks
            WHERE tsv @@ websearch_to_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
            """,
            (query, query, k),
        )
        rows = cur.fetchall()
    return [
        Result(chunk_id=r[0], content=r[1], metadata=r[2],
               keyword_rank=i + 1, keyword_score=float(r[3]))
        for i, r in enumerate(rows)
    ]


def hybrid_search(query: str, k: int = 5, *, pool: int = 20, rrf_k: int = 60) -> list[Result]:
    """Reciprocal Rank Fusion of vector + keyword rankings.

    Each method contributes 1 / (rrf_k + rank). We pull `pool` candidates from
    each, fuse, and return the top-k. rrf_k=60 is the common default that damps
    the weight of very high ranks.
    """
    vec = vector_search(query, pool)
    kw = keyword_search(query, pool)

    merged: dict[int, Result] = {}
    for r in vec:
        merged[r.chunk_id] = r
    for r in kw:
        if r.chunk_id in merged:
            merged[r.chunk_id].keyword_rank = r.keyword_rank
            merged[r.chunk_id].keyword_score = r.keyword_score
        else:
            merged[r.chunk_id] = r

    for r in merged.values():
        score = 0.0
        if r.vector_rank:
            score += 1.0 / (rrf_k + r.vector_rank)
        if r.keyword_rank:
            score += 1.0 / (rrf_k + r.keyword_rank)
        r.rrf_score = score

    ranked = sorted(merged.values(), key=lambda r: r.rrf_score or 0.0, reverse=True)
    return ranked[:k]
