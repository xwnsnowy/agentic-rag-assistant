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
| keyword | 0.462 | 0.367 | 0.351 | 441 | 0.47 | 0.49 | 0.50 |
| baseline (vector) | 0.962 | 0.897 | 0.585 | 1382 | 0.86 | 0.89 | 0.25 |
| hybrid (RRF) | 0.962 | 0.888 | 0.562 | 1576 | 0.86 | 0.90 | 0.25 |
| **hybrid+rerank** | **1.000** | **0.923** | **0.723** | 2350 | 0.85 | 0.87 | 0.50 |

_26 answerable items + 4 negative traps. `n=30`._

## Reading the numbers (what I'd say in an interview)

1. **Semantic >> lexical on this corpus.** Dense retrieval lifts MRR 0.37 → 0.90 and
   P@5 0.35 → 0.59 over keyword-only. Most questions are conceptual ("what is a
   reducer?"), so embeddings generalise where exact-term matching can't.

2. **Hybrid alone ≈ baseline.** With equal-weight RRF the weak keyword ranker slightly
   dilutes the already-strong vector ranking (hybrid MRR 0.888 vs baseline 0.897). On a
   clean, semantically-phrased corpus, dense retrieval is already strong — an honest
   finding, not hidden.

3. **Reranking wins.** A cross-encoder reranker over the wider hybrid candidate pool
   reorders by true query-document relevance and pushes **hybrid+rerank above baseline
   on every retrieval metric**: MRR 0.897 → 0.923, P@5 0.585 → 0.723, hit@5 0.962 → 1.00.
   The designed story — hybrid for recall, rerank for precision — demonstrated on 26 items.

4. **The cost is latency.** Reranking adds a network round-trip: ~2350 ms vs ~1382 ms
   for baseline. A real precision/latency tradeoff worth stating, not burying.

5. **The eval found a real weakness: abstention is poor (0.25–0.50).** On the 4 negative
   traps (questions the docs can't answer — e.g. "is there a `graph.deploy()`?"), the
   system too often answers instead of refusing, because first-stage retrieval always
   returns *some* top-k chunks and the LLM treats vaguely-related context as an answer.
   This is exactly the kind of failure an honest eval is meant to surface. **Fix on the
   roadmap:** a relevance-score gate (abstain when the top rerank score is below a
   threshold) and a stricter "answer only if the context truly covers it" prompt.

6. **Faithfulness/relevancy are solid (~0.85–0.90)** for the dense configs — answers are
   well-grounded in the retrieved context when an answer exists.

## Observability

LLM calls (generation + judge) are traced in **Langfuse** via the `langfuse.openai`
drop-in — model, token usage, **cost**, and latency per request show up in the
dashboard (verified: gpt-4o-mini, ~1.7s avg, cost auto-computed). Tracing is a
no-op when the Langfuse keys are unset.

## Next

- Expand the golden dataset to 30-50 items to stabilise the generation metrics.
