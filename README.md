# LangGraph Migration Workbench — an agentic RAG system

**Live demo: https://agentic-rag-assistant.vercel.app** — try
**[/migrate](https://agentic-rag-assistant.vercel.app/migrate)**
&nbsp;·&nbsp; web on Vercel, API on Render, Postgres+pgvector on Neon.
_(Free tier: the first request may take ~60s while the API cold-starts.)_

Paste legacy LangGraph v0.x code into **`/migrate`** and get a v1.0 migration as a
diff where **every change cites the pinned docs** — or an honest "no changes" /
"needs manual review" verdict. Underneath is what makes that trustworthy: a
retrieval-augmented assistant over the **LangGraph v1.0** documentation that goes
deep on the AI-engineering layer — retrieval engineering, **evaluation with real
numbers**, grounded generation with citations, and observability — not just
"calling an LLM API".

**Honest scope:** the workbench covers the **16 curated symbols** in
[`ai/data/deprecations.json`](ai/data/deprecations.json) (each verified by grepping
both pinned corpora, not written from memory) — not "any LangGraph code". Its
metrics are string/AST-level: they check the deprecated call is gone, the v1.0
idiom is present, and every change is cited — they do **not** execute the result.

> **Why RAG over just asking ChatGPT?** ChatGPT absorbed LangGraph from mostly
> pre-v1.0 tutorials, so it confidently emits dead APIs — and the eval below
> measures exactly that: a bare LLM given the same migration task returns the
> legacy code essentially unchanged (parses 1.000, **deprecated-API removal
> 0.000**). Grounding, citations, version pinning, knowing-when-it-doesn't-know,
> and measurability are the fix — and the technique transfers to private data
> ChatGPT never saw. Full rationale + FAQ: **[RATIONALE.md](RATIONALE.md)**.

> Meta-angle: the app answers questions *about* LangGraph, migrates code *to*
> LangGraph v1.0, and its agent + migration pipelines are built *with* LangGraph.

## What it does

- **Migration Workbench (`/migrate`):** a dedicated LangGraph pipeline —
  deterministic AST `detect` against the deprecations map, `research` grounded in
  the pinned corpora (`check_api_status` + retrieval), one structured-output
  `rewrite`, deterministic `verify` with a bounded retry — streamed live with the
  same node-graph view as chat, ending in a diff with per-change citations.
- Ingests the official LangGraph docs **versioned**: v1.0 (the answer corpus) and
  the deprecated v0.2 concepts docs side by side, **chunked by heading** (code
  blocks kept intact), with retrieval filtered by `docs_version`.
- Retrieves with three strategies and compares them on an eval set: **vector**
  (pgvector cosine), **keyword** (Postgres full-text), and **hybrid** (Reciprocal
  Rank Fusion) — then **reranks** with a cross-encoder (Cohere).
- Generates answers grounded **only** in retrieved context, with inline `[n]`
  citations back to the source docs, and abstains ("not in the docs") on questions
  the corpus can't answer. A **"Show work"** disclosure on `/chat` opens the live
  agent graph and a retrieval inspector (the full candidate pool with
  `cos · ts · rrf` score chips, cited rows badged).
- Measures everything: retrieval (hit@k / MRR / precision@k), generation
  (faithfulness / answer-relevancy via LLM-as-judge), migration quality
  (agent vs raw-LLM baseline), and **cost + latency per request in Langfuse** —
  surfaced in an **in-app eval dashboard at `/eval`** (retrieval comparison incl.
  the mixed-corpus stress test, migration table, Ragas, agent tool-selection,
  injection resistance, cache speed-up) so the numbers are visible without
  reading the repo.

## Results (headline)

### Migration: graph vs raw-LLM baseline

The workbench's reason to exist, measured. Same 20 snippets (10 to modernize,
6 to flag for manual review, 4 already clean), same scoring code path — one
condition is a bare gpt-4o-mini chat call, the other is the migration graph
(`detect → research → rewrite → verify`) over the pinned corpora:

| metric | raw-LLM baseline | migration graph |
|---|---|---|
| parses | 1.000 | **1.000** |
| deprecated_removed | 0.000 | **1.000** |
| idiom_present | 0.000 | **1.000** |
| citation_coverage | 0.000 | **1.000** |
| clean_passthrough | 1.000 | **1.000** |
| flagged_not_rewritten | 0.000 | **1.000** |

**How to read this honestly** (full caveats:
[ai/eval/results/migration_agent.md](ai/eval/results/migration_agent.md)):
the baseline's failure is the finding — a bare model *parses* fine and changes
nothing, so its `clean_passthrough` 1.000 is free. On the graph side,
`deprecated_removed`/`idiom_present` are largely true **by construction** (the
dataset derives from the same 16-symbol map the detector reads); the earned
column is `citation_coverage`, which failed first (0.800 — a `moved` symbol has
zero v1.0 mentions, so citations landed on plausible-but-wrong pages) and was
fixed in the system, not the metric. And no column executes the rewritten code —
the metrics are string/AST-level; an execution check is the honest next metric.
Baseline detail: [ai/eval/results/migration_baseline.md](ai/eval/results/migration_baseline.md).

### Retrieval: config comparison (v1.0 corpus)

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

(Reproducibility footnote: enforcing determinism later exposed that `ORDER BY`
ties were unordered — breaking ties by `id` moved the hybrid row to MRR 0.913 /
P@5 0.632 with no code change. The old figures were one valid ordering of a tie;
details in [ai/eval/results/eval_real.md](ai/eval/results/eval_real.md). A judged
re-baseline of this table is pending a working Cohere key.)

### The mixed-corpus stress test

Baseline vector search already scores 0.977 hit@5 on the clean v1.0 corpus — the
naive method nearly solves it, which proves little. So Stage 2 of Phase 3 made
the problem genuinely hard: the deprecated **v0.2 docs were ingested beside v1.0**
(154 + 244 chunks) and hybrid retrieval was re-run without a version filter
(retrieval-only, relevance judged by `(docs_version, slug)`):

| hybrid | hit@5 | MRR | P@5 | v0.2 chunks in top-5 |
|---|---|---|---|---|
| version-filtered `1.0` | 0.977 | 0.913 | 0.632 | 0.00 |
| unfiltered (mixed) | 0.909 | 0.647 | 0.345 | **2.64 / 5** |

The stale corpus does not sit inertly in the index: its prose on
persistence/streaming/graphs is near-identical to v1.0's, so it wins over half
the top-5, halving MRR and precision. That is the "confidently retrieves outdated
docs" failure the workbench exists to fix — **now a measurement, not a claim** —
and version-filtered retrieval (the default) recovers the published quality.
Details: [ai/eval/results/eval_mixed_corpus.md](ai/eval/results/eval_mixed_corpus.md).

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
| Frontend | Next.js, TypeScript, Tailwind, shadcn/ui (Radix + next-themes) |
| AI service | Python, FastAPI |
| Vector store | PostgreSQL + **pgvector** (Neon) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Hybrid search | pgvector cosine + Postgres full-text, fused with RRF |
| Reranking | Cohere Rerank (`rerank-v3.5`) |
| LLM gateway | OpenRouter (`openai/gpt-4o-mini`) — generation + LLM-as-judge |
| Eval | Ragas (isolated venv) + a custom LLM-as-judge |
| Observability | Langfuse (cost, latency, traces) |
| Agent (Phase 2) | LangGraph, also exposed over **MCP** |
| CI | GitHub Actions (lint/eval/Docker smoke-test/keep-warm) |

## Run locally

Prereqs: a Neon Postgres URL, an OpenAI key for embeddings, and an OpenRouter key
for generation / the eval judge (Cohere rerank + Langfuse optional).

```bash
# AI service
cd ai
python -m venv .venv && .venv\Scripts\Activate.ps1      # Windows
pip install -r requirements.txt
cp .env.example .env        # fill DATABASE_URL + EMBEDDING_API_KEY + OPENROUTER_API_KEY (+ optional keys)
python -m scripts.init_db        # pgvector + tables
python -m scripts.fetch_corpus   # download LangGraph v1.0 docs
python -m scripts.ingest         # chunk -> embed -> upsert
python -m scripts.run_eval --judge   # the eval comparison table
uvicorn app.main:app --reload --port 8000

# optional — the Phase 3 / Stage 2 extras:
python -m scripts.fetch_corpus --docs-version 0.2   # the deprecated v0.2 corpus
python -m scripts.ingest --docs-version 0.2
python -m scripts.run_mixed_eval                    # mixed-corpus stress test
python -m scripts.run_migration_eval --mode agent   # migration eval (--mode baseline for the control)

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

- `ai/app/` — config, db, embeddings, chunking, retrieval, rerank, generation,
  pipeline, agent, `migrate.py` (the workbench graph), tools + MCP server
- `ai/data/deprecations.json` — the corpus-verified v0.x → v1.0 API-status map
- `ai/eval/` — metrics, LLM-judge, harnesses (retrieval + migration), **results + write-ups**
- `ai/scripts/` — init_db, fetch_corpus, ingest, ask, run_eval, run_mixed_eval,
  run_migration_eval, migrate_ask, search
- `web/` — Next.js UI (`/chat` with multi-turn memory + "Show work",
  `/migrate` workbench, `/eval` metrics dashboard)
- `golden_dataset_langgraph.json` — eval golden dataset (questions + ground truth + expected sources)
- `Agentic_RAG_Build_Plan.md` / `PHASE_0.md`–`PHASE_3.md` — phased plan and progress

## Agent layer (Phase 2)

A **LangGraph** ReAct agent wraps retrieval as one tool among several and decides
which to call:

- **Tools:** `rag_search` (the Phase 1 pipeline), `calculator` (safe arithmetic),
  `list_doc_topics` (corpus coverage), and `check_api_status` (v0.x → v1.0 API
  verdicts from the curated deprecations map, corroborated by per-version
  occurrence counts from the corpus itself).
- **Orchestration:** an explicit `StateGraph` (agent ⇄ ToolNode) — multi-tool
  questions are handled in one turn (e.g. "what is a checkpointer, and what is 12×9?").
- **Multi-turn memory:** a LangGraph checkpointer (`MemorySaver` + per-conversation
  `thread_id`) so follow-ups resolve context ("can I use *it* with Postgres?"); the UI
  has a "New chat" button to start a fresh thread.
- **Guardrails:** max tool rounds, graceful tool-error handling, input validation,
  and a prompt-injection rule (it refuses to leak its prompt / follow injected instructions).
- **Eval:** tool-selection accuracy **1.000** and required-tool recall **1.000**
  over a 21-item labelled set (single-tool, multi-tool, off-domain no-tool traps,
  and `check_api_status` routing) —
  see [ai/eval/results/agent_eval.md](ai/eval/results/agent_eval.md).
- **Tracing:** every agent run is a multi-step Langfuse trace (LLM steps + each tool call, in order).
- **MCP server:** the same four tools are also published over the **Model Context
  Protocol** (`ai/app/mcp_server.py`) — one tool implementation, two front doors
  (internal LangGraph agent + any external MCP client like Claude Desktop). Run with
  `cd ai && python -m app.mcp_server`.

## Status

- **Phase 0 — Foundation:** ✅ complete
- **Phase 1 — RAG core + Eval (flagship):** ✅ complete (eval table proves hybrid+rerank > baseline)
- **Phase 2 — Agent layer (LangGraph tools + guardrails):** ✅ complete
- **Phase 3 — Visible reasoning + Migration Workbench:** ✅ complete
  (see **[PHASE_3.md](PHASE_3.md)**). Stage 1 made the agent's work inspectable
  (unit tests gating CI, retrieval trace, live agent-graph + "Show work" on
  `/chat`); Stage 2 shipped the versioned corpus, the mixed-corpus stress test,
  `check_api_status`, the migration eval (baseline first) and the `/migrate`
  workbench. Deployed live (**[DEPLOY.md](DEPLOY.md)** — Vercel + Render + Neon,
  no Docker). **Known gaps, stated honestly:** the Cohere key is currently dead
  (401), so live `hybrid+rerank` silently degrades to plain hybrid — the
  rank-movement view in the inspector and a judged re-baseline of the flagship
  table both wait on a rotated key.
- **Expansions:** shadcn/ui + light/dark theme, Markdown answers, **token-by-token
  streaming** of agent answers (SSE, no Vercel AI SDK), multi-turn agent
  memory, in-app eval dashboard (`/eval`), MCP server for the agent tools, query-rewriting,
  semantic cache (13× on repeats), prompt-injection eval (1.000), GitHub Actions
  CI/eval/keep-warm — full list in **[ROADMAP.md](ROADMAP.md)**
