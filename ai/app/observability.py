"""Langfuse observability — optional, no-op when keys are absent.

LLM calls go through the `langfuse.openai` drop-in (see app/llm.py), which
auto-captures model, token usage, cost and latency. This module just owns the
on/off decision and makes sure the Langfuse SDK can see its keys (the drop-in and
get_client() read them from the environment).
"""

from __future__ import annotations

import os
from functools import lru_cache

from app.config import get_settings


@lru_cache
def init() -> bool:
    """Return True if Langfuse is configured, exporting keys to the env so the
    SDK / OpenAI drop-in pick them up. Cached: runs once."""
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return False
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
    return True


def client():
    """Return the Langfuse singleton, or None when disabled."""
    if not init():
        return None
    try:
        from langfuse import get_client

        return get_client()
    except Exception:  # noqa: BLE001 - never let observability break the app
        return None


def flush() -> None:
    """Flush buffered events before a short-lived process exits."""
    c = client()
    if c:
        c.flush()
