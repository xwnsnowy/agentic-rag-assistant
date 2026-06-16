"""End-to-end RAG pipeline + the configs the eval harness compares.

RagConfig captures one retrieval strategy so the eval can run the SAME queries
through baseline vs hybrid vs hybrid+rerank and tabulate the difference.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.generation import Answer, generate
from app.rerank import rerank
from app.retrieval import Result, hybrid_search, keyword_search, vector_search


@dataclass
class RagConfig:
    name: str
    method: str = "hybrid"  # 'vector' | 'keyword' | 'hybrid'
    rerank: bool = False
    k: int = 5
    pool: int = 20  # first-stage candidates pulled before rerank/truncate


# The three configs Phase 1's DoD requires comparing.
BASELINE = RagConfig(name="baseline", method="vector", rerank=False)
HYBRID = RagConfig(name="hybrid", method="hybrid", rerank=False)
HYBRID_RERANK = RagConfig(name="hybrid+rerank", method="hybrid", rerank=True)
CONFIGS = [BASELINE, HYBRID, HYBRID_RERANK]


def retrieve(query: str, cfg: RagConfig) -> list[Result]:
    first_n = cfg.pool if cfg.rerank else cfg.k
    if cfg.method == "vector":
        results = vector_search(query, first_n)
    elif cfg.method == "keyword":
        results = keyword_search(query, first_n)
    else:
        results = hybrid_search(query, first_n, pool=cfg.pool)

    if cfg.rerank:
        return rerank(query, results, cfg.k)
    return results[: cfg.k]


def answer_question(query: str, cfg: RagConfig = HYBRID_RERANK) -> Answer:
    return generate(query, retrieve(query, cfg))
