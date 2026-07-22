# S2.1 — Mixed-corpus retrieval comparison (top-5)

**Retrieval-only run.** The generation columns of the flagship table
(faithfulness / relevancy / ctx-precision / ctx-recall / neg-handling) are
**absent by design**: this run had no `--judge` (it measures retrieval
degradation, and a judged re-baseline is deferred until the Cohere key is
rotated). **Reranking was inactive** (Cohere key dead, 401), so every row is
plain-hybrid order — which is why the mixed row is labelled `hybrid`, not
`hybrid+rerank`.

- Embedding vectors: **real**
- Corpus in DB: v0.2: 154 chunks  ·  v1.0: 244 chunks
- Answerable items: 44 (golden set; negatives excluded — no generation step)
- Relevance identity: **(docs_version, slug)** — a chunk counts as relevant only if it
  is a **v1.0** chunk from an expected page. Slug alone is ambiguous: `persistence`
  and `streaming` exist in both corpora.

| Config | version filter | hit@5 | MRR | P@5 | v0.2 in top-5 (avg) | latency (ms) |
|---|---|---|---|---|---|---|
| keyword | `1.0` | 0.386 | 0.330 | 0.298 | 0.00 | 461 |
| baseline | `1.0` | 0.977 | 0.902 | 0.627 | 0.00 | 1859 |
| hybrid | `1.0` | 0.977 | 0.913 | 0.632 | 0.00 | 2226 |
| hybrid (mixed corpus) | none (mixed) | 0.909 | 0.647 | 0.345 | 2.64 | 2224 |

## Delta (hybrid, filtered → unfiltered)

- hit@5: 0.977 → 0.909 (-0.068)
- MRR: 0.913 → 0.647 (-0.266)
- P@5: 0.632 → 0.345 (-0.286)
- v0.2 chunks in the top-5: 2.64 of 5 on average

## Notes

- The filtered rows re-verify the metric change: keyword and baseline reproduce the
  published Phase 1 numbers bit-identically under the new (docs_version, slug)
  relevance, proving the fix is a no-op when the version filter is on.
- The filtered hybrid row can differ from the published 0.977/0.896/0.627 by one
  item (gd-001): its relevant chunk sits in a ~zero-score (2.2e-16) `ts_rank` tie
  whose ordering Postgres leaves unspecified, and migration 003's full-table UPDATE
  permuted that tie. Not a metric artifact — the metric fix can only lower scores
  (its relevant set is a strict subset of slug-only), never raise them.

Reproduce: `python -m scripts.run_mixed_eval` (from `ai/`).