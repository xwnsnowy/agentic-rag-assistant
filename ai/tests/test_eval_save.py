"""save() must never let a partial run overwrite the published results table.

The published table (eval_real.md) carries both retrieval and generation columns.
A run without --judge can only fill the retrieval half, so if it wrote to the same
filename it would blank faithfulness/relevancy/ctx-*/neg-handling — losing numbers
that cost real API calls to produce.
"""

from eval import harness


def _summary(*, judged: bool, embedding: str = "real") -> dict:
    return {
        "k": 5,
        "embedding": embedding,
        "judged": judged,
        "n_answerable": 44,
        "n_negative": 6,
        "reports": [
            {
                "name": "hybrid+rerank",
                "hit": 1.0,
                "mrr": 0.928,
                "precision": 0.727,
                "latency_ms": 3001.0,
                "faithfulness": 0.918 if judged else None,
                "relevancy": 0.927 if judged else None,
                "context_precision": 0.918 if judged else None,
                "context_recall": 0.914 if judged else None,
                "abstention": 1.0 if judged else None,
            }
        ],
    }


def test_judged_run_writes_the_published_table(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    out = harness.save(_summary(judged=True))

    assert out.name == "eval_real.md"
    assert (tmp_path / "eval_real.json").exists()


def test_retrieval_only_run_writes_a_separate_file(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    out = harness.save(_summary(judged=False))

    assert out.name == "eval_real_retrieval.md"
    # The published table must be left untouched.
    assert not (tmp_path / "eval_real.md").exists()
    assert not (tmp_path / "eval_real.json").exists()


def test_retrieval_only_run_does_not_clobber_an_existing_published_table(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    published = tmp_path / "eval_real.md"
    published.write_text("PUBLISHED", encoding="utf-8")

    harness.save(_summary(judged=False))

    assert published.read_text(encoding="utf-8") == "PUBLISHED"


def test_fake_embedding_run_is_also_separated(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    out = harness.save(_summary(judged=False, embedding="FAKE (offline)"))

    assert out.name == "eval_fake_retrieval.md"
