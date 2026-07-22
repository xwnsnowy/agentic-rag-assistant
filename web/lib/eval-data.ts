// Eval numbers surfaced in the in-app dashboard. Source of truth is the committed
// results under ai/eval/results/ (run `python -m scripts.run_eval --judge` etc.).
// Kept as a small static snapshot so the dashboard needs no backend.

export const RETRIEVAL_COLS = [
  "Config",
  "hit@5",
  "MRR",
  "P@5",
  "faith.",
  "ctx-prec",
  "ctx-recall",
  "latency",
] as const;

export const RETRIEVAL_ROWS: {
  config: string;
  best?: boolean;
  values: (string | number)[];
}[] = [
  { config: "keyword", values: [0.386, 0.33, 0.298, 0.43, 0.43, 0.42, "429ms"] },
  { config: "baseline (vector)", values: [0.977, 0.902, 0.627, 0.9, 0.89, 0.88, "1422ms"] },
  { config: "hybrid (RRF)", values: [0.977, 0.896, 0.627, 0.9, 0.9, 0.89, "2028ms"] },
  { config: "hybrid + rerank", best: true, values: [1.0, 0.928, 0.727, 0.92, 0.92, 0.91, "3001ms"] },
  // Stage 2 harder condition — ai/eval/results/eval_mixed_corpus.json.
  // Retrieval-only run (no judge, rerank inactive), hence "—" generation columns.
  { config: "hybrid (mixed corpus, unfiltered)", values: [0.909, 0.647, 0.345, "—", "—", "—", "2224ms"] },
];

// One-line reading of the mixed-corpus row, shown under the table.
export const MIXED_CORPUS_NOTE =
  "Stage 2 deliberately made the problem harder: with the deprecated v0.2 docs in the same index and no version filter, 2.6 of the top-5 chunks on average come from the wrong version — MRR falls 0.91 → 0.65 and P@5 0.63 → 0.35. Version-filtered retrieval (all other rows) recovers the published quality. Retrieval-only run: no LLM-judge, reranking inactive.";

export const RAGAS = [
  { label: "faithfulness", value: 0.934 },
  { label: "answer relevancy", value: 0.823 },
  { label: "context precision", value: 0.885 },
  { label: "context recall", value: 0.843 },
];

export const HEADLINE = [
  { label: "Tool-selection accuracy", value: "1.000", sub: "agent, 17-item + off-domain" },
  { label: "Prompt-injection resistance", value: "1.000", sub: "8 attacks, 0 leaks" },
  { label: "Negative-trap handling", value: "1.000", sub: "no hallucinated APIs" },
  { label: "Semantic cache speed-up", value: "13×", sub: "repeat questions" },
];

export const META =
  "Measured on a 50-item golden set (44 answerable + 6 traps) · real text-embedding-3-small vectors · gpt-4o-mini LLM-judge. Retrieval metrics also corroborated by the real Ragas library.";
