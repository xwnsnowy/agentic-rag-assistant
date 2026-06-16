"""Thin Postgres access layer using psycopg3.

We keep a single short-lived connection helper for Phase 0. A real connection
pool comes later (Phase 1+) when query volume justifies it. Vectors are passed
as text literals (e.g. '[0.1,0.2,...]') and cast with ::vector in SQL, which
avoids needing an extra pgvector Python adapter.
"""

from contextlib import contextmanager

import psycopg

from app.config import get_settings


@contextmanager
def get_connection():
    """Yield a psycopg connection. Raises a clear error if DATABASE_URL is unset."""
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy ai/.env.example to ai/.env and point it "
            "at your Neon (pooled) connection string."
        )
    conn = psycopg.connect(settings.database_url)
    try:
        yield conn
    finally:
        conn.close()


def vector_literal(values: list[float]) -> str:
    """Format a Python float list as a pgvector text literal: '[1,2,3]'."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def ping() -> bool:
    """Return True if the DB answers SELECT 1. Used by the /db/health endpoint."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
