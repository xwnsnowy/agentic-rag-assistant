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
- **context_precision** — LLM-judge (Ragas-style): fraction of the retrieved context that is
  actually relevant to the question (retrieval signal-to-noise).
- **context_recall** — LLM-judge (Ragas-style): fraction of the ground-truth answer's
  information that the retrieved context covers.
- **neg-handling** — on the negative traps, did the system correctly avoid affirming a
  capability the docs don't describe (say "not in the docs" or "LangGraph doesn't provide it")?

`hit@k` saturates when expected pages are large, so **MRR / precision@k** are the
honest retrieval signals here.

### Why these metrics are LLM-judged, not the Ragas library

The plan called for "Ragas + a custom LLM-judge". In practice the **Ragas package could
not be installed cleanly** in this project: every Ragas version imports
`langchain_community.chat_models.vertexai`, which current `langchain-community` no longer
ships, and the older langchain stack Ragas needs (`langchain-core` 0.3) conflicts head-on
with the **langchain 1.x** stack the Phase 2 agent requires (`langgraph` / `langchain-openai`
pin `langchain-core >= 1.4`). Rather than fork the project into incompatible venvs, the
four standard RAG metrics (faithfulness, answer-relevancy, context-precision,
context-recall) are implemented here as a single LLM-judge call — the same definitions
Ragas uses, run against `gpt-4o-mini`. See `eval/judge.py`.

## Results (top-5, real `text-embedding-3-small` vectors, Cohere `rerank-v3.5`, judge = gpt-4o-mini)

| Config | hit@5 | MRR | P@5 | latency (ms) | faithfulness | relevancy | ctx-prec | ctx-recall | neg-handling |
|---|---|---|---|---|---|---|---|---|---|
| keyword | 0.386 | 0.330 | 0.298 | 429 | 0.43 | 0.46 | 0.43 | 0.42 | 1.00 |
| baseline (vector) | 0.977 | 0.902 | 0.627 | 1422 | 0.90 | 0.92 | 0.89 | 0.88 | 1.00 |
| hybrid (RRF) | 0.977 | 0.896 | 0.627 | 2028 | 0.90 | 0.93 | 0.90 | 0.89 | 1.00 |
| **hybrid+rerank** | **1.000** | **0.928** | **0.727** | 3001 | **0.92** | **0.93** | **0.92** | **0.91** | 1.00 |

_44 answerable items + 6 negative traps. `n=50`._

## Reading the numbers (what I'd say in an interview)

1. **Semantic >> lexical on this corpus.** Dense retrieval lifts MRR 0.33 → 0.90 and
   P@5 0.30 → 0.63 over keyword-only. Most questions are conceptual ("what is a
   reducer?"), so embeddings generalise where exact-term matching can't.

2. **Hybrid alone ≈ baseline.** With equal-weight RRF the weak keyword ranker slightly
   dilutes the already-strong vector ranking (hybrid MRR 0.896 vs baseline 0.902). On a
   clean, semantically-phrased corpus, dense retrieval is already strong — an honest
   finding, not hidden.

3. **Reranking wins — on every metric.** A cross-encoder reranker over the wider hybrid
   candidate pool reorders by true query-document relevance and pushes **hybrid+rerank
   above baseline
   on every metric**: MRR 0.902 → 0.928, P@5 0.627 → 0.727, hit@5 0.977 → 1.00, and the
   Ragas-style context metrics too (context-precision 0.889 → 0.918, context-recall
   0.877 → 0.914). The designed story — hybrid for recall, rerank for precision —
   demonstrated on 44 answerable items.

4. **The cost is latency.** Reranking adds a network round-trip: ~3000 ms vs ~1422 ms
   for baseline. A real precision/latency tradeoff worth stating, not burying.

5. **The eval found a real weakness — and the fix is the interesting part.** The first
   30-item run scored **neg-handling 0.25–0.50**: on trap questions (e.g. "is there a
   `graph.deploy()`?") the system over-answered. Diagnosis found *two* causes, not one:
   - the generation prompt treated topically-related context as an answer, and
   - a measurement bug: a rerank-score gate *can't* separate traps from real questions
     (the "built-in vector DB?" trap retrieves a vector-store chunk scoring 0.67 —
     higher than some genuine questions), so the real lever was the prompt, plus a
     judge that recognises a correct *denial* ("LangGraph does not provide X") as valid,
     not only an "I don't know".
   After a stricter groundedness prompt + a dedicated negative-handling judge,
   **neg-handling is 1.00** with faithfulness/relevancy on answerable items unchanged.

6. **Faithfulness/relevancy/context metrics are solid (~0.88–0.93)** for the dense configs —
   answers are well-grounded and retrieval surfaces the right context when an answer exists.

## Observability

LLM calls (generation + judge) are traced in **Langfuse** via the `langfuse.openai`
drop-in — model, token usage, **cost**, and latency per request show up in the
dashboard (verified: gpt-4o-mini, ~1.7s avg, cost auto-computed). Tracing is a
no-op when the Langfuse keys are unset.

## Next

- Golden dataset is at 50 items (44 answerable + 6 traps); could grow further.
- If the project later drops to a langchain-0.3 / Python-3.12 stack, swap the LLM-judge
  context metrics for the Ragas library directly (same definitions).
