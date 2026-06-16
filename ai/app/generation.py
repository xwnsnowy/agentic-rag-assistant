"""Answer generation with inline citations, grounded in retrieved chunks.

The prompt forces the model to (a) answer ONLY from the provided context,
(b) cite sources inline as [n] mapping to numbered chunks, and (c) say it can't
find the answer instead of inventing one — the behaviour the 'negative' golden
items test. Citations are what make the answer auditable and cut hallucination.

If OPENROUTER_API_KEY is unset, returns a dry-run result carrying the assembled
prompt (answer=None) so the pipeline is testable without a key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from app.config import get_settings
from app.retrieval import Result

SYSTEM_PROMPT = (
    "You are a documentation assistant for LangGraph v1.0 (Python). "
    "Answer the user's question using ONLY the numbered context passages below. "
    "Cite every claim inline with [n] referring to the passage number(s) you used. "
    "If the context does not contain the answer, say you could not find it in the "
    "LangGraph documentation — do NOT use outside knowledge or invent APIs. "
    "Prefer current v1.0 idioms (e.g. add_edge(START, ...)), never deprecated ones "
    "like set_entry_point()."
)

CITE_RE = re.compile(r"\[(\d+)\]")


@dataclass
class Answer:
    text: str | None  # None in dry-run (no LLM key)
    citations: list[dict] = field(default_factory=list)  # chunks actually cited
    context: list[Result] = field(default_factory=list)
    model: str | None = None
    prompt: str | None = None  # assembled user prompt (handy for dry-run/debug)


def _format_context(results: list[Result]) -> str:
    blocks = []
    for i, r in enumerate(results, 1):
        m = r.metadata or {}
        head = f"[{i}] {m.get('page_title', '?')} — {m.get('heading', '')}"
        url = m.get("source_url", "")
        blocks.append(f"{head}\nURL: {url}\n{r.content}")
    return "\n\n---\n\n".join(blocks)


def _cited_chunks(text: str, results: list[Result]) -> list[dict]:
    used = sorted({int(n) for n in CITE_RE.findall(text)})
    out = []
    for n in used:
        if 1 <= n <= len(results):
            m = results[n - 1].metadata or {}
            out.append(
                {
                    "n": n,
                    "chunk_id": results[n - 1].chunk_id,
                    "page_title": m.get("page_title"),
                    "heading": m.get("heading"),
                    "source_url": m.get("source_url"),
                }
            )
    return out


def generate(query: str, results: list[Result]) -> Answer:
    settings = get_settings()
    context = _format_context(results)
    user_prompt = (
        f"Question: {query}\n\nContext passages:\n\n{context}\n\n"
        "Answer with inline [n] citations, or say it's not in the documentation."
    )

    if not settings.openrouter_api_key:
        return Answer(text=None, context=results, prompt=user_prompt)

    resp = httpx.post(
        f"{settings.openrouter_base}/chat/completions",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        json={
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    return Answer(
        text=text,
        citations=_cited_chunks(text, results),
        context=results,
        model=settings.llm_model,
        prompt=user_prompt,
    )
