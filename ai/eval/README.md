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

## Results (top-5, real `text-embedding-3-small` vectors, Cohere `rerank-v3.5`, judge = gpt-4o-mini)

| Config | hit@5 | MRR | P@5 | latency (ms) | faithfulness | relevancy | abstention |
|---|---|---|---|---|---|---|---|
| keyword | 0.700 | 0.453 | 0.432 | 503 | 0.63 | 0.68 | 1.00 |
| baseline (vector) | 0.900 | 0.783 | 0.600 | 1609 | 0.81 | 0.86 | 1.00 |
| hybrid (RRF) | 0.900 | 0.758 | 0.500 | 1696 | 0.83 | 0.90 | 1.00 |
| **hybrid+rerank** | **1.000** | **0.900** | **0.700** | 2603 | 0.77 | 0.79 | 1.00 |

_10 answerable items + 1 negative trap. `n=11` (starter set; expanding to 30-50)._

## Reading the numbers (what I'd say in an interview)

1. **Semantic >> lexical on this corpus.** Real embeddings lift MRR 0.45 → 0.78 and
   P@5 0.43 → 0.60 over keyword-only. The questions are conceptual ("what is a
   reducer?"), so dense retrieval generalises where exact-term matching can't.

2. **Hybrid alone ≈ baseline.** With equal-weight RRF the weak keyword ranker (MRR 0.45)
   slightly dilutes the already-strong vector ranking (hybrid MRR 0.758 vs baseline
   0.783). On a small, clean, semantically-phrased corpus, dense retrieval is already
   strong — an honest finding, not hidden.

3. **Reranking wins.** A cross-encoder reranker over the wider hybrid candidate pool
   reorders by true query-document relevance and pushes **hybrid+rerank above baseline
   on every retrieval metric**: MRR 0.78 → 0.90, P@5 0.60 → 0.70, hit@5 0.90 → 1.00.
   This is the designed story — hybrid for recall, rerank for precision — demonstrated.

4. **The cost is latency.** Reranking adds a network round-trip: ~2603 ms vs ~1609 ms
   for baseline. A real precision/latency tradeoff worth stating, not burying.

5. **Generation-quality numbers are noisy at n=11.** The small faithfulness/relevancy
   dip on hybrid+rerank (0.77/0.79) is within LLM-judge noise at this sample size; the
   retrieval metrics are the reliable signal until the dataset grows to 30-50 items.

6. **No hallucination on the trap.** abstention = 1.0: the system says "not in the docs"
   for the negative question instead of inventing an API.

## Observability

LLM calls (generation + judge) are traced in **Langfuse** via the `langfuse.openai`
drop-in — model, token usage, **cost**, and latency per request show up in the
dashboard (verified: gpt-4o-mini, ~1.7s avg, cost auto-computed). Tracing is a
no-op when the Langfuse keys are unset.

## Next

- Expand the golden dataset to 30-50 items to stabilise the generation metrics.
