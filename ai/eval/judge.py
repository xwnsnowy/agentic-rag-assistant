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

from app.config import get_settings
from app.llm import chat

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
    text = chat(
        [
            {"role": "system", "content": _RUBRIC},
            {"role": "user", "content": user},
        ],
        name="eval.judge",
        response_format={"type": "json_object"},  # guarantees valid JSON
    )
    return _parse(text)


_NUM_RE = {
    "faithfulness": re.compile(r'"faithfulness"\s*:\s*([0-9.]+)'),
    "answer_relevancy": re.compile(r'"answer_relevancy"\s*:\s*([0-9.]+)'),
}
_ABSTAIN_RE = re.compile(r'"abstained"\s*:\s*(true|false)')


def _parse(text: str) -> dict:
    """Parse the judge JSON; fall back to regex so one malformed reply can't
    crash the whole eval run."""
    m = _JSON_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    out: dict = {}
    for key, rx in _NUM_RE.items():
        hit = rx.search(text)
        out[key] = float(hit.group(1)) if hit else None
    ab = _ABSTAIN_RE.search(text)
    out["abstained"] = ab.group(1) == "true" if ab else False
    return out
