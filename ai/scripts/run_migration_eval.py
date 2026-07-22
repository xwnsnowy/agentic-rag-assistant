"""Run the migration eval and print/save the table.

Usage (from ai/):
  python -m scripts.run_migration_eval                 # baseline (bare LLM, no retrieval/tools)
  python -m scripts.run_migration_eval --judge         # + LLM-judge corroboration
  python -m scripts.run_migration_eval --mode agent    # S2.4 migration graph

Both modes are mapped into the same MigrationOutput contract and scored by the
IDENTICAL code path in eval/migration_harness.py — the baseline-vs-agent
comparison is apples-to-apples by construction, never by parallel metrics.

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


def baseline_preamble(summary: dict) -> str:
    """Context header for the published baseline table, computed from the run
    itself so a re-run can never leave stale prose above fresh numbers."""
    rows = summary["rows"]
    n_changes = sum(r["n_changes"] for r in rows)
    n_caveats = sum(r["n_caveats"] for r in rows)
    return (
        "**S2.3 control condition.** One bare chat call per snippet — no retrieval, no\n"
        "tools, no pinned docs. The model gets the same output channels the S2.4 agent\n"
        "will have (unchanged-is-ok, a changes list, a caveats list); what it cannot\n"
        "have is grounding, so `citation_coverage` is 0 by construction — with no docs\n"
        "there is nothing real to cite, and asking it to invent slugs would manufacture\n"
        "fake grounding.\n\n"
        f"Across all {summary['n']} items the bare model reported **{n_changes} changes** and\n"
        f"**{n_caveats} caveats**. Note that `clean_passthrough` and `flagged_not_rewritten`\n"
        "must be read jointly with `deprecated_removed`: a model that never changes\n"
        "anything aces the clean items for free while failing every migration — the\n"
        "clean score is only meaningful once the modernize columns are non-zero.\n\n"
        "Reproduce: `python -m scripts.run_migration_eval --mode baseline` (from `ai/`).\n"
    )


def agent_runner(item: dict) -> MigrationOutput:
    """The S2.4 migration graph, mapped into the SAME output contract the
    baseline uses — the harness cannot tell the runners apart by shape."""
    from app.migrate import run_migrate  # lazy: keep module importable without keys

    res = run_migrate(item["legacy_code"])
    if res.error:  # dataset items all parse, but score a reject honestly as-is
        return MigrationOutput(code="", caveats=(res.error,))
    changes = tuple(
        Change(description=c["description"], citations=tuple(c["citation_slugs"]))
        for c in res.changes
    )
    return MigrationOutput(
        code=res.rewritten, changes=changes, caveats=tuple(res.caveats)
    )


def agent_preamble(summary: dict) -> str:
    """Context header for the agent table; the baseline comparison is loaded
    from the committed baseline JSON so the two files can never disagree."""
    baseline_path = RESULTS / "migration_baseline.json"
    rows = summary["rows"]
    n_changes = sum(r["n_changes"] for r in rows)
    n_caveats = sum(r["n_caveats"] for r in rows)
    lines = [
        "**S2.4 — the migration graph** (`app/migrate.py`): deterministic AST `detect`",
        "against `data/deprecations.json`, `research` via check_api_status + rag_search",
        "over the pinned corpora, one grounded structured-output `rewrite`, deterministic",
        "`verify` with one bounded retry. Scored by the identical harness code path as",
        "the raw-LLM baseline.",
        "",
        f"Across all {summary['n']} items the graph reported **{n_changes} changes** and "
        f"**{n_caveats} caveats**.",
        "",
        "Reproduce: `python -m scripts.run_migration_eval --mode agent` (from `ai/`).",
        "",
    ]
    if baseline_path.exists():
        base = json.loads(baseline_path.read_text(encoding="utf-8"))["metrics"]
        m = summary["metrics"]
        lines += [
            "| metric | raw-LLM baseline | migration graph |",
            "|---|---|---|",
        ]
        for key in (
            "parses",
            "deprecated_removed",
            "idiom_present",
            "citation_coverage",
            "clean_passthrough",
            "flagged_not_rewritten",
        ):
            lines.append(f"| {key} | {base[key]:.3f} | **{m[key]:.3f}** |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "agent"], default="baseline")
    ap.add_argument("--judge", action="store_true", help="add LLM-judge corroboration")
    args = ap.parse_args()

    from app.config import get_settings  # noqa: PLC0415

    if args.mode == "agent":
        label = (
            f"migration graph ({get_settings().llm_model}, "
            "detect -> research -> rewrite -> verify, pinned corpora)"
        )
        summary = run_migration_eval(agent_runner, label=label, judge=args.judge)
        preamble = agent_preamble(summary)
    else:
        label = f"raw-LLM baseline ({get_settings().llm_model}, no retrieval, no tools)"
        summary = run_migration_eval(baseline_runner, label=label, judge=args.judge)
        preamble = baseline_preamble(summary)
    md = render_markdown(summary)
    head, _, rest = md.partition("\n")
    md = f"{head}\n\n{preamble}{rest}"

    # Save BEFORE printing: the run costs real API calls, and a Windows cp1252
    # console choking on a checkmark must not be able to discard the results.
    RESULTS.mkdir(parents=True, exist_ok=True)
    out_md = RESULTS / f"migration_{args.mode}.md"
    out_json = RESULTS / f"migration_{args.mode}.json"
    out_md.write_text(md + "\n", encoding="utf-8")
    out_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    print(md)
    print(f"\nSaved -> {out_md}")


if __name__ == "__main__":
    main()
