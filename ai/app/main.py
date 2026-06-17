"""FastAPI entrypoint for the AI service.

Surface area:
  GET  /            -> service banner
  GET  /health      -> liveness (no external deps)
  GET  /db/health   -> checks the Postgres/Neon connection
  POST /ask         -> run the RAG pipeline, return answer + citations

Run locally:  uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent import run_agent
from app.config import get_settings
from app.db import ping
from app.pipeline import CONFIGS, HYBRID_RERANK, answer_question

settings = get_settings()
_CONFIG_BY_NAME = {c.name: c for c in CONFIGS}

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


class AskRequest(BaseModel):
    question: str
    config: str = HYBRID_RERANK.name  # baseline | hybrid | hybrid+rerank | keyword


@app.post("/ask")
def ask(req: AskRequest):
    """Answer a question with the RAG pipeline. Sync def -> runs in a threadpool."""
    cfg = _CONFIG_BY_NAME.get(req.config, HYBRID_RERANK)
    ans = answer_question(req.question, cfg)
    return {
        "question": req.question,
        "config": cfg.name,
        "answer": ans.text,
        "citations": ans.citations,
    }


class AgentRequest(BaseModel):
    question: str


@app.post("/agent")
def agent_endpoint(req: AgentRequest):
    """Run the LangGraph agent: it picks tools (rag_search/calculator/topics)."""
    res = run_agent(req.question)
    return {
        "question": req.question,
        "answer": res.answer,
        "tools_used": res.tools_used,
        "rounds": res.rounds,
    }
