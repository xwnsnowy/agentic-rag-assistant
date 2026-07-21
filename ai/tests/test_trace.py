"""Unit tests for the S1.1 retrieval trace (app/pipeline.py + app/tools.py).

Pure: vector_search / keyword_search are monkeypatched on app.pipeline, and the
Cohere HTTP call is faked at app.rerank._post_with_backoff so the REAL rerank()
body runs (that is what proves the top_n=len(pool) change scores everything).
No DB, no network, no keys.

The central hazard under test: rrf_fuse and rerank() mutate the SAME shared
Result objects (keyword ranks, rrf_score, rerank_score are written in place,
and rerank returns them reordered). retrieve_with_trace must therefore freeze
the pool ORDER before rerank but read the SCORES after it — get that ordering
wrong and the trace looks plausible while silently showing post-rerank state
as "pre-rerank", or all-None rerank scores.
"""

from types import SimpleNamespace

import app.rerank as rerank_mod
import app.pipeline as pipeline_mod
import app.tools as tools_mod
from app.pipeline import RagConfig, RetrievalTrace, retrieve, retrieve_with_trace
from app.retrieval import Result
from app.tools import begin_citation_capture, begin_debug_capture, rag_search

# --- fixtures ---------------------------------------------------------------
# vec [1,2,3,4] + kw [3,5,2,6]  =>  fused order [3, 2, 1, 5, 4, 6]
# (3 and 2 are in both lists; 4/6 tie and keep insertion order).
_VEC_IDS = [1, 2, 3, 4]
_KW_IDS = [3, 5, 2, 6]
_FUSED_ORDER = [3, 2, 1, 5, 4, 6]

# Fake cross-encoder relevance, keyed by content. Deliberately DISAGREES with
# the fused order (6 is last in fusion, first here) so pre- vs post-rerank
# order genuinely differ.
_RELEVANCE = {
    "content-6": 0.9, "content-1": 0.8, "content-5": 0.7,
    "content-3": 0.6, "content-2": 0.5, "content-4": 0.4,
}


def _result(chunk_id: int, *, vrank=None, krank=None) -> Result:
    return Result(
        chunk_id=chunk_id,
        content=f"content-{chunk_id}",
        metadata={
            "page_title": f"Page {chunk_id}",
            "heading": f"H{chunk_id}",
            "source_url": f"https://example.com/c{chunk_id}",
        },
        vector_rank=vrank,
        keyword_rank=krank,
        vector_score=(1.0 - vrank * 0.01) if vrank else None,
        keyword_score=(0.9 - krank * 0.01) if krank else None,
    )


def _install_searches(monkeypatch, seen: dict | None = None):
    """Fake vector/keyword search returning FRESH Result objects on every call
    (fusion mutates its inputs, so shared fixtures would leak state between
    calls and between tests)."""

    def fake_vector(query, k, *, version=None):
        if seen is not None:
            seen.setdefault("vector_queries", []).append(query)
            seen.setdefault("versions", []).append(version)
        return [_result(cid, vrank=i + 1) for i, cid in enumerate(_VEC_IDS[:k])]

    def fake_keyword(query, k, *, version=None):
        if seen is not None:
            seen.setdefault("keyword_queries", []).append(query)
            seen.setdefault("versions", []).append(version)
        return [_result(cid, krank=i + 1) for i, cid in enumerate(_KW_IDS[:k])]

    monkeypatch.setattr(pipeline_mod, "vector_search", fake_vector)
    monkeypatch.setattr(pipeline_mod, "keyword_search", fake_keyword)


class _FakeResp:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _install_cohere(monkeypatch, captured_payloads: list):
    """Fake the HTTP layer only, so the real rerank() body (top_n, score
    assignment, truncation) is exercised. Mimics Cohere v2/rerank: results
    sorted by relevance desc, truncated to top_n, one entry per scored doc."""
    monkeypatch.setattr(
        rerank_mod, "get_settings",
        lambda: SimpleNamespace(cohere_api_key="test-key", rerank_model="rerank-test"),
    )

    def fake_post(settings, payload):
        captured_payloads.append(payload)
        items = [
            {"index": i, "relevance_score": _RELEVANCE[doc]}
            for i, doc in enumerate(payload["documents"])
        ]
        items.sort(key=lambda it: it["relevance_score"], reverse=True)
        return _FakeResp({"results": items[: payload["top_n"]]})

    monkeypatch.setattr(rerank_mod, "_post_with_backoff", fake_post)


_HYBRID_RERANK_CFG = RagConfig(name="t-hr", method="hybrid", rerank=True, k=3, pool=10)


# --- the mutation/ordering hazard ------------------------------------------


def test_pool_is_pre_rerank_order_final_ids_are_post_rerank_and_they_differ(monkeypatch):
    _install_searches(monkeypatch)
    _install_cohere(monkeypatch, [])

    results, trace = retrieve_with_trace("q", _HYBRID_RERANK_CFG)

    pool_ids = [p["chunk_id"] for p in trace.pool]
    assert pool_ids == _FUSED_ORDER  # fused/hybrid order, NOT rerank order
    assert trace.final_ids == [6, 1, 5]  # top-3 by fake cross-encoder
    assert trace.final_ids == [r.chunk_id for r in results]
    assert pool_ids[: len(trace.final_ids)] != trace.final_ids  # rerank moved things


def test_every_pool_entry_has_rrf_score_and_after_rerank_a_rerank_score(monkeypatch):
    """Proves the top_n=len(pool) change: pre-change, only the final k=3 would
    carry a rerank_score; now all 6 pool members must."""
    payloads: list = []
    _install_searches(monkeypatch)
    _install_cohere(monkeypatch, payloads)

    _, trace = retrieve_with_trace("q", _HYBRID_RERANK_CFG)

    assert len(trace.pool) == 6
    assert all(p["rrf_score"] is not None for p in trace.pool)
    assert all(p["rerank_score"] is not None for p in trace.pool)
    # rerank() asked Cohere to score the whole pool, not just top_k.
    assert payloads[0]["top_n"] == len(payloads[0]["documents"]) == 6
    # And the scores are the per-document ones, attached to the right chunks.
    by_id = {p["chunk_id"]: p for p in trace.pool}
    assert by_id[6]["rerank_score"] == 0.9
    assert by_id[4]["rerank_score"] == 0.4


def test_pool_entries_have_no_content_and_exactly_the_documented_keys(monkeypatch):
    _install_searches(monkeypatch)
    _install_cohere(monkeypatch, [])

    _, trace = retrieve_with_trace("q", _HYBRID_RERANK_CFG)

    expected_keys = {
        "chunk_id", "page_title", "heading", "source_url",
        "vector_rank", "vector_score", "keyword_rank", "keyword_score",
        "rrf_score", "rerank_score",
    }
    for entry in trace.pool:
        assert set(entry) == expected_keys
        assert "content" not in entry


# --- every config shape -----------------------------------------------------

_ALL_CFGS = [
    RagConfig(name="keyword", method="keyword", rerank=False),
    RagConfig(name="baseline", method="vector", rerank=False),
    RagConfig(name="hybrid", method="hybrid", rerank=False),
    RagConfig(name="hybrid+rerank", method="hybrid", rerank=True),
    RagConfig(name="hybrid+rerank+rewrite", method="hybrid", rerank=True, rewrite=True),
]


def test_retrieve_returns_exactly_retrieve_with_trace_first_element(monkeypatch):
    _install_searches(monkeypatch)
    _install_cohere(monkeypatch, [])
    monkeypatch.setattr(pipeline_mod, "rewrite_query", lambda q: f"{q} (rewritten)")

    for cfg in _ALL_CFGS:
        via_retrieve = retrieve("q", cfg)
        via_trace, trace = retrieve_with_trace("q", cfg)
        # Full dataclass equality (ids, scores, ranks, metadata), per config.
        assert via_retrieve == via_trace, cfg.name
        assert trace.final_ids == [r.chunk_id for r in via_trace], cfg.name
        assert len(via_retrieve) <= cfg.k, cfg.name


def test_non_rerank_configs_final_ids_match_pool_head_and_no_rerank_scores(monkeypatch):
    _install_searches(monkeypatch)

    for cfg in _ALL_CFGS[:3]:  # keyword, baseline, hybrid
        results, trace = retrieve_with_trace("q", cfg)
        assert trace.final_ids == [p["chunk_id"] for p in trace.pool][: cfg.k], cfg.name
        assert all(p["rerank_score"] is None for p in trace.pool), cfg.name
        assert trace.timings_ms["rerank"] is None, cfg.name
        assert isinstance(trace.timings_ms["retrieve"], float), cfg.name
        assert trace.rewritten_query is None, cfg.name

    # Method-specific score fields: keyword pools have no rrf/vector state.
    _, kw_trace = retrieve_with_trace("q", _ALL_CFGS[0])
    assert all(p["keyword_rank"] is not None for p in kw_trace.pool)
    assert all(p["rrf_score"] is None for p in kw_trace.pool)
    # Hybrid pools all carry rrf_score even without rerank.
    _, hy_trace = retrieve_with_trace("q", _ALL_CFGS[2])
    assert all(p["rrf_score"] is not None for p in hy_trace.pool)


def test_rewrite_is_recorded_and_used_for_search(monkeypatch):
    seen: dict = {}
    _install_searches(monkeypatch, seen)
    _install_cohere(monkeypatch, [])
    monkeypatch.setattr(pipeline_mod, "rewrite_query", lambda q: f"{q} (rewritten)")

    _, trace = retrieve_with_trace("raw question", _ALL_CFGS[4])

    assert trace.query == "raw question"  # the caller's query, not the rewrite
    assert trace.rewritten_query == "raw question (rewritten)"
    assert seen["vector_queries"] == ["raw question (rewritten)"]
    assert seen["keyword_queries"] == ["raw question (rewritten)"]
    assert isinstance(trace.timings_ms["rerank"], float)


# --- rag_search + the debug sink -------------------------------------------


def _fixed_results() -> list[Result]:
    return [_result(10, vrank=1), _result(11, vrank=2)]


def _fixed_trace(query: str) -> RetrievalTrace:
    return RetrievalTrace(
        query=query,
        rewritten_query=None,
        pool=[{"chunk_id": 10}, {"chunk_id": 11}, {"chunk_id": 12}],
        final_ids=[10, 11],
        timings_ms={"retrieve": 12.5, "rerank": 3.0},
    )


def _expected_block(n: int, cid: int) -> str:
    return (
        f"[{n}] Page {cid} — H{cid}\n"
        f"URL: https://example.com/c{cid}\ncontent-{cid}"
    )


def test_rag_search_without_debug_sink_is_byte_identical_and_captures_nothing(monkeypatch):
    monkeypatch.setattr(
        tools_mod, "retrieve_with_trace", lambda q, cfg: (_fixed_results(), _fixed_trace(q))
    )
    tools_mod._citation_sink.set(None)
    tools_mod._debug_sink.set(None)

    out = rag_search.invoke({"query": "standalone"})

    # The exact pre-S1.1 return string — the frozen tool contract.
    assert out == _expected_block(1, 10) + "\n\n---\n\n" + _expected_block(2, 11)


def test_rag_search_with_debug_sink_same_string_plus_out_of_band_trace(monkeypatch):
    monkeypatch.setattr(
        tools_mod, "retrieve_with_trace", lambda q, cfg: (_fixed_results(), _fixed_trace(q))
    )
    citations = begin_citation_capture()
    debug = begin_debug_capture()

    out = rag_search.invoke({"query": "what is a reducer"})

    # In-band: byte-identical to the sink-less call above.
    assert out == _expected_block(1, 10) + "\n\n---\n\n" + _expected_block(2, 11)
    # Out-of-band: one entry per tool call, trace fields flattened in.
    assert len(debug) == 1
    entry = debug[0]
    assert entry["tool_call_query"] == "what is a reducer"
    assert entry["citation_ns"] == [1, 2]
    assert entry["query"] == "what is a reducer"
    assert entry["rewritten_query"] is None
    assert [p["chunk_id"] for p in entry["pool"]] == [10, 11, 12]
    assert entry["final_ids"] == [10, 11]
    assert entry["timings_ms"] == {"retrieve": 12.5, "rerank": 3.0}
    # Citation capture is untouched by the debug sink.
    assert [c["n"] for c in citations] == [1, 2]


def test_rag_search_debug_sink_numbers_continue_across_calls(monkeypatch):
    monkeypatch.setattr(
        tools_mod, "retrieve_with_trace", lambda q, cfg: (_fixed_results(), _fixed_trace(q))
    )
    begin_citation_capture()
    debug = begin_debug_capture()

    rag_search.invoke({"query": "first"})
    rag_search.invoke({"query": "second"})

    assert [e["citation_ns"] for e in debug] == [[1, 2], [3, 4]]
    assert [e["tool_call_query"] for e in debug] == ["first", "second"]


def test_rag_search_empty_results_still_traces_with_no_citations(monkeypatch):
    monkeypatch.setattr(tools_mod, "retrieve_with_trace", lambda q, cfg: ([], _fixed_trace(q)))
    debug = begin_debug_capture()

    out = rag_search.invoke({"query": "nothing"})

    assert out == "No relevant passages found in the LangGraph documentation."
    assert len(debug) == 1
    assert debug[0]["citation_ns"] == []
    assert debug[0]["final_ids"] == [10, 11]  # whatever the trace said
