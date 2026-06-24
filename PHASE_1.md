# Phase 1 — RAG core + Eval ✅ COMPLETE (FLAGSHIP)

> The phase that makes this project stand out: a real RAG pipeline **with a
> measurement layer**. The deep-dive write-up (metrics + full table + caveats)
> lives in **[ai/eval/README.md](ai/eval/README.md)**; this is the recap.
> Plan: [Agentic_RAG_Build_Plan.md](Agentic_RAG_Build_Plan.md).

## Definition of Done — all met

- [x] **Eval table comparing ≥3 retrieval configs with real numbers** — keyword /
      baseline / hybrid / hybrid+rerank over a 50-item golden set.
- [x] **hybrid+rerank beats baseline (and I can explain why)** — MRR 0.902 → **0.928**,
      P@5 0.627 → **0.727**, hit@5 0.977 → **1.000**.
- [x] **Faithfulness measured + every answer carries citations** — LLM-as-judge
      faithfulness ~0.92 (+ Ragas-style context-precision/recall); answers cite chunks as `[n]`.
- [x] **Langfuse dashboard for cost + latency per request** — verified (gpt-4o-mini,
      cost auto-computed, ~1.7s avg).

## Pipeline (built in order)

| Step | Module |
|---|---|
| Heading-based chunking (code blocks kept intact, metadata attached) | `app/chunking.py` |
| Ingestion: chunk → embed → upsert (idempotent) | `scripts/ingest.py` |
| Vector retrieval (pgvector cosine) | `app/retrieval.py` |
| Keyword retrieval (Postgres full-text) | `app/retrieval.py` |
| Hybrid search (Reciprocal Rank Fusion) | `app/retrieval.py` |
| Reranking (Cohere cross-encoder) | `app/rerank.py` |
| Generation grounded in context + `[n]` citations | `app/generation.py` |
| Pipeline configs (baseline/hybrid/hybrid+rerank) | `app/pipeline.py` |
| Eval: metrics + LLM-judge + harness | `ai/eval/` |
| Chat UI + `POST /ask` | `web/`, `app/main.py` |

## Results (top-5, real embeddings, Cohere rerank, gpt-4o-mini judge, n=50)

| Config | hit@5 | MRR | P@5 | latency (ms) | faithfulness | relevancy | ctx-prec | ctx-recall | neg-handling |
|---|---|---|---|---|---|---|---|---|---|
| keyword | 0.386 | 0.330 | 0.298 | 429 | 0.43 | 0.46 | 0.43 | 0.42 | 1.00 |
| baseline (vector) | 0.977 | 0.902 | 0.627 | 1422 | 0.90 | 0.92 | 0.89 | 0.88 | 1.00 |
| hybrid (RRF) | 0.977 | 0.896 | 0.627 | 2028 | 0.90 | 0.93 | 0.90 | 0.89 | 1.00 |
| **hybrid+rerank** | **1.000** | **0.928** | **0.727** | 3001 | **0.92** | **0.93** | **0.92** | **0.91** | 1.00 |

_Metrics come two ways: an inline LLM-judge (shown above) **and** the real Ragas library
run in an isolated venv (faithfulness 0.934, answer_relevancy 0.823, context_precision
0.885, context_recall 0.843 for hybrid+rerank) — see [ai/eval/README.md](ai/eval/README.md)._

## Key decisions

1. **Hybrid via RRF**, not score-mixing — fuse by rank position so cosine and
   `ts_rank` scales don't need calibrating.
2. **Rerank is the lever that beats baseline.** Hybrid alone ≈ baseline (the weak
   keyword ranker dilutes a strong vector ranking); a cross-encoder reranker over the
   wider hybrid pool fixes ordering → precision. Cost: ~2× latency, stated honestly.
3. **Eval-first found real problems**, then fixed them:
   - The dataset was Vietnamese while the corpus is English → broke lexical retrieval →
     translated questions to English.
   - A version-drift trap (gd-009): v1.0 uses `langchain.agents.create_agent`, not
     `langgraph.prebuilt.create_react_agent` — flagged, not trusted from memory.
   - Weak handling of "trap" questions (neg-handling 0.25–0.50) → diagnosed two causes
     (lenient prompt + a mis-framed metric) → fixed to **1.00**.
4. **Offline-first dev.** A fake-embedding fallback let the whole pipeline run and the
   DB round-trip be proven before spending on API keys.

## Try it

```bash
cd ai
python -m scripts.ingest                  # chunk -> embed -> upsert (244 chunks)
python -m scripts.ask "How do I add short-term memory with a checkpointer?"
python -m scripts.run_eval --judge        # the comparison table + Langfuse traces
```

**In one line:** *built a hybrid-search + reranking RAG pipeline that lifts
retrieval MRR from 0.90 (vector baseline) to 0.92 with rerank, measured faithfulness
with an LLM-judge, and tracked cost/latency per request in Langfuse — eval-first, not
eval-last.*
