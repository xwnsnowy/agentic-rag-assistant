# ai/ — Python AI service (FastAPI)

Embeddings, retrieval, agent, and eval layer. Talks to Postgres + pgvector (Neon).

## Setup (no Docker — local venv)

```bash
cd ai
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # then fill in DATABASE_URL (Neon pooled URL)
```

## Database (Phase 0)

```bash
python -m scripts.init_db      # create pgvector ext + documents + chunks tables
python -m scripts.seed_chunk   # insert 1 chunk + run a cosine-similarity query
```

`seed_chunk` works offline with a fake embedding when `EMBEDDING_API_KEY` is empty;
set the key to use the real `text-embedding-3-small` model.

## Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

- `GET /health` — liveness
- `GET /db/health` — checks the Neon connection

## Layout

```
app/
  config.py      env-driven settings
  db.py          psycopg connection + vector helpers
  embeddings.py  OpenAI-compatible embeddings (+ offline fallback)
  main.py        FastAPI app + health endpoints
migrations/      SQL schema (001_init.sql)
scripts/         init_db.py, seed_chunk.py
```
