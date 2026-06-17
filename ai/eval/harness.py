"""Eval harness: run each RagConfig over the golden dataset and tabulate.

Retrieval metrics run always (keyword gives real numbers even before a real
embedding key). Generation metrics (faithfulness / relevancy via LLM-judge) run
only with --judge AND an OpenRouter key. Results are printed and written to
eval/results/ so the comparison table is reproducible.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.generation import generate
from app.pipeline import CONFIGS, RagConfig, retrieve
from eval import judge as judge_mod
from eval.metrics import hit_at_k, precision_at_k, reciprocal_rank

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "golden_dataset_langgraph.json"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "eval" / "results"

# Add a pure-keyword config so there is at least one fully-meaningful column
# before a real embedding key lands.
KEYWORD = RagConfig(name="keyword", method="keyword", rerank=False)
DEFAULT_CONFIGS = [KEYWORD, *CONFIGS]


@dataclass
class ConfigReport:
    name: str
    hit: float
    mrr: float
    precision: float
    latency_ms: float
    faithfulness: float | None = None
    relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    abstention: float | None = None  # fraction of negatives correctly handled


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def run_eval(configs=DEFAULT_CONFIGS, k: int = 5, judge: bool = False) -> dict:
    settings = get_settings()
    real_embed = bool(settings.embedding_api_key)
    can_judge = judge and bool(settings.openrouter_api_key)

    items = json.loads(DATASET.read_text(encoding="utf-8"))["items"]
    answerable = [i for i in items if i.get("expected_slugs")]
    negatives = [i for i in items if not i.get("expected_slugs")]

    reports: list[ConfigReport] = []
    for cfg in configs:
        hits, rrs, precs, lats = [], [], [], []
        faiths, relevs, ctxps, ctxrs, abstains = [], [], [], [], []

        for item in answerable:
            try:
                t0 = time.perf_counter()
                results = retrieve(item["question"], RagConfig(**{**cfg.__dict__, "k": k}))
                lats.append((time.perf_counter() - t0) * 1000)
                exp = item["expected_slugs"]
                hits.append(hit_at_k(results, exp))
                rrs.append(reciprocal_rank(results, exp))
                precs.append(precision_at_k(results, exp))

                if can_judge:
                    ans = generate(item["question"], results)
                    ctx = "\n\n".join(r.content for r in results)
                    v = judge_mod.judge_answer(item["question"], item["ground_truth"], ans.text or "", ctx)
                    if v.get("faithfulness") is not None:
                        faiths.append(float(v["faithfulness"]))
                    if v.get("answer_relevancy") is not None:
                        relevs.append(float(v["answer_relevancy"]))
                    if v.get("context_precision") is not None:
                        ctxps.append(float(v["context_precision"]))
                    if v.get("context_recall") is not None:
                        ctxrs.append(float(v["context_recall"]))
            except Exception as exc:  # noqa: BLE001 - skip on transient errors, don't crash the run
                print(f"  [skip] {cfg.name}/{item['id']}: {type(exc).__name__}")

        if can_judge:
            for item in negatives:
                try:
                    results = retrieve(item["question"], RagConfig(**{**cfg.__dict__, "k": k}))
                    ans = generate(item["question"], results)
                    handled = judge_mod.judge_negative(item["question"], ans.text or "")
                    abstains.append(1.0 if handled else 0.0)
                except Exception as exc:  # noqa: BLE001
                    print(f"  [skip] {cfg.name}/{item['id']}: {type(exc).__name__}")

        reports.append(
            ConfigReport(
                name=cfg.name,
                hit=_mean(hits),
                mrr=_mean(rrs),
                precision=_mean(precs),
                latency_ms=_mean(lats),
                faithfulness=_mean(faiths) if faiths else None,
                relevancy=_mean(relevs) if relevs else None,
                context_precision=_mean(ctxps) if ctxps else None,
                context_recall=_mean(ctxrs) if ctxrs else None,
                abstention=_mean(abstains) if abstains else None,
            )
        )

    return {
        "k": k,
        "embedding": "real" if real_embed else "FAKE (offline)",
        "judged": can_judge,
        "n_answerable": len(answerable),
        "n_negative": len(negatives),
        "reports": [r.__dict__ for r in reports],
    }


def render_markdown(summary: dict) -> str:
    lines = [
        f"# Eval results (top-{summary['k']})",
        "",
        f"- Embedding vectors: **{summary['embedding']}**"
        + ("" if summary["embedding"] == "real" else "  ← vector/hybrid columns are placeholders until a real key lands"),
        f"- LLM-judge: **{'on' if summary['judged'] else 'off'}**  ·  answerable items: {summary['n_answerable']}  ·  negatives: {summary['n_negative']}",
        "",
        "| Config | hit@k | MRR | P@k | latency (ms) | faithfulness | relevancy | ctx-prec | ctx-recall | neg-handling |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def fmt(x):
        return "—" if x is None else f"{x:.3f}"

    for r in summary["reports"]:
        lines.append(
            f"| {r['name']} | {r['hit']:.3f} | {r['mrr']:.3f} | {r['precision']:.3f} "
            f"| {r['latency_ms']:.0f} | {fmt(r['faithfulness'])} | {fmt(r['relevancy'])} "
            f"| {fmt(r['context_precision'])} | {fmt(r['context_recall'])} | {fmt(r['abstention'])} |"
        )
    return "\n".join(lines)


def save(summary: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tag = "real" if summary["embedding"] == "real" else "fake"
    (RESULTS_DIR / f"eval_{tag}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md = render_markdown(summary)
    (RESULTS_DIR / f"eval_{tag}.md").write_text(md, encoding="utf-8")
    return RESULTS_DIR / f"eval_{tag}.md"
