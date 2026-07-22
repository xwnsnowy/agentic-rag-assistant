"""FastAPI entrypoint for the AI service.

Surface area:
  GET  /            -> service banner
  GET  /health      -> liveness (no external deps)
  GET  /db/health   -> checks the Postgres/Neon connection
  POST /ask         -> run the RAG pipeline, return answer + citations
  POST /agent       -> run the LangGraph agent (picks tools), return full answer
  POST /agent/stream-> same agent, streamed token-by-token over SSE
  POST /migrate     -> migration workbench (detect/research/rewrite/verify)
  POST /migrate/stream -> same graph over SSE, + a `result` event with the diff

Run locally:  uvicorn app.main:app --reload --port 8000
"""

import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import astream_agent, run_agent
from app.config import get_settings
from app.db import ping
from app.migrate import astream_migrate, run_migrate
from app.pipeline import CONFIGS, HYBRID_RERANK, answer_question

settings = get_settings()
_CONFIG_BY_NAME = {c.name: c for c in CONFIGS}
logger = logging.getLogger(__name__)

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
    except Exception:  # noqa: BLE001
        # Never echo the exception to the client: psycopg errors routinely embed
        # the DSN (host/user, sometimes credentials) and this endpoint is public.
        # The operator gets the full detail in the server log instead.
        logger.exception("/db/health: database ping failed")
        return {"status": "error", "database": "unreachable"}


class AskRequest(BaseModel):
    question: str
    config: str = HYBRID_RERANK.name  # baseline | hybrid | hybrid+rerank | keyword


@app.post("/ask")
def ask(req: AskRequest):
    """Answer a question with the RAG pipeline. Sync def -> runs in a threadpool."""
    cfg = _CONFIG_BY_NAME.get(req.config, HYBRID_RERANK)
    ans = answer_question(req.question, cfg, use_cache=True)
    return {
        "question": req.question,
        "config": cfg.name,
        "answer": ans.text,
        "citations": ans.citations,
    }


class AgentRequest(BaseModel):
    question: str
    thread_id: str | None = None  # pass to keep short-term memory across turns


@app.post("/agent")
def agent_endpoint(req: AgentRequest):
    """Run the LangGraph agent: it picks tools (rag_search/calculator/topics).

    Pass a stable thread_id to enable multi-turn memory (follow-up questions).
    """
    res = run_agent(req.question, thread_id=req.thread_id)
    return {
        "question": req.question,
        "answer": res.answer,
        "tools_used": res.tools_used,
        "rounds": res.rounds,
        "thread_id": res.thread_id,
        "citations": res.citations,
        # Additive (S1.2): one serialized RetrievalTrace per rag_search call —
        # lets you inspect the pool/scores with plain curl. The frontend's
        # AgentResponse type simply ignores the extra key.
        "retrieval_traces": res.retrieval_traces,
    }


@app.post("/agent/stream")
async def agent_stream_endpoint(req: AgentRequest):
    """Same as /agent, but streams the answer token-by-token over SSE.

    Each line is `data: {json}\\n\\n` with an event of type
    token | tools | node | retrieval | citations | done.
    The frontend reads the body with a stream reader and appends tokens live.
    """

    async def sse():
        async for ev in astream_agent(req.question, thread_id=req.thread_id):
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Disable proxy buffering (e.g. Render/nginx) so tokens flush immediately.
            "X-Accel-Buffering": "no",
        },
    )


class MigrateRequest(BaseModel):
    code: str


@app.post("/migrate")
def migrate_endpoint(req: MigrateRequest):
    """Run the migration workbench graph (S2.4). Sync def -> threadpool.

    Non-streaming mirror of /migrate/stream, for curl/debugging: the same
    result payload plus the findings/citations/retrieval traces out-of-band.
    """
    res = run_migrate(req.code)
    return {
        "original": res.original,
        "rewritten": res.rewritten,
        "changes": res.changes,
        "caveats": res.caveats,
        "diff": res.diff,
        "error": res.error,
        "verified": res.verified,
        "attempts": res.attempts,
        "findings": res.findings,
        "citations": res.citations,
        "retrieval_traces": res.retrieval_traces,
    }


@app.post("/migrate/stream")
async def migrate_stream_endpoint(req: MigrateRequest):
    """The migration graph over SSE — same framing and event vocabulary as
    /agent/stream (node | retrieval | token | citations | done) plus one new
    `result` event carrying {original, rewritten, changes, caveats, diff}.
    The diff is produced server-side (stdlib difflib): deterministic,
    testable, and the client needs no diff dependency.
    """

    async def sse():
        async for ev in astream_migrate(req.code):
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
