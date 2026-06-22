"""Query rewriting: turn a raw user question into a retrieval-optimized query.

A short LLM step that strips chit-chat, expands abbreviations, and keeps the key
LangGraph technical terms — so first-stage retrieval matches better. This is the
classic "rewrite-retrieve-read" enhancement; the eval measures whether it helps.

Falls back to the original query if no LLM key is configured or the call fails.
"""

from __future__ import annotations

from app.config import get_settings
from app.llm import chat

_SYSTEM = (
    "You rewrite a user's question into a concise search query for retrieving "
    "LangGraph v1.0 documentation. Keep the key technical terms, expand vague "
    "references, drop greetings/filler. Return ONLY the rewritten query, one line, "
    "no quotes or explanation."
)


def rewrite_query(query: str) -> str:
    settings = get_settings()
    if not settings.openrouter_api_key:
        return query
    try:
        out = chat(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": query},
            ],
            name="rag.rewrite_query",
        ).strip()
        # Guard against the model returning something empty or absurdly long.
        return out if 0 < len(out) <= 300 else query
    except Exception:  # noqa: BLE001 - best-effort enhancement
        return query
