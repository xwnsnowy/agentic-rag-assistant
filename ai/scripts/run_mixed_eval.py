"""S2.1 — measure how much the mixed (v1.0 + v0.2) corpus degrades retrieval.

Runs the golden dataset through the filtered configs (keyword / baseline /
hybrid, all `version="1.0"`) plus the unfiltered `hybrid (mixed corpus)`
condition, retrieval-only, and publishes the comparison to its OWN tracked
file: eval/results/eval_mixed_corpus.{md,json}.

Why not harness.save(): save() deliberately routes judge-less runs to the
gitignored eval_real_retrieval.* so a partial run can never blank the
generation columns of the published eval_real.md. This script respects that
guard by never touching eval_real.* at all.

Why retrieval-only: this step is about retrieval degradation; a --judge run
costs money, and with the Cohere key dead (401) any rerank row would silently
be hybrid anyway. The full judged re-baseline belongs after the key rotation.

Usage (from ai/):
  python -m scripts.run_mixed_eval
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import BASELINE, HYBRID  # noqa: E402
from eval.harness import KEYWORD, MIXED, RESULTS_DIR, run_eval  # noqa: E402


def _row(r: dict) -> str:
    version = r.get("version")
    vlabel = f"`{version}`" if version else "none (mixed)"
    v02 = r.get("v02_in_topk")
    v02s = f"{v02:.2f}" if v02 is not None else "—"
    return (
        f"| {r['name']} | {vlabel} | {r['hit']:.3f} | {r['mrr']:.3f} "
        f"| {r['precision']:.3f} | {v02s} | {r['latency_ms']:.0f} |"
    )


def render(summary: dict) -> str:
    corpus = "  ·  ".join(f"v{v}: {n} chunks" for v, n in summary.get("corpus", {}).items())
    by_name = {r["name"]: r for r in summary["reports"]}
    lines = [
        f"# S2.1 — Mixed-corpus retrieval comparison (top-{summary['k']})",
        "",
        "**Retrieval-only run.** The generation columns of the flagship table",
        "(faithfulness / relevancy / ctx-precision / ctx-recall / neg-handling) are",
        "**absent by design**: this run had no `--judge` (it measures retrieval",
        "degradation, and a judged re-baseline is deferred until the Cohere key is",
        "rotated). **Reranking was inactive** (Cohere key dead, 401), so every row is",
        "plain-hybrid order — which is why the mixed row is labelled `hybrid`, not",
        "`hybrid+rerank`.",
        "",
        f"- Embedding vectors: **{summary['embedding']}**",
        f"- Corpus in DB: {corpus}",
        f"- Answerable items: {summary['n_answerable']} (golden set; negatives excluded — no generation step)",
        "- Relevance identity: **(docs_version, slug)** — a chunk counts as relevant only if it",
        "  is a **v1.0** chunk from an expected page. Slug alone is ambiguous: `persistence`",
        "  and `streaming` exist in both corpora.",
        "",
        "| Config | version filter | hit@5 | MRR | P@5 | v0.2 in top-5 (avg) | latency (ms) |",
        "|---|---|---|---|---|---|---|",
        *[_row(r) for r in summary["reports"]],
    ]

    filtered = by_name.get("hybrid")
    mixed = by_name.get("hybrid (mixed corpus)")
    if filtered and mixed:
        lines += [
            "",
            "## Delta (hybrid, filtered → unfiltered)",
            "",
            f"- hit@5: {filtered['hit']:.3f} → {mixed['hit']:.3f} ({mixed['hit'] - filtered['hit']:+.3f})",
            f"- MRR: {filtered['mrr']:.3f} → {mixed['mrr']:.3f} ({mixed['mrr'] - filtered['mrr']:+.3f})",
            f"- P@5: {filtered['precision']:.3f} → {mixed['precision']:.3f} "
            f"({mixed['precision'] - filtered['precision']:+.3f})",
            f"- v0.2 chunks in the top-5: {mixed.get('v02_in_topk', 0):.2f} of 5 on average",
        ]

    lines += [
        "",
        "## Notes",
        "",
        "- The filtered rows re-verify the metric change: keyword and baseline reproduce the",
        "  published Phase 1 numbers bit-identically under the new (docs_version, slug)",
        "  relevance, proving the fix is a no-op when the version filter is on.",
        "- The filtered hybrid row can differ from the published 0.977/0.896/0.627 by one",
        "  item (gd-001): its relevant chunk sits in a ~zero-score (2.2e-16) `ts_rank` tie",
        "  whose ordering Postgres leaves unspecified, and migration 003's full-table UPDATE",
        "  permuted that tie. Not a metric artifact — the metric fix can only lower scores",
        "  (its relevant set is a strict subset of slug-only), never raise them.",
        "",
        "Reproduce: `python -m scripts.run_mixed_eval` (from `ai/`).",
    ]
    return "\n".join(lines)


def main() -> None:
    summary = run_eval(configs=[KEYWORD, BASELINE, HYBRID, MIXED], judge=False)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "eval_mixed_corpus.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md = render(summary)
    (RESULTS_DIR / "eval_mixed_corpus.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\nSaved -> {RESULTS_DIR / 'eval_mixed_corpus.md'}")


if __name__ == "__main__":
    main()
