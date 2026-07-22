"""Run the migration eval and print/save the table.

Usage (from ai/):
  python -m scripts.run_migration_eval                 # baseline (bare LLM, no retrieval/tools)
  python -m scripts.run_migration_eval --judge         # + LLM-judge corroboration
  python -m scripts.run_migration_eval --mode agent    # S2.4 migration graph (not built yet)

`--mode baseline` is the control this whole phase is measured against: one bare
chat call per snippet ("migrate this to LangGraph v1.0"), no retrieval, no
tools, no pinned docs. It is a *fair* baseline, not a strawman - the prompt
gives the model the same output channels the agent will have (unchanged-is-ok,
a changes list, a caveats list); what it cannot have is grounding. Citation
coverage is therefore 0 by construction: with no docs there is nothing real to
cite, and asking the bare model to invent slugs would manufacture fake
grounding, which is worse than measuring its absence.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.migration_harness import (  # noqa: E402
    Change,
    MigrationOutput,
    render_markdown,
    run_migration_eval,
)

RESULTS = Path(__file__).resolve().parents[1] / "eval" / "results"

_BASELINE_SYSTEM = (
    "You are a LangGraph migration assistant. The user gives you a Python "
    "snippet written for an older version of LangGraph. Migrate it to "
    "LangGraph v1.0. Return ONLY a JSON object with exactly these keys: "
    '"code": string - the full migrated file (return the input code unchanged '
    "if nothing needs migrating), "
    '"changes": array of {"description": string} - one entry per change you '
    "made (empty array if you made none), "
    '"caveats": array of strings - note any API you are uncertain about, '
    "naming the symbol (empty array if none)."
)


def baseline_runner(item: dict) -> MigrationOutput:
    """Bare LLM, one call, no retrieval, no tools - the control condition."""
    from app.llm import chat  # lazy: keep module importable without keys

    text = chat(
        [
            {"role": "system", "content": _BASELINE_SYSTEM},
            {"role": "user", "content": item["legacy_code"]},
        ],
        name="eval.migration_baseline",
        response_format={"type": "json_object"},
    )
    parsed = json.loads(text)
    changes = tuple(
        Change(description=str(c.get("description", "")), citations=())
        for c in parsed.get("changes", [])
        if isinstance(c, dict)
    )
    caveats = tuple(str(c) for c in parsed.get("caveats", []))
    return MigrationOutput(code=str(parsed.get("code", "")), changes=changes, caveats=caveats)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "agent"], default="baseline")
    ap.add_argument("--judge", action="store_true", help="add LLM-judge corroboration")
    args = ap.parse_args()

    if args.mode == "agent":
        raise SystemExit(
            "--mode agent is not implemented until S2.4: the migration graph "
            "(app/migrate.py) does not exist yet. Run --mode baseline."
        )

    from app.config import get_settings  # noqa: PLC0415

    label = f"raw-LLM baseline ({get_settings().llm_model}, no retrieval, no tools)"
    summary = run_migration_eval(baseline_runner, label=label, judge=args.judge)
    md = render_markdown(summary)
    print(md)

    RESULTS.mkdir(parents=True, exist_ok=True)
    out_md = RESULTS / f"migration_{args.mode}.md"
    out_json = RESULTS / f"migration_{args.mode}.json"
    out_md.write_text(md + "\n", encoding="utf-8")
    out_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved -> {out_md}")


if __name__ == "__main__":
    main()
