"""Thin Postgres access layer using psycopg3.

Connections come from a process-wide psycopg_pool. Neon sits behind TLS and a
cold connect costs 300ms-1s; a request does two queries (vector + keyword), so
without a pool every answer paid that twice. The pool is opened lazily on first
use so importing this module (tests, the MCP server) never touches the network.
Vectors are passed as text literals (e.g. '[0.1,0.2,...]') and cast with
::vector in SQL, which avoids needing an extra pgvector Python adapter.
"""

import atexit
from contextlib import contextmanager
from threading import Lock

from psycopg_pool import ConnectionPool

from app.config import get_settings

_pool: ConnectionPool | None = None
_pool_lock = Lock()


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                settings = get_settings()
                if not settings.database_url:
                    raise RuntimeError(
                        "DATABASE_URL is not set. Copy ai/.env.example to ai/.env and point it "
                        "at your Neon (pooled) connection string."
                    )
                # Small and bounded: Neon's pooled endpoint already multiplexes,
                # and a single uvicorn worker serves a handful of streams at
                # once. max_idle recycles connections before Neon's idle
                # suspend closes them under us; check= drops dead ones.
                _pool = ConnectionPool(
                    settings.database_url,
                    min_size=1,
                    max_size=6,
                    max_idle=240.0,
                    check=ConnectionPool.check_connection,
                    open=True,
                )
                # Short-lived scripts (ingest, eval) otherwise hit the pool's
                # __del__ during interpreter finalization, where its worker
                # threads can no longer be joined.
                atexit.register(_pool.close)
    return _pool


@contextmanager
def get_connection():
    """Yield a pooled psycopg connection. Raises a clear error if DATABASE_URL is unset."""
    with _get_pool().connection() as conn:
        yield conn


def vector_literal(values: list[float]) -> str:
    """Format a Python float list as a pgvector text literal: '[1,2,3]'."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def ping() -> bool:
    """Return True if the DB answers SELECT 1. Used by the /db/health endpoint."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
