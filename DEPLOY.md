# Deploy

Continuous deploy, no Docker: **web → Vercel**, **ai → Render**, **DB → Neon**.
Push to `main` redeploys. All secrets live in each platform's dashboard — never committed.

```
[Vercel] Next.js  ──HTTPS──►  [Render] FastAPI  ──►  [Neon] Postgres + pgvector
 NEXT_PUBLIC_API_URL            CORS_ORIGINS            DATABASE_URL (pooled)
```

## 1. Database — Neon (already used in dev)

The same Neon database that holds the ingested chunks serves production. Make sure the
`vector` extension is enabled and the corpus is ingested (`python -m scripts.ingest`).
Use the **pooled** connection string for `DATABASE_URL`.

## 2. AI service — Render

1. New → **Blueprint**, point at this repo. Render reads [render.yaml](render.yaml) at the
   repo root (it sets `rootDir: ai`, native Python, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
2. Fill the `sync:false` env vars in the dashboard: `DATABASE_URL`, `EMBEDDING_API_KEY`,
   `OPENROUTER_API_KEY`, `COHERE_API_KEY`, `LANGFUSE_*`, and `CORS_ORIGINS`
   (your Vercel URL, e.g. `https://your-app.vercel.app`).
3. Health check is `/health`. After deploy, verify `GET /db/health` returns `reachable`.

> First request is slow on the free plan (cold start + heavy imports). That's expected.

## 3. Web — Vercel

1. Import the repo, set **Root Directory** to `web/` (zero-config Next.js, uses pnpm).
2. Add env var `NEXT_PUBLIC_API_URL` = your Render URL (e.g. `https://agentic-rag-ai.onrender.com`).
3. Deploy. The chat UI calls the Render API; make sure that URL is in the API's `CORS_ORIGINS`.

## 4. Wire-up checklist

- [ ] Neon `vector` extension on, corpus ingested
- [ ] Render env vars set; `/health` green, `/db/health` reachable
- [ ] `CORS_ORIGINS` on Render = the Vercel domain
- [ ] `NEXT_PUBLIC_API_URL` on Vercel = the Render URL
- [ ] Open the Vercel URL, ask a question in both RAG and Agent modes

## Keep the API warm (avoid the ~40s cold start)

Render's free tier spins the API down after ~15 min idle, so the first request
then takes ~40s. Two mitigations are in place + recommended:

1. **Frontend pre-warm** — the web app pings `/health` on page load, so the API
   is usually awake by the time the visitor types a question. The chat also shows
   a "waking up the server…" message if a request runs long (no blank wait).
2. **External uptime pinger (recommended, most reliable):** create a free
   [UptimeRobot](https://uptimerobot.com) HTTP monitor on
   `https://agentic-rag-ai-fspt.onrender.com/health`, interval **5 minutes**. This
   keeps the instance warm 24/7. (A `keep-warm` GitHub Action also exists, but
   GitHub disables scheduled workflows on inactive repos and cron timing is loose —
   UptimeRobot is steadier.)
3. Or upgrade the Render instance to a paid plan (always-on).

## Notes

- Keep `main` deployable; do WIP on branches (preview deploys on both platforms).
- Ragas eval is a local-only dev tool (separate venv) — not part of the deployed service.
- Rotate any API key that has been shared outside the dashboards.
