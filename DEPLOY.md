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

## Notes

- Keep `main` deployable; do WIP on branches (preview deploys on both platforms).
- Ragas eval is a local-only dev tool (separate venv) — not part of the deployed service.
- Rotate any API key that has been shared outside the dashboards.
