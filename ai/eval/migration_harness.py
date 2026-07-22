"""Migration eval harness (S2.3): deterministic metrics for the workbench.

Why deterministic-first: `ast.parse`, substring must/must-not checks and slug
matching are free, reproducible in CI, and immune to judge drift. The optional
LLM judge (--judge) only corroborates - exactly the role Ragas plays for
retrieval. That mirror is deliberate: the numbers the project stands on must
never depend on a model's mood.

The harness is runner-agnostic: `run_migration_eval` takes any callable
`(item: dict) -> MigrationOutput`, so the raw-LLM baseline (S2.3) and the
migration graph (S2.4) are scored by the *same* code and the comparison is
apples-to-apples by construction.

Metrics, and which kinds they apply to:
  parses               (all)       ast.parse accepts the produced code
  deprecated_removed   (modernize) no must_not_contain string survives
  idiom_present        (modernize) every must_contain string is present
  citation_coverage    (modernize) fraction of reported changes carrying >=1
                                   citation whose slug is in
                                   expected_citation_slugs; an item that was
                                   supposed to change but reports no changes
                                   scores 0
  clean_passthrough    (clean)     the code came back unchanged
  flagged_not_rewritten(flag)      the code came back unchanged AND a caveat
                                   names the unevidenced symbol. Rewriting an
                                   unevidenced symbol - even loudly, even to
                                   the v1.0-taught alternative - scores 0:
                                   absence from a 12-page corpus is not proof
                                   of removal, and the map's epistemics bind
                                   the tool too.

"Unchanged" is deliberately strict: identical modulo trailing whitespace and
blank lines (see `normalize_code`). Indentation and every token must match -
we do NOT use AST equality, because a reformat still touched code the tool had
no evidence to touch. The S2.4 graph can trivially meet this bar by returning
its input verbatim when the deterministic detect node finds nothing.
"""

from __future__ import annotations

import ast
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DATASET = Path(__file__).resolve().parent / "migration_dataset.json"

KINDS = ("modernize", "flag", "clean")

# metric -> kinds it is scored on ("*" = every kind)
METRIC_KINDS = {
    "parses": "*",
    "deprecated_removed": ("modernize",),
    "idiom_present": ("modernize",),
    "citation_coverage": ("modernize",),
    "clean_passthrough": ("clean",),
    "flagged_not_rewritten": ("flag",),
}


@dataclass(frozen=True)
class Change:
    """One reported change: what was done and which doc pages back it."""

    description: str
    citations: tuple[str, ...] = ()  # page slugs, e.g. ("graph-api",)


@dataclass(frozen=True)
class MigrationOutput:
    """The common output contract every runner (baseline or agent) maps into."""

    code: str
    changes: tuple[Change, ...] = ()
    caveats: tuple[str, ...] = ()


def load_dataset() -> list[dict]:
    return json.loads(DATASET.read_text(encoding="utf-8"))["items"]


def normalize_code(code: str) -> tuple[str, ...]:
    """Whitespace-insensitive-but-token-strict view of a snippet.

    Keeps leading indentation (semantic in Python), drops blank lines and
    trailing whitespace, and ignores a ```python fence if a model wrapped its
    answer despite instructions - fence noise is formatting, not a code change.
    """
    lines = [ln.rstrip() for ln in code.strip().splitlines()]
    return tuple(
        ln for ln in lines if ln.strip() and not ln.strip().startswith("```")
    )


def _parses(code: str) -> bool:
    if not code.strip():
        return False  # no code is not parseable code
    try:
        ast.parse(_strip_fences(code))
        return True
    except SyntaxError:
        return False


def _strip_fences(code: str) -> str:
    return "\n".join(
        ln for ln in code.splitlines() if not ln.strip().startswith("```")
    )


def _has_caveat(out: MigrationOutput, symbols: list[str]) -> bool:
    """A caveat counts only if it names one of the item's unevidenced symbols -
    a generic 'please review' disclaimer is not a flag."""
    return any(sym in caveat for caveat in out.caveats for sym in symbols)


def _citation_coverage(out: MigrationOutput, expected_slugs: list[str]) -> float:
    if not out.changes:
        return 0.0  # a modernize item must report what it changed
    covered = sum(
        1
        for ch in out.changes
        if any(slug in expected_slugs for slug in ch.citations)
    )
    return covered / len(out.changes)


def score_item(item: dict, out: MigrationOutput) -> dict:
    """Score one item; metrics that don't apply to its kind are absent."""
    kind = item["kind"]
    code = out.code
    unchanged = normalize_code(code) == normalize_code(item["legacy_code"])

    scores: dict = {"parses": _parses(code)}
    if kind == "modernize":
        scores["deprecated_removed"] = not any(
            bad in code for bad in item["must_not_contain"]
        )
        scores["idiom_present"] = all(good in code for good in item["must_contain"])
        scores["citation_coverage"] = _citation_coverage(
            out, item["expected_citation_slugs"]
        )
    elif kind == "flag":
        scores["flagged_not_rewritten"] = unchanged and _has_caveat(
            out, item["symbols"]
        )
    elif kind == "clean":
        scores["clean_passthrough"] = unchanged
    else:  # pragma: no cover - dataset tests forbid unknown kinds
        raise ValueError(f"unknown kind {kind!r}")
    return scores


def _zero_scores(kind: str) -> dict:
    """All applicable metrics at their floor, for items whose runner raised."""
    scores: dict = {"parses": False}
    for metric, kinds in METRIC_KINDS.items():
        if kinds != "*" and kind in kinds:
            scores[metric] = 0.0 if metric == "citation_coverage" else False
    return scores


def run_migration_eval(
    runner: Callable[[dict], MigrationOutput],
    *,
    label: str,
    judge: bool = False,
) -> dict:
    """Run every dataset item through `runner` and aggregate the metrics."""
    items = load_dataset()
    rows = []
    for item in items:
        t0 = time.perf_counter()
        try:
            out = runner(item)
            err = None
        except Exception as exc:  # noqa: BLE001 - one bad item must not kill the run
            out = MigrationOutput(code="")
            err = f"{type(exc).__name__}: {exc}"
        latency_ms = round((time.perf_counter() - t0) * 1000)

        # A crashed runner must score zero, not vacuous-true: empty code would
        # trivially satisfy must_not_contain and ast.parse('') succeeds.
        scores = _zero_scores(item["kind"]) if err else score_item(item, out)
        row = {
            "id": item["id"],
            "kind": item["kind"],
            "scores": scores,
            "n_changes": len(out.changes),
            "n_caveats": len(out.caveats),
            "latency_ms": latency_ms,
            "error": err,
            "code": out.code,
            "changes": [
                {"description": c.description, "citations": list(c.citations)}
                for c in out.changes
            ],
            "caveats": list(out.caveats),
        }
        if judge:
            row["judge"] = judge_migration(item, out)
        rows.append(row)

    return {
        "label": label,
        "n": len(rows),
        "by_kind": {k: sum(1 for r in rows if r["kind"] == k) for k in KINDS},
        "metrics": _aggregate(rows, judge=judge),
        "rows": rows,
    }


def _aggregate(rows: list[dict], *, judge: bool) -> dict:
    out: dict = {}
    for metric, kinds in METRIC_KINDS.items():
        vals = [
            float(r["scores"][metric])
            for r in rows
            if kinds == "*" or r["kind"] in kinds
        ]
        out[metric] = round(sum(vals) / len(vals), 3) if vals else None
    if judge:
        jvals = [
            r["judge"]["migration_quality"]
            for r in rows
            if r.get("judge") and r["judge"].get("migration_quality") is not None
        ]
        out["judge_migration_quality"] = (
            round(sum(jvals) / len(jvals), 3) if jvals else None
        )
    return out


# --- optional LLM judge (same pattern as eval/judge.py; off by default) -----

_JUDGE_RUBRIC = (
    "You are a strict evaluator for a LangGraph v0.x -> v1.0 migration tool. "
    "You get the LEGACY code, the item KIND with its expectation, and the tool "
    "OUTPUT (code + reported changes + caveats). Expectations: kind=modernize "
    "-> the deprecated API is replaced with the modern v1.0 idiom and nothing "
    "else breaks; kind=flag -> the code is NOT rewritten (the symbol's removal "
    "is unproven) and a caveat states the uncertainty; kind=clean -> the code "
    "comes back unchanged. Return ONLY JSON: "
    '{"migration_quality": 0..1, "reason": "..."}.'
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def judge_migration(item: dict, out: MigrationOutput) -> dict:
    """LLM corroboration of the deterministic scores. Imported lazily so the
    harness (and its pure tests) never needs app/ or an API key."""
    from app.llm import chat  # noqa: PLC0415 - lazy: keeps tests key-free

    user = (
        f"KIND: {item['kind']}\nNOTE: {item['note']}\n\n"
        f"LEGACY:\n{item['legacy_code']}\n\nOUTPUT CODE:\n{out.code}\n\n"
        f"REPORTED CHANGES: {[c.description for c in out.changes]}\n"
        f"CAVEATS: {list(out.caveats)}"
    )
    text = chat(
        [
            {"role": "system", "content": _JUDGE_RUBRIC},
            {"role": "user", "content": user},
        ],
        name="eval.judge_migration",
        response_format={"type": "json_object"},
    )
    m = _JSON_RE.search(text)
    if m:
        try:
            parsed = json.loads(m.group(0))
            return {
                "migration_quality": float(parsed.get("migration_quality"))
                if parsed.get("migration_quality") is not None
                else None,
                "reason": parsed.get("reason", ""),
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return {"migration_quality": None, "reason": "unparseable judge reply"}


# --- rendering ---------------------------------------------------------------

def render_markdown(summary: dict) -> str:
    m = summary["metrics"]
    bk = summary["by_kind"]
    lines = [
        f"# Migration eval — {summary['label']}",
        "",
        f"- items: {summary['n']} "
        f"(modernize {bk['modernize']} / flag {bk['flag']} / clean {bk['clean']})",
        f"- parses: **{m['parses']:.3f}**",
        f"- deprecated_removed (modernize): **{m['deprecated_removed']:.3f}**",
        f"- idiom_present (modernize): **{m['idiom_present']:.3f}**",
        f"- citation_coverage (modernize): **{m['citation_coverage']:.3f}**",
        f"- clean_passthrough (clean): **{m['clean_passthrough']:.3f}**",
        f"- flagged_not_rewritten (flag): **{m['flagged_not_rewritten']:.3f}**",
    ]
    if m.get("judge_migration_quality") is not None:
        lines.append(f"- judge_migration_quality: {m['judge_migration_quality']:.3f}")
    lines += [
        "",
        "| id | kind | parses | removed | idiom | cites | passthrough | flagged | changes | caveats |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in summary["rows"]:
        s = r["scores"]

        def cell(key: str) -> str:
            if key not in s:
                return "—"
            v = s[key]
            if isinstance(v, bool):
                return "✓" if v else "✗"
            return f"{v:.2f}"

        lines.append(
            f"| {r['id']} | {r['kind']} | {cell('parses')} | "
            f"{cell('deprecated_removed')} | {cell('idiom_present')} | "
            f"{cell('citation_coverage')} | {cell('clean_passthrough')} | "
            f"{cell('flagged_not_rewritten')} | {r['n_changes']} | {r['n_caveats']} |"
        )
    return "\n".join(lines)
