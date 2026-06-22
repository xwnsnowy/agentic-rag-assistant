# Roadmap

What's been built beyond the core phases, and what's queued. Core phases live in
[PROJECT_STATUS.md](PROJECT_STATUS.md) · [PHASE_0](PHASE_0.md)/[1](PHASE_1.md)/[2](PHASE_2.md).

## ✅ Shipped — expansions

| Area | What | Where |
|---|---|---|
| **UX** | Answers render as **Markdown** (code blocks, lists, links), themed | `web/components/markdown.tsx` |
| **UX** | **shadcn/ui** + **light/dark theme toggle** (next-themes) | `web/components/`, `web/app/` |
| **RAG** | **Query rewriting** (rewrite-retrieve-read) config `hybrid+rerank+rewrite` | `ai/app/query_rewrite.py` |
| **RAG** | **Semantic answer cache** — repeat/near-dup question ~8.5s → ~0.65s (13×) | `ai/app/cache.py` |
| **Safety** | **Prompt-injection eval** — 8 attacks, resistance **1.000** | `ai/eval/injection_*` |
| **Resilience** | Rerank **degrades to hybrid** on Cohere failure (no 500) | `ai/app/rerank.py` |
| **Ops** | **GitHub Actions**: CI (web build + ai syntax), gated eval regression job, keep-warm cron | `.github/workflows/` |
| **Deploy** | Live: Vercel + Render + Neon, CORS wired | [DEPLOY.md](DEPLOY.md) |

Run the new evals:
```bash
cd ai
python -m scripts.run_eval --judge        # now also compares hybrid+rerank+rewrite
python -m scripts.run_injection_eval      # prompt-injection resistance
```

## 🔜 Queued — high signal

- **Corrective-RAG (CRAG):** grade retrieved docs, re-retrieve / widen when low quality.
- **Conversational memory (multi-turn):** persist threads via a LangGraph checkpointer
  (strong meta-angle — the very mechanism the docs describe); pass `thread_id` through API + UI.
- **Embedding-model ablation:** `text-embedding-3-small` vs `-large` vs Voyage/Cohere — comparison table.
- **chunk-size / top-k ablation:** sweep params, pick the optimum by the eval.
- **Streaming UX:** token streaming + live "agent is using tool X" (Vercel AI SDK / SSE).
- **Eval dashboard page:** render the eval tables + Langfuse metrics inside the web app.
- **Auth + chat history:** user accounts (Kinde/Clerk) + persist conversations (`chat_logs`).
- **web_search tool (Tavily):** answer beyond the docs; measure tool-selection on mixed queries.
- **Metric-threshold gate in CI:** fail a PR if `hybrid+rerank` MRR drops below a floor.
- **Citation preview:** hover/click `[n]` to show the source chunk.

## 🧱 Known limitations (honest)

- **Cohere trial key expired** → live rerank degrades to hybrid (eval table was produced
  while the key was valid). Drop in a fresh key to re-enable live reranking.
- **Langfuse keys** on Render are wrong (401) → production traces aren't recorded (local
  traces exist). Non-fatal; re-paste clean keys to enable.
- **Semantic cache is process-local** (in-memory) — swap for Redis/pg in real production.
- **Render free tier** cold-starts (~60s first request) — mitigated by the keep-warm cron.
