# Eval

Reproducible comparison of retrieval configs over the golden dataset
([../../golden_dataset_langgraph.json](../../golden_dataset_langgraph.json)).

```bash
cd ai
python -m scripts.run_eval            # retrieval metrics only
python -m scripts.run_eval --judge    # + faithfulness/relevancy/abstention (LLM)
```

## Metrics

- **hit@k** — did any of the top-k come from an expected doc page? (slug-level relevance)
- **MRR** — 1 / rank of the first relevant chunk, averaged. Rewards ranking the right chunk high.
- **precision@k** — fraction of the top-k that are relevant.
- **faithfulness** — LLM-judge: are the answer's claims grounded in the retrieved context? (anti-hallucination)
- **answer_relevancy** — LLM-judge: does the answer address the question?
- **abstention** — on the negative trap, did the system correctly say "not in the docs"?

`hit@k` saturates when expected pages are large, so **MRR / precision@k** are the
honest retrieval signals here.

## Results (top-5, real `text-embedding-3-small` vectors, judge = gpt-4o-mini)

| Config | hit@5 | MRR | P@5 | latency (ms) | faithfulness | relevancy | abstention |
|---|---|---|---|---|---|---|---|
| keyword | 0.700 | 0.453 | 0.432 | 344 | 0.63 | 0.68 | 1.00 |
| baseline (vector) | 0.900 | **0.783** | **0.600** | 1260 | 0.81 | 0.87 | 1.00 |
| hybrid (RRF) | 0.900 | 0.758 | 0.500 | 1614 | 0.82 | 0.90 | 1.00 |
| hybrid+rerank | 0.900 | 0.758 | 0.500 | 1497 | **0.84** | **0.90** | 1.00 |

_10 answerable items + 1 negative trap. `n=11` (starter set; expanding to 30-50)._

## Reading the numbers (what I'd say in an interview)

1. **Semantic >> lexical on this corpus.** Real embeddings lift MRR 0.45 → 0.78 and
   P@5 0.43 → 0.60 over keyword-only. The questions are conceptual ("what is a
   reducer?"), so dense retrieval generalises where exact-term matching can't.

2. **Hybrid does not (yet) beat baseline.** With equal-weight RRF, the weak keyword
   ranker (MRR 0.45) dilutes the already-strong vector ranking, so hybrid MRR (0.758)
   sits just below baseline (0.783). This is expected on a small, clean, semantically-
   phrased corpus and is an honest finding, not a failure to hide.

3. **Rerank is the lever to make hybrid win.** `hybrid+rerank == hybrid` here because
   no Cohere key is set (reranking is a passthrough). The designed story: hybrid widens
   recall, a cross-encoder reranker fixes ordering/precision — that's what should push
   `hybrid+rerank` above `baseline`. Even with rerank off, faithfulness is already
   highest on that row (0.84).

4. **No hallucination on the trap.** abstention = 1.0: the system says "not in the docs"
   for the negative question instead of inventing an API.

## Next

- Add Cohere rerank to complete the "hybrid+rerank > baseline" comparison.
- Secondary lever (no key needed): weight RRF toward the vector ranker.
- Wire Langfuse for per-request cost/latency; expand the dataset to 30-50 items.
