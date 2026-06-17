"""Agent eval: tool-selection accuracy over a small labelled set.

For each question we know which tool(s) the agent *should* call. We run the agent,
read which tools it actually called, and score:
  exact      : the called tool-set equals the expected set (no missing, no extra)
  recall     : every expected tool was called (extras allowed)
The no-tool items ([] expected) double as a guardrail check that the agent doesn't
reach for a tool when it shouldn't (e.g. greetings).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app import observability as obs
from app.agent import run_agent

DATASET = Path(__file__).resolve().parent / "agent_dataset.json"


def run_agent_eval() -> dict:
    items = json.loads(DATASET.read_text(encoding="utf-8"))["items"]
    rows = []
    exact_hits = 0
    recall_hits = 0
    for it in items:
        expected = set(it["expected_tools"])
        t0 = time.perf_counter()
        try:
            res = run_agent(it["question"])
            used = set(res.tools_used)
            err = None
        except Exception as exc:  # noqa: BLE001
            used, err = set(), type(exc).__name__
        latency = (time.perf_counter() - t0) * 1000

        exact = used == expected
        recall = expected.issubset(used)
        exact_hits += exact
        recall_hits += recall
        rows.append({
            "id": it["id"], "expected": sorted(expected), "used": sorted(used),
            "exact": exact, "recall": recall, "latency_ms": round(latency), "error": err,
        })

    obs.flush()
    n = len(items)
    return {
        "n": n,
        "tool_selection_exact": exact_hits / n,
        "required_tool_recall": recall_hits / n,
        "rows": rows,
    }


def render(summary: dict) -> str:
    lines = [
        "# Agent tool-selection eval",
        "",
        f"- items: {summary['n']}",
        f"- **tool-selection accuracy (exact set match): {summary['tool_selection_exact']:.3f}**",
        f"- required-tool recall: {summary['required_tool_recall']:.3f}",
        "",
        "| id | expected | used | exact |",
        "|---|---|---|---|",
    ]
    for r in summary["rows"]:
        exp = ", ".join(r["expected"]) or "(none)"
        used = ", ".join(r["used"]) or "(none)"
        mark = "✓" if r["exact"] else "✗"
        lines.append(f"| {r['id']} | {exp} | {used} | {mark} |")
    return "\n".join(lines)
