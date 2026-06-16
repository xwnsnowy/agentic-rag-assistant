"""Shared chat-completion call via the OpenAI SDK.

When Langfuse is configured we import the `langfuse.openai` drop-in, which traces
every call (model, token usage, cost, latency) with no manual instrumentation;
otherwise we use the plain OpenAI client. Our endpoint is OpenAI-compatible
(base_url + key from settings), so the same code serves OpenAI directly.

generation.py and the eval judge both call chat() so tracing is centralised.
"""

from __future__ import annotations

from functools import lru_cache

from app import observability as obs
from app.config import get_settings


@lru_cache
def _client():
    settings = get_settings()
    if obs.init():
        from langfuse.openai import OpenAI  # traced drop-in
    else:
        from openai import OpenAI
    return OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base)


def chat(messages: list[dict], *, name: str, temperature: float = 0.0) -> str:
    """Run a chat completion and return the assistant text."""
    settings = get_settings()
    kwargs = {"model": settings.llm_model, "messages": messages, "temperature": temperature}
    if obs.init():
        kwargs["name"] = name  # the drop-in accepts a Langfuse observation name
    resp = _client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content
