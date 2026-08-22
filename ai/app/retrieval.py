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

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

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
    rerank_score: float | None = None  # set by the reranker (Cohere relevance)

    @property
    def citation(self) -> str:
        m = self.metadata or {}
        return f"{m.get('page_title', '?')} — {m.get('heading', '')} <{m.get('source_url', '')}>"


def _version_predicate(version: str | None) -> tuple[str, tuple]:
    """SQL fragment + params for the docs_version filter.

    None means NO filter (search across every corpus version); a string
    restricts candidates to that version. Kept in one place so vector and
    keyword search can't drift apart."""
    if version is None:
        return "", ()
    return "docs_version = %s", (version,)


def vector_search(query: str, k: int = 5, *, version: str | None = None) -> list[Result]:
    """Top-k by cosine similarity in pgvector, optionally within one docs_version."""
    qv = vector_literal(embed(query))
    pred, pred_params = _version_predicate(version)
    where = f"WHERE {pred}" if pred else ""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, content, metadata,
                   1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM chunks
            {where}
            ORDER BY embedding <=> %s::vector, id
            LIMIT %s
            """,
            (qv, *pred_params, qv, k),
        )
        rows = cur.fetchall()
    return [
        Result(chunk_id=r[0], content=r[1], metadata=r[2],
               vector_rank=i + 1, vector_score=float(r[3]))
        for i, r in enumerate(rows)
    ]


def keyword_search(query: str, k: int = 5, *, version: str | None = None) -> list[Result]:
    """Top-k by Postgres full-text rank. websearch_to_tsquery handles plain user
    queries (phrases, operators) gracefully.

    The `, id` in ORDER BY is a deterministic tiebreaker, not decoration.
    ts_rank produces genuine ties — including float-noise scores around 2e-16
    shared by many rows — and SQL leaves the order of tied rows unspecified, so
    Postgres returns whatever physical order it happens to have. A full-table
    UPDATE (migration 003) rewrote row order and silently permuted one query's
    top-20, moving MRR by 0.017 with no code change. Retrieval that is not
    reproducible cannot be measured, so ties break by id.
    """
    pred, pred_params = _version_predicate(version)
    extra = f"AND {pred}" if pred else ""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, content, metadata,
                   ts_rank(tsv, websearch_to_tsquery('english', %s)) AS rank
            FROM chunks
            WHERE tsv @@ websearch_to_tsquery('english', %s)
            {extra}
            ORDER BY rank DESC, id
            LIMIT %s
            """,
            (query, query, *pred_params, k),
        )
        rows = cur.fetchall()
    return [
        Result(chunk_id=r[0], content=r[1], metadata=r[2],
               keyword_rank=i + 1, keyword_score=float(r[3]))
        for i, r in enumerate(rows)
    ]


def rrf_fuse(vec: list[Result], kw: list[Result], *, rrf_k: int = 60) -> list[Result]:
    """Fuse a vector ranking and a keyword ranking with Reciprocal Rank Fusion.

    Pure function (no I/O) so the fusion math is unit-testable without Postgres.

    Why RRF: it merges rankings using only rank position, so we don't have to
    calibrate cosine scores against ts_rank scores (different, incompatible
    scales). Each method contributes 1 / (rrf_k + rank); a chunk found by both
    methods sums both contributions. rrf_k=60 is the common default that damps
    the weight of very high ranks.
    """
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

    # sorted() is stable: ties keep insertion order (vector hits, then keyword-only).
    return sorted(merged.values(), key=lambda r: r.rrf_score or 0.0, reverse=True)


def search_both(
    query: str,
    pool: int,
    *,
    version: str | None = None,
    vector: Callable[..., list[Result]] | None = None,
    keyword: Callable[..., list[Result]] | None = None,
) -> tuple[list[Result], list[Result]]:
    """Run vector and keyword search concurrently and return (vec, kw).

    The two legs are independent and each is dominated by waiting on the
    network (the embeddings API, then Neon), so overlapping them costs nothing
    and the keyword leg finishes entirely inside the embed call's shadow.
    `vector`/`keyword` let a caller substitute its own bound names (the
    pipeline's tests patch those, not this module's).
    """
    vector = vector or vector_search
    keyword = keyword or keyword_search
    with ThreadPoolExecutor(max_workers=2) as ex:
        vec_f = ex.submit(vector, query, pool, version=version)
        kw_f = ex.submit(keyword, query, pool, version=version)
        return vec_f.result(), kw_f.result()


def hybrid_search(
    query: str, k: int = 5, *, pool: int = 20, rrf_k: int = 60, version: str | None = None
) -> list[Result]:
    """Hybrid retrieval: pull `pool` candidates from each of vector + keyword
    search, fuse the two rankings with RRF (see rrf_fuse), return the top-k."""
    vec, kw = search_both(query, pool, version=version)
    return rrf_fuse(vec, kw, rrf_k=rrf_k)[:k]
