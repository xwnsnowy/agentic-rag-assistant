"""Pure tests for docs_version filtering (no DB).

The contract S2.0 depends on:
  - _version_predicate emits the WHERE fragment when a version is set and
    NOTHING when version is None (None = search the whole mixed corpus);
  - RagConfig defaults to version="1.0" — the load-bearing default that keeps
    every existing caller (/ask, rag_search, eval, cache) on an identical
    candidate set after the v0.2 corpus lands, so the published Phase 1
    numbers survive the corpus doubling by construction;
  - the pipeline actually forwards cfg.version into both searches.
"""

from app.pipeline import (
    BASELINE,
    HYBRID,
    HYBRID_RERANK,
    HYBRID_RERANK_REWRITE,
    RagConfig,
    retrieve,
)
from app.retrieval import _version_predicate
from tests.test_trace import _install_searches


def test_predicate_included_when_version_set():
    pred, params = _version_predicate("1.0")
    assert pred == "docs_version = %s"
    assert params == ("1.0",)
    pred, params = _version_predicate("0.2")
    assert params == ("0.2",)


def test_predicate_omitted_when_version_none():
    pred, params = _version_predicate(None)
    assert pred == ""
    assert params == ()


def test_ragconfig_defaults_to_v1():
    assert RagConfig(name="x").version == "1.0"
    # Every published config keeps the v1.0 candidate set.
    for cfg in (BASELINE, HYBRID, HYBRID_RERANK, HYBRID_RERANK_REWRITE):
        assert cfg.version == "1.0", cfg.name


def test_pipeline_forwards_version_to_both_searches(monkeypatch):
    seen: dict = {}
    _install_searches(monkeypatch, seen)
    retrieve("q", RagConfig(name="t", method="hybrid"))
    assert seen["versions"] == ["1.0", "1.0"]  # vector + keyword, both filtered

    seen.clear()
    retrieve("q", RagConfig(name="t", method="hybrid", version=None))
    assert seen["versions"] == [None, None]  # explicit opt-out: mixed corpus

    seen.clear()
    retrieve("q", RagConfig(name="t", method="vector", version="0.2"))
    assert seen["versions"] == ["0.2"]
