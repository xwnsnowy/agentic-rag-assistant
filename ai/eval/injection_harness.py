"""Prompt-injection resistance eval for the agent.

Runs each attack through the agent and uses an LLM judge to decide whether the
agent resisted (didn't leak its prompt/secrets, didn't follow the injection).
"""

from __future__ import annotations

import json
from pathlib import Path

from app import observability as obs
from app.agent import run_agent
from eval.judge import judge_injection

DATASET = Path(__file__).resolve().parent / "injection_dataset.json"


def run_injection_eval() -> dict:
    items = json.loads(DATASET.read_text(encoding="utf-8"))["items"]
    rows, resisted = [], 0
    for it in items:
        try:
            ans = run_agent(it["attack"]).answer
            ok = judge_injection(it["attack"], ans)
        except Exception:  # noqa: BLE001
            ans, ok = "", False
        resisted += ok
        rows.append({"id": it["id"], "resisted": ok, "answer": ans[:120]})
    obs.flush()
    return {"n": len(items), "resistance": resisted / len(items) if items else 0.0, "rows": rows}


def render(summary: dict) -> str:
    lines = [
        "# Prompt-injection resistance",
        "",
        f"- attacks: {summary['n']}",
        f"- **resistance: {summary['resistance']:.3f}** (fraction the agent did NOT comply with)",
        "",
        "| id | resisted |",
        "|---|---|",
        *[f"| {r['id']} | {'✓' if r['resisted'] else '✗'} |" for r in summary["rows"]],
    ]
    return "\n".join(lines)
