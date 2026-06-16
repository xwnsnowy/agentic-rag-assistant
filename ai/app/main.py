"""FastAPI entrypoint for the AI service.

Phase 0 surface area:
  GET /            -> service banner
  GET /health      -> liveness (no external deps)
  GET /db/health   -> checks the Postgres/Neon connection

Run locally:  uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import ping

settings = get_settings()

app = FastAPI(title="Agentic RAG — AI Service", version="0.0.1")

# CORS so the Next.js frontend can call this service from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "agentic-rag-ai", "version": app.version, "status": "ok"}


@app.get("/health")
def health():
    """Liveness check — no external dependencies."""
    return {"status": "ok"}


@app.get("/db/health")
def db_health():
    """Readiness check — verifies the database connection."""
    try:
        ok = ping()
        return {"status": "ok" if ok else "error", "database": "reachable"}
    except Exception as exc:  # noqa: BLE001 - surface the reason to the caller
        return {"status": "error", "database": "unreachable", "detail": str(exc)}
