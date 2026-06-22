# Changelog

## 2026-06-23

### Added
- **shadcn/ui + light/dark theme toggle** (next-themes) — chat UI rebuilt on shadcn
  primitives; Markdown rendering for answers (code blocks, lists, links).
- **Multi-turn memory** for the agent via a LangGraph checkpointer (`thread_id`,
  `MemorySaver`) — follow-up questions resolve context ("can I use *it* with
  Postgres?"); "New chat" button in the UI.
- **In-app eval dashboard** at `/eval` — retrieval comparison, Ragas, agent
  tool-selection, injection resistance, cache speed-up, shown without reading the repo.
- **Query rewriting** retrieval config `hybrid+rerank+rewrite` (rewrite-retrieve-read).
- **Semantic answer cache** — repeat / near-duplicate questions ~8.5s → ~0.65s (13×).
- **Prompt-injection eval** — 8 attacks, resistance **1.000**.
- **GitHub Actions**: CI (web build + ai syntax), gated eval regression job, keep-warm cron.
- **Docs**: `ROADMAP.md`, `RATIONALE.md` (design rationale + interview FAQ incl. "vs ChatGPT",
  pgvector vs vector DB, heading-chunking, version pinning, small model, eval method).
- **Cold-start UX** (from the AI-PM review): web pre-warms `/health` on load + shows a
  clear "waking up the server (~40s)…" state instead of a blank wait; UptimeRobot
  keep-warm guidance in `DEPLOY.md`.

### Changed
- Rerank now **degrades to hybrid** on Cohere failure (no 500) — best-effort enhancement.

### Reviewed (AI-PM audit, verified on live)
- Strong portfolio (~8/10), interview-ready. Weak links are **operational, not features**:
  - **P0 cold start** measured ~42s on first request → mitigated (pre-warm + loading state;
    recommend UptimeRobot 5-min ping).
  - **P0 security** — exposed OpenAI key still in use on the public deploy → **rotate**.
  - **P1 story drift** — live rerank degraded (Cohere trial key expired) so live runs
    *hybrid*, not *hybrid+rerank* as advertised → drop in a fresh Cohere key.

### Pending (next session)
- [ ] **Rotate OpenAI key** → update `ai/.env` + Render env, verify pipeline/agent.
- [ ] **Fresh Cohere key** (free) → re-enable live reranking; optionally re-run `run_eval --judge`.
- [ ] **UptimeRobot** monitor on `/health` (every 5 min) to kill cold starts 24/7.
- [ ] (optional) Fix Langfuse keys on Render for production traces.

### Deferred (with reason)
- Full eval re-run including the new `+rewrite` config — **deferred** until a fresh Cohere
  key, since running it now (key expired) would regress the committed flagship numbers.
