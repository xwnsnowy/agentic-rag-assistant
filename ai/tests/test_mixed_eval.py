"""The mixed-corpus eval condition must stay honest by construction.

- The unfiltered config really is unfiltered (version=None) and really is plain
  hybrid: with the Cohere key dead, a row labelled `hybrid+rerank` would claim a
  rerank that never happened.
- The published markdown must say "retrieval-only" and carry corpus provenance,
  so the file cannot be mistaken for the judged flagship table.

Pure tests — the renderer is exercised with a fixture summary, no DB.
"""

from eval.harness import DEFAULT_CONFIGS, MIXED
from scripts.run_mixed_eval import render


def test_mixed_config_is_unfiltered_plain_hybrid():
    assert MIXED.version is None
    assert MIXED.method == "hybrid"
    assert MIXED.rerank is False
    assert "mixed" in MIXED.name
    assert "rerank" not in MIXED.name


def test_mixed_config_is_part_of_the_default_comparison():
    assert MIXED in DEFAULT_CONFIGS


def _summary() -> dict:
    def row(name, version, hit, mrr, prec, v02):
        return {
            "name": name,
            "version": version,
            "hit": hit,
            "mrr": mrr,
            "precision": prec,
            "latency_ms": 1000.0,
            "v02_in_topk": v02,
        }

    return {
        "k": 5,
        "embedding": "real",
        "judged": False,
        "n_answerable": 44,
        "n_negative": 6,
        "corpus": {"0.2": 154, "1.0": 244},
        "reports": [
            row("hybrid", "1.0", 0.977, 0.913, 0.632, 0.0),
            row("hybrid (mixed corpus)", None, 0.9, 0.8, 0.5, 1.2),
        ],
    }


def test_render_marks_the_run_retrieval_only_and_rerank_inactive():
    md = render(_summary())
    assert "Retrieval-only" in md
    assert "Reranking was inactive" in md


def test_render_carries_corpus_provenance_and_both_rows():
    md = render(_summary())
    assert "v0.2: 154 chunks" in md
    assert "v1.0: 244 chunks" in md
    assert "| hybrid |" in md
    assert "| hybrid (mixed corpus) |" in md
    assert "none (mixed)" in md


def test_render_reports_the_delta_between_filtered_and_mixed():
    md = render(_summary())
    assert "## Delta" in md
    assert "0.977 → 0.900 (-0.077)" in md
    assert "1.20 of 5" in md
