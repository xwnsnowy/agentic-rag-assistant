"""End-to-end RAG pipeline + the configs the eval harness compares.

RagConfig captures one retrieval strategy so the eval can run the SAME queries
through baseline vs hybrid vs hybrid+rerank and tabulate the difference.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.generation import Answer, generate
from app.query_rewrite import rewrite_query
from app.rerank import rerank
from app.retrieval import Result, keyword_search, rrf_fuse, vector_search


@dataclass
class RagConfig:
    name: str
    method: str = "hybrid"  # 'vector' | 'keyword' | 'hybrid'
    rerank: bool = False
    rewrite: bool = False  # LLM query-rewrite before retrieval
    k: int = 5
    pool: int = 20  # first-stage candidates pulled before rerank/truncate
    # Which docs_version to retrieve from; None = the whole (mixed) corpus.
    # The "1.0" default is LOAD-BEARING: every existing caller (/ask,
    # rag_search, the eval harness, the cache) keeps retrieving from an
    # identical candidate set after the v0.2 corpus lands, so the published
    # Phase 1 numbers survive the corpus doubling by construction. Only a
    # caller that explicitly opts into None (or "0.2") sees the harder pool.
    version: str | None = "1.0"


# The three configs Phase 1's DoD requires comparing.
BASELINE = RagConfig(name="baseline", method="vector", rerank=False)
HYBRID = RagConfig(name="hybrid", method="hybrid", rerank=False)
HYBRID_RERANK = RagConfig(name="hybrid+rerank", method="hybrid", rerank=True)
# Enhancement: rewrite the query first, then hybrid + rerank.
HYBRID_RERANK_REWRITE = RagConfig(
    name="hybrid+rerank+rewrite", method="hybrid", rerank=True, rewrite=True
)
CONFIGS = [BASELINE, HYBRID, HYBRID_RERANK, HYBRID_RERANK_REWRITE]


@dataclass
class RetrievalTrace:
    """Everything the pipeline computed on the way to its final k results.

    The backend already produces all of this per question (both search
    rankings, RRF fusion over the pool, a cross-encoder score per candidate)
    and then discards it. The trace captures it so the UI can show the work —
    without touching what any existing caller receives.
    """

    query: str
    rewritten_query: str | None  # set iff the rewrite step ran
    pool: list[dict]  # serialized Results in PRE-rerank (fused/hybrid) order
    final_ids: list[int]  # chunk_ids in POST-rerank order (len == k)
    timings_ms: dict  # {"retrieve": float, "rerank": float | None}


def _pool_entry(r: Result) -> dict:
    """Serialize one pool member for the trace: identity + every score.

    `content` is deliberately excluded — the inspector renders titles and
    scores, and shipping ~20 x ~2000 chars of passage text per tool call
    over SSE would be pure waste.
    """
    m = r.metadata or {}
    return {
        "chunk_id": r.chunk_id,
        "page_title": m.get("page_title"),
        "heading": m.get("heading"),
        "source_url": m.get("source_url"),
        "vector_rank": r.vector_rank,
        "vector_score": r.vector_score,
        "keyword_rank": r.keyword_rank,
        "keyword_score": r.keyword_score,
        "rrf_score": r.rrf_score,
        "rerank_score": r.rerank_score,
    }


def retrieve_with_trace(query: str, cfg: RagConfig) -> tuple[list[Result], RetrievalTrace]:
    """retrieve(), but also returning the intermediate state as a RetrievalTrace.

    Behaviour-identical to the pre-trace retrieve() for every config shape;
    retrieve() below is now just this function with the trace discarded.
    """
    original_query = query
    rewritten: str | None = None
    if cfg.rewrite:
        query = rewrite_query(query)
        rewritten = query

    first_n = cfg.pool if cfg.rerank else cfg.k
    t0 = time.perf_counter()
    if cfg.method == "vector":
        pool = vector_search(query, first_n, version=cfg.version)
    elif cfg.method == "keyword":
        pool = keyword_search(query, first_n, version=cfg.version)
    else:
        # Call rrf_fuse directly instead of hybrid_search so the trace keeps
        # the full PRE-truncation fused pool (hybrid_search cuts it to k and
        # the discarded tail would be unrecoverable).
        pool = rrf_fuse(
            vector_search(query, cfg.pool, version=cfg.version),
            keyword_search(query, cfg.pool, version=cfg.version),
        )
    retrieve_ms = (time.perf_counter() - t0) * 1000.0

    # HAZARD (see tests/test_trace.py): rrf_fuse and rerank() mutate the same
    # shared Result objects — rerank() writes rerank_score in place and returns
    # them reordered. So: freeze the pool ORDER now (shallow list copy taken
    # before rerank), but serialize AFTER rerank, so the trace shows pre-rerank
    # order carrying post-rerank scores. Snapshotting dicts here instead would
    # silently miss every rerank_score; serializing the reranked list would
    # silently lose the fused order.
    pool_snapshot = list(pool)

    rerank_ms: float | None = None
    if cfg.rerank:
        t1 = time.perf_counter()
        final = rerank(query, pool[:first_n], cfg.k)
        rerank_ms = (time.perf_counter() - t1) * 1000.0
    else:
        final = pool[:first_n][: cfg.k]

    trace = RetrievalTrace(
        query=original_query,
        rewritten_query=rewritten,
        pool=[_pool_entry(r) for r in pool_snapshot],
        final_ids=[r.chunk_id for r in final],
        timings_ms={"retrieve": round(retrieve_ms, 1),
                    "rerank": round(rerank_ms, 1) if rerank_ms is not None else None},
    )
    return final, trace


def retrieve(query: str, cfg: RagConfig) -> list[Result]:
    return retrieve_with_trace(query, cfg)[0]


def answer_question(
    query: str, cfg: RagConfig = HYBRID_RERANK, *, use_cache: bool = False
) -> Answer:
    if use_cache:
        from app import cache

        hit = cache.get(query)
        if hit is not None:
            return hit
        ans = generate(query, retrieve(query, cfg))
        if ans.text:
            cache.put(query, ans)
        return ans
    return generate(query, retrieve(query, cfg))
