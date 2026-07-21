"""Unit tests for citation capture + [n] marker mapping.

Covers both halves of the mechanism:
  - app/tools.py : rag_search numbers passages globally across calls within a
    turn and stashes structured sources in a contextvar sink
  - app/agent.py : _citations_for maps the answer's inline [n] markers back
    onto those sources (dedup, sorted, out-of-range ignored)

Pure: retrieval is monkeypatched, so no DB / embeddings / API keys.
"""

import app.tools as tools_mod
from app.agent import _citations_for
from app.retrieval import Result
from app.tools import begin_citation_capture, rag_search


def _sink_entry(n: int) -> dict:
    return {
        "n": n,
        "chunk_id": 100 + n,
        "page_title": f"Page {n}",
        "heading": f"Heading {n}",
        "source_url": f"https://example.com/p{n}",
    }


def test_markers_map_to_matching_sink_entries():
    sink = [_sink_entry(n) for n in range(1, 6)]
    answer = "Use add_edge [2]. Compile the graph [5]."
    cites = _citations_for(answer, sink)
    assert [c["n"] for c in cites] == [2, 5]
    assert cites[0]["source_url"] == "https://example.com/p2"
    assert cites[1]["chunk_id"] == 105


def test_out_of_range_marker_is_ignored():
    sink = [_sink_entry(n) for n in range(1, 4)]
    cites = _citations_for("Real [1], phantom [9].", sink)
    assert [c["n"] for c in cites] == [1]


def test_markers_are_deduped_and_ordered():
    sink = [_sink_entry(n) for n in range(1, 6)]
    cites = _citations_for("See [3], then [1], then [3] again [1].", sink)
    assert [c["n"] for c in cites] == [1, 3]  # deduped, ascending


def test_empty_sink_or_unmarked_answer_yields_no_citations():
    assert _citations_for("Anything [1]", []) == []
    assert _citations_for("No markers here.", [_sink_entry(1)]) == []
    assert _citations_for("", [_sink_entry(1)]) == []


# --- rag_search side: global numbering + sink capture -----------------------


def _fake_results(ids: list[int]) -> list[Result]:
    return [
        Result(
            chunk_id=i,
            content=f"passage-{i}",
            metadata={
                "page_title": f"Page {i}",
                "heading": f"H{i}",
                "source_url": f"https://example.com/c{i}",
            },
        )
        for i in ids
    ]


def test_rag_search_numbers_globally_across_calls_and_fills_sink(monkeypatch):
    calls = iter([_fake_results([10, 11]), _fake_results([12])])
    monkeypatch.setattr(tools_mod, "retrieve", lambda q, cfg: next(calls))

    sink = begin_citation_capture()
    out1 = rag_search.invoke({"query": "first"})
    out2 = rag_search.invoke({"query": "second"})

    # First call numbers [1][2]; second continues at [3] — never restarts.
    assert "[1] Page 10" in out1 and "[2] Page 11" in out1
    assert "[3] Page 12" in out2 and "[1]" not in out2

    assert [s["n"] for s in sink] == [1, 2, 3]
    assert [s["chunk_id"] for s in sink] == [10, 11, 12]
    assert sink[2]["source_url"] == "https://example.com/c12"

    # End-to-end: an answer citing [2] resolves to chunk 11's source.
    cites = _citations_for("As shown in [2].", sink)
    assert [c["chunk_id"] for c in cites] == [11]


def test_rag_search_without_capture_numbers_from_one(monkeypatch):
    monkeypatch.setattr(tools_mod, "retrieve", lambda q, cfg: _fake_results([42]))
    # Standalone path (MCP server / direct call): no sink, numbering restarts at 1.
    tools_mod._citation_sink.set(None)
    out = rag_search.invoke({"query": "standalone"})
    assert out.startswith("[1] Page 42")


def test_rag_search_empty_results_message(monkeypatch):
    monkeypatch.setattr(tools_mod, "retrieve", lambda q, cfg: [])
    assert rag_search.invoke({"query": "nothing"}) == (
        "No relevant passages found in the LangGraph documentation."
    )
