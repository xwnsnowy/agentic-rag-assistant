"""Migration workbench (Phase 3 S2.4): detect -> research -> rewrite -> verify.

Why a dedicated graph and not the ReAct agent with a longer prompt: migration
is a pipeline with known stages, not open-ended tool choice. The S2.3 baseline
proved the failure mode is *blindness*, not hallucination — the bare model
returned all 20 snippets unchanged because pre-v1.0 tutorials taught it that
`set_entry_point` is idiomatic. So detection must not depend on the model at
all: `detect` and `verify` are deterministic AST/string code against the
curated map in data/deprecations.json, and the LLM is only trusted with the
one job it is good at (rewriting code given explicit, evidenced instructions).

The epistemics of the map bind this module too:
  - deprecated / renamed / moved  -> "modernize": rewrite, grounded in retrieved
    v1.0 passages, every change citing them.
  - unevidenced                   -> "flag": the code comes back UNCHANGED with a
    deterministic caveat naming the symbol. Absence from a 12-page corpus is
    not proof of removal; silently rewriting would claim evidence we lack.
  - unchanged / unknown           -> untouched. If nothing is actionable the input
    is returned byte-identical without ever visiting an LLM: a model would
    reformat, and reformatting is a change we had no reason to make.
"""

from __future__ import annotations

import ast
import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path

MAX_CODE_CHARS = 8000  # mirrors MAX_QUESTION_CHARS in agent.py, scaled for files
MAX_REWRITE_ATTEMPTS = 2  # one initial rewrite + exactly one verify-driven retry

MODERNIZE_STATUSES = ("deprecated", "renamed", "moved")

_DEPRECATIONS = Path(__file__).resolve().parents[1] / "data" / "deprecations.json"


# --- deterministic core (no LLM, no DB, no network) --------------------------


def validate_input(code: str) -> str | None:
    """Input guardrails; returns a clean user-facing message, or None if OK.

    Rejecting unparseable input up front is load-bearing: detect works on the
    AST, so code we cannot parse is code we cannot honestly analyse — and a
    SyntaxError from deep inside a node would surface as a 500, not a message.
    """
    if not code or not code.strip():
        return "Please provide some Python code to migrate."
    if len(code) > MAX_CODE_CHARS:
        return (
            f"Input is too large ({len(code)} characters; the limit is "
            f"{MAX_CODE_CHARS}). Please migrate one file at a time."
        )
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return (
            f"Input does not parse as Python (line {exc.lineno}: {exc.msg}). "
            "Please fix the syntax first — migration works on valid code only."
        )
    return None


def collect_symbols(tree: ast.AST) -> dict[str, int]:
    """Symbol-ish identifiers used in the tree -> first line number.

    Deliberately covers every way the mapped symbols are actually spelled in
    legacy code: attribute calls (builder.set_entry_point), bare names
    (create_react_agent, SqliteSaver), from-imports, and keyword arguments
    (config_schema=..., interrupt_before=[...]). Exact-name matching only —
    `interrupt` never matches `interrupt_before`.
    """
    found: dict[str, int] = {}

    def add(name: str | None, lineno: int) -> None:
        if name and name not in found:
            found[name] = lineno

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            add(node.attr, node.lineno)
        elif isinstance(node, ast.Name):
            add(node.id, node.lineno)
        elif isinstance(node, ast.keyword):
            add(node.arg, node.value.lineno)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                add(alias.name, node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for part in alias.name.split("."):
                    add(part, node.lineno)
    return found


def _load_entries() -> dict[str, dict]:
    doc = json.loads(_DEPRECATIONS.read_text(encoding="utf-8"))
    return {e["symbol"]: e for e in doc["entries"]}


def detect_findings(code: str) -> list[dict]:
    """Match the code's symbols against deprecations.json. Assumes valid input.

    Returns findings in source order, each tagged with an `action`:
    "modernize" (status deprecated/renamed/moved — a rewrite is evidenced) or
    "flag" (status unevidenced — the code must stay, with a caveat). Symbols
    with status "unchanged" or absent from the map produce no finding.
    """
    entries = _load_entries()
    symbols = collect_symbols(ast.parse(code))
    findings: list[dict] = []
    for sym, line in sorted(symbols.items(), key=lambda kv: (kv[1], kv[0])):
        entry = entries.get(sym)
        if entry is None or entry["status"] == "unchanged":
            continue
        findings.append(
            {
                "symbol": sym,
                "line": line,
                "status": entry["status"],
                "action": "modernize" if entry["status"] in MODERNIZE_STATUSES else "flag",
                "replacement": entry.get("replacement"),
                "doc_slug": entry["doc_slug"],
                "doc_version": entry["doc_version"],
            }
        )
    return findings


def flag_caveat(finding: dict) -> str:
    """Deterministic caveat for an unevidenced symbol — no LLM on this path.

    The caveat MUST name the symbol (a generic "please review" is not a flag)
    and states exactly what the corpora show, nothing more: the map's own
    epistemics, rendered from the map entry.
    """
    parts = [
        f"`{finding['symbol']}` was kept unchanged: the v0.2 docs teach it but "
        "the pinned v1.0 corpus never mentions it, and absence from a 12-page "
        "corpus is not proof of removal."
    ]
    if finding.get("replacement"):
        parts.append(f"The v1.0 docs teach {finding['replacement']} instead.")
    parts.append(f"[{finding['doc_slug']}]")
    return " ".join(parts)


def _strip_fences(code: str) -> str:
    """Drop ```-fence lines a model may wrap its code in despite instructions."""
    return "\n".join(
        ln for ln in code.splitlines() if not ln.strip().startswith("```")
    )


def _parses(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def verify_rewrite(code: str | None, findings: list[dict]) -> list[str]:
    """Deterministic post-rewrite checks. Returns problems; empty == verified.

    Three checks, mirroring what the eval harness will measure:
      1. the rewrite parses (structured LLM output is the flakiest node);
      2. no modernize-symbol survives — as a SUBSTRING, deliberately stricter
         than AST presence, because a leftover mention in a comment or string
         is still the deprecated name shipped back to the user;
      3. every flag-symbol is still present (AST) — an LLM that "helpfully"
         rewrote an unevidenced API contradicted the map and must be caught.
    """
    if not code or not code.strip():
        return ["the rewrite produced no code"]
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"the rewrite is not valid Python (line {exc.lineno}: {exc.msg})"]
    problems = []
    for f in findings:
        if f["action"] == "modernize" and f["symbol"] in code:
            problems.append(
                f"the deprecated symbol {f['symbol']} still appears in the "
                "rewrite; it must be fully replaced (do not mention it even "
                "in comments)"
            )
    present = collect_symbols(tree)
    for f in findings:
        if f["action"] == "flag" and f["symbol"] not in present:
            problems.append(
                f"the unevidenced symbol {f['symbol']} was removed; it must "
                "remain in the code exactly as written"
            )
    return problems


def make_diff(original: str, rewritten: str) -> str:
    """Server-side unified diff — stdlib difflib: deterministic, testable, and
    the client needs no diff dependency. Empty string when nothing changed."""
    if original == rewritten:
        return ""
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            rewritten.splitlines(keepends=True),
            fromfile="legacy.py",
            tofile="migrated.py",
        )
    )


@dataclass
class MigrateResult:
    original: str
    rewritten: str  # == original when nothing was (or could safely be) changed
    changes: list[dict] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    diff: str = ""
    findings: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)  # sink sources the changes cite
    retrieval_traces: list[dict] = field(default_factory=list)
    attempts: int = 0
    verified: bool = True
    error: str | None = None
