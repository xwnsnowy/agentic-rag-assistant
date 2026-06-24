# Agentic RAG Assistant — LangGraph docs

**Live demo: https://agentic-rag-assistant.vercel.app**
&nbsp;·&nbsp; web on Vercel, API on Render, Postgres+pgvector on Neon.
_(Free tier: the first request may take ~60s while the API cold-starts.)_

A retrieval-augmented assistant that answers questions about the **LangGraph v1.0**
documentation. It goes deep on the AI-engineering layer: retrieval engineering,
**evaluation with real numbers**, grounded generation with citations, and
observability — not just "calling an LLM API".

> **Why RAG over just asking ChatGPT?** Grounding, citations, version pinning,
> knowing-when-it-doesn't-know, and measurability — and the technique transfers to
> private data ChatGPT never saw. Full rationale + FAQ: **[RATIONALE.md](RATIONALE.md)**.

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
  request in Langfuse** — surfaced in an **in-app eval dashboard at `/eval`**
  (retrieval comparison, Ragas, agent tool-selection, injection resistance, cache
  speed-up) so the numbers are visible without reading the repo.

## Results (headline)

Reranking over a hybrid candidate pool is the best retriever, beating the vector
baseline on every metric (golden set, `n=50`):

| Config | hit@5 | MRR | P@5 | faithfulness | ctx-recall | latency |
|---|---|---|---|---|---|---|
| baseline (vector) | 0.977 | 0.902 | 0.627 | 0.90 | 0.88 | 1422 ms |
| hybrid (RRF) | 0.977 | 0.896 | 0.627 | 0.90 | 0.89 | 2028 ms |
| **hybrid+rerank** | **1.000** | **0.928** | **0.727** | **0.92** | **0.91** | 3001 ms |

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

### Containerized (optional)

The AI service ships a [`ai/Dockerfile`](ai/Dockerfile) + [`docker-compose.yml`](docker-compose.yml)
(API + Postgres/pgvector in one command). Production deploys to **managed platforms**
(Render/Vercel/Neon) rather than self-hosted containers — simpler and cheaper at this scale — so
the image is a **portability artifact**: it's **built and smoke-tested in CI** (`docker` job in
[ci.yml](.github/workflows/ci.yml)) on GitHub's cloud runner, proving it works without Docker on
the dev machine.

```bash
docker compose up --build      # needs Docker; brings up API + pgvector
```

## Project layout

- `ai/app/` — config, db, embeddings, chunking, retrieval, rerank, generation, pipeline
- `ai/eval/` — metrics, LLM-judge, harness, **results + write-up**
- `ai/scripts/` — init_db, fetch_corpus, ingest, ask, run_eval, search
- `web/` — Next.js chat UI (`/` chat with multi-turn memory, `/eval` metrics dashboard)
- `golden_dataset_langgraph.json` — eval golden dataset (questions + ground truth + expected sources)
- `Agentic_RAG_Build_Plan.md` / `PHASE_0.md` — phased plan and progress

## Agent layer (Phase 2)

A **LangGraph** ReAct agent wraps retrieval as one tool among several and decides
which to call:

- **Tools:** `rag_search` (the Phase 1 pipeline), `calculator` (safe arithmetic),
  `list_doc_topics` (corpus coverage).
- **Orchestration:** an explicit `StateGraph` (agent ⇄ ToolNode) — multi-tool
  questions are handled in one turn (e.g. "what is a checkpointer, and what is 12×9?").
- **Multi-turn memory:** a LangGraph checkpointer (`MemorySaver` + per-conversation
  `thread_id`) so follow-ups resolve context ("can I use *it* with Postgres?"); the UI
  has a "New chat" button to start a fresh thread.
- **Guardrails:** max tool rounds, graceful tool-error handling, input validation,
  and a prompt-injection rule (it refuses to leak its prompt / follow injected instructions).
- **Eval:** tool-selection accuracy **0.917**, required-tool recall **1.000** over a
  labelled set — see [ai/eval/results/agent_eval.md](ai/eval/results/agent_eval.md).
- **Tracing:** every agent run is a multi-step Langfuse trace (LLM steps + each tool call, in order).
- **MCP server:** the same three tools are also published over the **Model Context
  Protocol** (`ai/app/mcp_server.py`) — one tool implementation, two front doors
  (internal LangGraph agent + any external MCP client like Claude Desktop). Run with
  `cd ai && python -m app.mcp_server`.

## Status

- **Phase 0 — Foundation:** ✅ complete
- **Phase 1 — RAG core + Eval (flagship):** ✅ complete (eval table proves hybrid+rerank > baseline)
- **Phase 2 — Agent layer (LangGraph tools + guardrails):** ✅ complete
- **Phase 3 — Production polish:** deployed live (see **[DEPLOY.md](DEPLOY.md)** —
  Vercel + Render + Neon, no Docker)
- **Expansions:** shadcn/ui + light/dark theme, Markdown answers, multi-turn agent
  memory, in-app eval dashboard (`/eval`), MCP server for the agent tools, query-rewriting,
  semantic cache (13× on repeats), prompt-injection eval (1.000), GitHub Actions
  CI/eval/keep-warm — full list in **[ROADMAP.md](ROADMAP.md)**
