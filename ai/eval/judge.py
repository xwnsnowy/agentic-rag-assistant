"""LLM-as-judge for generation quality (runs only when OPENROUTER_API_KEY is set).

We score two things Ragas-style:
  faithfulness     : is every claim in the answer supported by the retrieved
                     context? (catches hallucination)
  answer_relevancy : does the answer actually address the question?
For negative (trap) questions, the correct behaviour is to abstain, so we score
`abstained` instead.

The judge is forced to return strict JSON so scores parse deterministically.
"""

from __future__ import annotations

import json
import re

import httpx

from app.config import get_settings

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_RUBRIC = (
    "You are a strict evaluator for a RAG system answering questions about "
    "LangGraph v1.0. Given the QUESTION, the CONTEXT passages the system "
    "retrieved, a reference GROUND_TRUTH, and the system ANSWER, return ONLY a "
    "JSON object: {\"faithfulness\": 0..1, \"answer_relevancy\": 0..1, "
    "\"abstained\": true|false, \"reason\": \"...\"}. "
    "faithfulness = fraction of the answer's claims supported by CONTEXT (1.0 = "
    "fully grounded, no invented facts). answer_relevancy = how well it addresses "
    "the QUESTION. abstained = true if the answer says the info isn't in the docs."
)


def judge_answer(question: str, ground_truth: str, answer: str, context_text: str) -> dict:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY required for the LLM judge")

    user = (
        f"QUESTION:\n{question}\n\nCONTEXT:\n{context_text}\n\n"
        f"GROUND_TRUTH:\n{ground_truth}\n\nANSWER:\n{answer}"
    )
    resp = httpx.post(
        f"{settings.openrouter_base}/chat/completions",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        json={
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": _RUBRIC},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    m = _JSON_RE.search(text)
    return json.loads(m.group(0)) if m else {"faithfulness": None, "answer_relevancy": None}
