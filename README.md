# Agentic RAG Assistant — LangGraph docs

A retrieval-augmented assistant that answers questions about the **LangGraph v1.0**
documentation, built to demonstrate AI-engineering depth: retrieval engineering,
**evaluation with real numbers**, grounded generation with citations, and
observability — not just "calling an LLM API".

> Meta-angle: the app answers questions *about* LangGraph, and the agent layer
> (Phase 2) is built *with* LangGraph.

## What it does

- Ingests the official LangGraph v1.0 docs, **chunked by heading** (code blocks kept intact).
- Retrieves with three strategies and compares them on an eval set: **vector**
  (pgvector cosine), **keyword** (Postgres full-text), and **hybrid** (Reciprocal
  Rank Fusion) — then **reranks** with a cross-encoder (Cohere).
- Generates answers grounded **only** in retrieved context, with inline `[n]`
  citations back to the source docs, and abstains ("not in the docs") on questions
  the corpus can't answer.
- Measures everything: retrieval (hit@k / MRR / precision@k), generation
  (faithfulness / answer-relevancy via LLM-as-judge), and **cost + latency per
  request in Langfuse**.

## Results (headline)

Reranking over a hybrid candidate pool is the best retriever, beating the vector
baseline on every retrieval metric (golden set, `n=30`):

| Config | hit@5 | MRR | P@5 | latency |
|---|---|---|---|---|
| baseline (vector) | 0.962 | 0.897 | 0.585 | 1382 ms |
| hybrid (RRF) | 0.962 | 0.888 | 0.562 | 1576 ms |
| **hybrid+rerank** | **1.000** | **0.923** | **0.723** | 2350 ms |

The eval also surfaced a real weakness — weak handling of unanswerable "trap"
questions — which was then **diagnosed and fixed** (stricter groundedness prompt +
a dedicated negative-handling judge): trap handling went 0.25–0.50 → **1.00**. Full
table, faithfulness numbers, methodology and honest caveats:
**[ai/eval/README.md](ai/eval/README.md)**.

## Architecture

```
web/   Next.js + TypeScript + Tailwind   ── HTTP ──>   ai/   Python + FastAPI
  chat UI, clickable citations                          chunking, retrieval,
                                                        rerank, generation, eval
                         └────────── PostgreSQL + pgvector (Neon) ──────────┘
                                     chunks (embedding + tsvector)
```

Two languages, two roles — TypeScript for the app, Python for the AI/eval layer.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind |
| AI service | Python, FastAPI |
| Vector store | PostgreSQL + **pgvector** (Neon) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Hybrid search | pgvector cosine + Postgres full-text, fused with RRF |
| Reranking | Cohere Rerank (`rerank-v3.5`) |
| Generation / judge | `gpt-4o-mini` (OpenAI-compatible) |
| Observability | Langfuse (cost, latency, traces) |
| Agent (Phase 2) | LangGraph |

## Run locally

Prereqs: a Neon Postgres URL and an OpenAI API key (Cohere + Langfuse optional).

```bash
# AI service
cd ai
python -m venv .venv && .venv\Scripts\Activate.ps1      # Windows
pip install -r requirements.txt
cp .env.example .env        # fill DATABASE_URL + EMBEDDING_API_KEY (+ optional keys)
python -m scripts.init_db        # pgvector + tables
python -m scripts.fetch_corpus   # download LangGraph v1.0 docs
python -m scripts.ingest         # chunk -> embed -> upsert
python -m scripts.run_eval --judge   # the eval comparison table
uvicorn app.main:app --reload --port 8000

# Web (separate terminal)
cd web
pnpm install
pnpm dev        # http://localhost:3000
```

> This machine uses a corporate/local CA: Node needs `NODE_OPTIONS=--use-system-ca`
> and Python uses `truststore` (auto-injected). See [CLAUDE.md](CLAUDE.md).

## Project layout

- `ai/app/` — config, db, embeddings, chunking, retrieval, rerank, generation, pipeline
- `ai/eval/` — metrics, LLM-judge, harness, **results + write-up**
- `ai/scripts/` — init_db, fetch_corpus, ingest, ask, run_eval, search
- `web/` — Next.js chat UI
- `golden_dataset_langgraph.json` — eval golden dataset (questions + ground truth + expected sources)
- `Agentic_RAG_Build_Plan.md` / `PHASE_0.md` — phased plan and progress

## Status

- **Phase 0 — Foundation:** ✅ complete
- **Phase 1 — RAG core + Eval (flagship):** ✅ complete (eval table proves hybrid+rerank > baseline)
- **Phase 2 — Agent layer (LangGraph tools + guardrails):** next
