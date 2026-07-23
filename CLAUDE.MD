# CLAUDE.md

Project context for Claude Code. Read this before working on any task in this repo.

## What this project is

An **Agentic RAG Assistant** that answers questions about the **LangGraph documentation**.
It demonstrates AI-Engineer skills: retrieval engineering, evaluation,
and agent orchestration — not just "calling an LLM API". Polish and correctness matter more
than feature count. Note the intentional meta-angle: the agent layer is built **with** LangGraph,
and answers questions **about** LangGraph — building it is also how the author learns the tool.

## Corpus

- Source: official LangGraph docs (conceptual guides + API reference + how-to guides). Python.
- **Pinned version: LangGraph v1.0** (stable since Oct 2025). The ecosystem moves fast — older
  tutorials use deprecated patterns (e.g. `set_entry_point()`); keep answers to current v1.0
  idioms (e.g. `add_edge(START, ...)`).
- Chunk docs **by heading/section**, never split a code block mid-way. Keep heading + code
  together. Store useful metadata (page title, section, source URL) per chunk.
- IMPORTANT: AI-library answers can look plausible but be wrong. Every golden-dataset answer
  must be verified against the pinned v1.0 docs, not from memory.

## Architecture

```
web/   Next.js + TypeScript + Tailwind   -> UI, auth, chat history, render citations
ai/    Python + FastAPI                   -> embeddings, retrieval, agent, eval
        shared: PostgreSQL + pgvector      -> chunks, embeddings, chat logs
```

Two languages, two roles — this split is intentional: TS for the app, Python for the AI/eval
layer. Do not collapse the Python layer into TS.

## Tech stack

- Vector store: PostgreSQL + **pgvector** (do not introduce a separate vector DB)
- Embeddings: `text-embedding-3-small` (or Voyage/Cohere) via the AI service
- LLM access: OpenRouter
- Reranking: Cohere Rerank API (or a cross-encoder later)
- Eval: Ragas + a small custom LLM-as-judge
- Observability: Langfuse (traces, cost, latency)
- Agent orchestration: LangGraph (Python); agent tools also exposed over MCP
- Frontend: Next.js + shadcn/ui (Radix + next-themes), Markdown answers via react-markdown.
  Agent answers stream token-by-token over SSE (`POST /agent/stream` -> `runAgentStream`
  reads the body with a stream reader). No Vercel AI SDK — the backend is FastAPI, so plain
  SSE is simpler than adapting the SDK's data-stream protocol.

## Build phases (current status: Phase 0–3 COMPLETE. Phase 1 eval proves hybrid+rerank > baseline; Phase 2 agent picks among 4 tools at 1.000 accuracy (21 items) with guardrails; Phase 3 delivered visible reasoning + the `/migrate` Migration Workbench — see PHASE_3.md. Blocked on a rotated Cohere key: rerank rank-movement UI + a judged re-baseline.)

- **Phase 0 — Foundation.** Scaffold `web/` and `ai/`, enable pgvector, create the `chunks`
  table, get one chunk inserted + cosine-similarity query working, and a Next.js -> FastAPI
  health-check.
- **Phase 1 — RAG core + Eval (FLAGSHIP).** Ingestion + heading-based chunking; hybrid search
  (pgvector + Postgres full-text via Reciprocal Rank Fusion); reranking; generation WITH
  citations; an eval pipeline over a golden dataset measuring retrieval + faithfulness + cost
  - latency. Compare baseline vs hybrid vs hybrid+rerank with real numbers. Do NOT move to
    Phase 2 until there is an eval table proving improvements.
- **Phase 2 — Agent layer.** Wrap retrieval as a tool; add 1-2 more tools (web search,
  db query/calculator); LangGraph orchestration; guardrails (max loops, tool-error handling,
  input/output validation). Measure tool-selection accuracy.
- **Phase 3 — Visible reasoning + Migration Workbench** (production polish — streaming,
  caching, deploy — landed early as expansions). Stage 1: unit tests gating CI, retrieval
  trace, `node`/`retrieval` SSE events, live agent-graph + "Show work" inspector on `/chat`.
  Stage 2: versioned corpus (v0.2 beside v1.0), mixed-corpus eval, `check_api_status`,
  migration eval (raw-LLM baseline first), the `detect → research → rewrite → verify`
  migration graph, and the `/migrate` UI. Full DoD + findings in `PHASE_3.md`.

## `chunks` table (Phase 0 target schema)

- `id` (pk)
- `content` (text) — the chunk text
- `embedding` (vector) — pgvector column
- `metadata` (jsonb) — page title, section, source URL
- `tsv` (tsvector) — generated from content, for keyword/full-text side of hybrid search

## Deployment (continuous deploy from the start)

We deploy as we build — push to a branch creates a preview, merge to `main` deploys production.

- **web/ (Next.js) -> Vercel.** Root directory set to `web/`. Zero-config, git push auto-deploys.
- **ai/ (FastAPI) -> Render (or Railway).** Root directory set to `ai/`. Long-running container,
  better than serverless for LLM calls / agent loops / heavy deps.
- **Database -> Neon (Postgres + pgvector).** Enable the `vector` extension. Use the pooled
  `DATABASE_URL` from Neon.

Deploy-aware rules for any code you write:

- Never hardcode `localhost` or ports. Read hosts/URLs from env vars.
- Frontend calls backend via `NEXT_PUBLIC_API_URL`; backend must enable CORS for the frontend domain.
- All secrets (`DATABASE_URL`, OpenRouter key, embedding key, Cohere key, Langfuse keys) live in
  each platform's dashboard env vars — never commit. Mirror required keys in `.env.example`.
- Keep `main` always deployable. Do WIP on branches and rely on preview deploys.

## Local development — NO DOCKER

The dev machine is resource-constrained and cannot run Docker well. Do NOT use Docker,
docker-compose, or containers anywhere — not for local dev, not for deployment. Keep everything
lightweight.

> **One narrow, approved exception (containerization demo):** `ai/Dockerfile`, `docker-compose.yml`
> and `ai/.dockerignore` exist to demonstrate the service is containerizable (a common production requirement).
> They are **never built or run on the dev machine** — the CI job `docker` in
> `.github/workflows/ci.yml` builds + smoke-tests the image on GitHub's cloud runner. Local dev
> and production deploy stay no-Docker (uvicorn + Vercel/Render/Neon). Do NOT introduce Docker
> into the local-dev or deploy paths.

- Run `web/` with `pnpm dev` (use **pnpm**, not npm); run `ai/` with `uvicorn` (a local Python venv, not a container).
- **SSL note (this machine has a corporate/local CA):**
  - Node/pnpm: prefix with `NODE_OPTIONS=--use-system-ca` (e.g. `NODE_OPTIONS=--use-system-ca pnpm install`).
  - Python: standard CA verification fails too. We depend on `truststore` and call
    `truststore.inject_into_ssl()` (auto-run in `ai/app/__init__.py`) to use the OS trust store.
- For the database, do NOT install or run Postgres locally. Use **Neon**: create a separate
  dev branch/database in Neon and point local `DATABASE_URL` at it. Same managed Postgres +
  pgvector for both local and production, just different branches.
- Prefer lightweight tooling and avoid heavy local processes; the machine lags easily.

## Commands (keep this section updated as the project grows)

Fill these in during Phase 0 once scaffolded, and update them whenever they change. This section
is the first place to look for how to run anything.

- web dev: `cd web && NODE_OPTIONS=--use-system-ca pnpm dev` (http://localhost:3000 — routes: `/chat`, `/migrate` migration workbench, `/eval` dashboard)
- web build: `cd web && NODE_OPTIONS=--use-system-ca pnpm build`
- web test: `cd web && NODE_OPTIONS=--use-system-ca pnpm test` (vitest; covers the SSE frame parser in `lib/sse.ts`)
- web deps: `cd web && NODE_OPTIONS=--use-system-ca pnpm install`
- ai venv (Windows): `cd ai && python -m venv .venv && .venv\Scripts\Activate.ps1`
- ai deps: `cd ai && pip install -r requirements.txt`
- ai dev: `cd ai && uvicorn app.main:app --reload --port 8000` (note: module is `app.main`)
- db migrate: `cd ai && python -m scripts.init_db` (applies every migrations/*.sql in filename order; all idempotent)
- db seed/DoD: `cd ai && python -m scripts.seed_chunk` (insert 1 chunk + cosine query)
- fetch corpus: `cd ai && python -m scripts.fetch_corpus` (LangGraph v1.0 docs -> data/raw/ + manifest.json; pinned tag 1.0.10)
- fetch corpus v0.2: `cd ai && python -m scripts.fetch_corpus --docs-version 0.2` (10 concepts pages from the GitHub repo at pinned tag 0.2.76 -> data/raw-0.2/ + manifest-0.2.json)
- eval: `cd ai && python -m scripts.run_eval --judge` (compares keyword/baseline/hybrid/hybrid+rerank; `--judge` adds faithfulness/relevancy via LLM, traced to Langfuse)
- mixed-corpus eval: `cd ai && python -m scripts.run_mixed_eval` (S2.1: filtered v1.0 configs vs unfiltered mixed-corpus hybrid, retrieval-only; writes eval/results/eval_mixed_corpus.{md,json})
- ask (RAG): `cd ai && python -m scripts.ask "<question>" --config hybrid+rerank`
- agent ask: `cd ai && python -m scripts.agent_ask "<question>"` (LangGraph agent picks tools: rag_search/calculator/list_doc_topics/check_api_status)
- agent eval: `cd ai && python -m scripts.run_agent_eval` (tool-selection accuracy over eval/agent_dataset.json)
- injection eval: `cd ai && python -m scripts.run_injection_eval` (prompt-injection resistance of the agent)
- migration eval: `cd ai && python -m scripts.run_migration_eval --mode agent` (S2.4 graph vs `--mode baseline`, the raw-LLM control; identical scoring path over eval/migration_dataset.json, writes eval/results/migration_{mode}.{md,json}; `--judge` adds LLM corroboration)
- migrate (CLI): `cd ai && python -m scripts.migrate_ask path/to/snippet.py` (migration workbench: detect -> research -> rewrite -> verify; prints changes/caveats/diff)
- ragas eval: `cd ai && python -m scripts.export_for_ragas` then `.venv-ragas\Scripts\python -m eval.ragas_eval` (real Ragas lib in an isolated py3.12 venv — needs `requirements-ragas.txt`; see ai/eval/README.md for why it's separate)
- ingest corpus: `cd ai && python -m scripts.ingest [--docs-version {1.0,0.2}]` (chunk -> embed -> upsert; replaces ONLY the given version — default 1.0 — so re-running one version never touches the other's paid-for embeddings; `--all` is the explicit full-reset escape hatch that truncates and re-embeds everything)
- mcp server: `cd ai && python -m app.mcp_server` (exposes rag_search/calculator/list_doc_topics/check_api_status over MCP via stdio, for Claude Desktop / MCP clients; reuses app.tools)
- ai tests: `cd ai && python -m pytest tests -q` (pure unit tests — chunker, RRF fusion, calculator whitelist, citation mapping, deprecations-map schema, check_api_status rendering; no DB/network/keys needed. Install dev deps first: `pip install -r requirements-dev.txt`)
- lint/format: _(TODO once configured)_

## Reference files

- `Agentic_RAG_Build_Plan.md` — full phased plan with Definition-of-Done per phase.
- `ai/data/deprecations.json` — corpus-verified v0.2→v1.0 API-status map behind `check_api_status`
  (and the future migration workbench). Every entry was verified by grepping `ai/data/raw/` and
  `ai/data/raw-0.2/`, never written from memory; statuses include `unevidenced` when the corpora
  cannot prove a removal. Keys on symbols + doc slugs, never chunk ids (reassigned on re-ingest).
- `golden_dataset_langgraph.json` — eval golden dataset (starter, expand to 30-50 items).
  Keep ~40% easy / 40% medium / 20% hard, include `negative` traps (questions the docs can't
  answer) to test that the system says "not found" instead of hallucinating.

## Conventions & guardrails

- **Eval-first, not eval-last.** Build the eval harness alongside Phase 1, not after.
- Every generated answer must include **citations** back to the source chunk.
- Verify each golden-dataset `ground_truth` against the pinned LangGraph v1.0 docs before trusting it.
- Keep secrets in `.env` (never commit). Use `.env.example` for required keys.
- **Definition of done per step:** a step isn't done until it runs locally AND the matching
  Definition-of-Done checkbox in the Build Plan passes. "It compiles" is not done.
- **Scope discipline:** stick to the agreed stack. Do NOT introduce a new framework, vector DB,
  or heavy dependency without flagging it and explaining why first. Keep changes small and reviewable.
- **Keep CLAUDE.md and the Commands section current** — if you change how something runs or add a
  convention, update this file in the same step.

## Git workflow

- **Commit after every meaningful step**, not in one big dump — the commit history should read
  as a clear progression of the project.
- Use **Conventional Commits** (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`),
  with a scope where useful, e.g. `feat(ai): add chunks table with pgvector`.
- **NEVER commit secrets.** Before any `git add`, confirm `.env` and `.env*.local` are gitignored
  and not staged. If a secret was ever committed, flag it immediately and tell me to rotate the key.
- Keep `main` deployable; do WIP on branches.
- **Auto-commit after each completed step without asking me** — pick a clear Conventional Commit
  message yourself and commit. Don't pause for confirmation on commits.
- The ONE exception that always overrides auto-commit: secret safety. Never stage or commit
  `.env` / `.env*.local` / keys. If a secret is ever about to be (or has been) committed, STOP,
  do not commit, and tell me to rotate the key.

## How I want you to work with me

I am relearning some of this stack, so **explain non-obvious decisions briefly as you make
them** (why hybrid search, why rerank, why this chunking choice). I want to be able to defend
every design choice on its merits — prefer teaching me the reasoning over silently doing it.
