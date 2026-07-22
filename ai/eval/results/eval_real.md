# Eval results (top-5)

- Embedding vectors: **real**
- LLM-judge: **on**  ·  answerable items: 44  ·  negatives: 6

| Config | hit@k | MRR | P@k | latency (ms) | faithfulness | relevancy | ctx-prec | ctx-recall | neg-handling |
|---|---|---|---|---|---|---|---|---|---|
| keyword | 0.386 | 0.330 | 0.298 | 429 | 0.432 | 0.455 | 0.430 | 0.416 | 1.000 |
| baseline | 0.977 | 0.902 | 0.627 | 1422 | 0.895 | 0.920 | 0.889 | 0.877 | 1.000 |
| hybrid | 0.977 | 0.896 | 0.627 | 2028 | 0.898 | 0.927 | 0.899 | 0.886 | 1.000 |
| hybrid+rerank | 1.000 | 0.928 | 0.727 | 3001 | 0.918 | 0.927 | 0.918 | 0.914 | 1.000 |

## Reproducibility note (added after this run)

These numbers were produced **before** retrieval had a deterministic tiebreaker.
`ORDER BY rank DESC` alone leaves the order of tied rows unspecified, and one golden
item (gd-001) has its relevant chunk inside a `ts_rank` tie — several rows share a
float-noise score of ~2.2e-16. A later full-table `UPDATE` (migration 003) changed
physical row order and permuted that tie, moving the **hybrid** row to
MRR **0.913** / P@5 **0.632**.

The old numbers are not wrong — they are one valid ordering of a tie SQL does not
pin. But valid is not enough: a measurement that cannot be reproduced is not a
measurement. Retrieval now breaks ties by `id`, so the ordering is stable across
runs and across database maintenance.

**A judged re-baseline of this whole table is pending** — it needs a working Cohere
key, because with the key dead every `hybrid+rerank` figure would silently collapse
onto the plain-hybrid row. Until then, the deterministic retrieval-only numbers live
in `eval_mixed_corpus.md`, and the generation columns above remain the last valid
judged measurement.