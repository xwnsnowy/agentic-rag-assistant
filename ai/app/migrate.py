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
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app import tools as tools_mod
from app.tools import begin_citation_capture, begin_debug_capture

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


# --- the LangGraph pipeline --------------------------------------------------
#
#   START -> detect -> research -> rewrite -> verify -> END
#                         ^__________________________|   (verify fails -> ONE retry)
#
# detect and verify are the deterministic functions above; research talks to
# check_api_status + rag_search (through the same citation/debug sinks the
# chat agent uses, so numbering and the retrieval inspector work here for
# free); rewrite is the single LLM call. Clean input exits after detect and
# never reaches a model.


class MigrateState(TypedDict, total=False):
    code: str
    error: str | None
    findings: list[dict]
    caveats: list[str]
    evidence: list[dict]  # per finding: verdict + numbered passages
    rewritten: str | None
    changes: list[dict]  # {"description": str, "citations": [int]}
    attempts: int
    verify_ok: bool
    verify_feedback: str | None


def _emit(payload: dict) -> None:
    """Push a UI event through LangGraph's custom stream (no-op off-stream)."""
    try:
        get_stream_writer()(payload)
    except Exception:  # noqa: BLE001 - outside a runnable context (direct calls/tests)
        pass


def _emit_node(name: str, status: str) -> None:
    _emit({"type": "node", "v": {"name": name, "status": status}})


# Test seams: module-level indirection so pure tests monkeypatch these three
# names and the graph runs with zero network/DB/keys.
def _rag_search(query: str, docs_version: str) -> str:
    return tools_mod.rag_search.func(query=query, docs_version=docs_version)


def _check_api_status(symbol: str) -> str:
    return tools_mod.check_api_status.func(symbol=symbol)


def _chat(messages: list[dict], **kwargs) -> str:
    from app.llm import chat  # lazy: keeps the module importable without keys

    return chat(messages, **kwargs)


def _detect_node(state: MigrateState) -> dict:
    _emit_node("detect", "active")
    code = state["code"]
    error = validate_input(code)
    if error:
        return {"error": error, "findings": [], "caveats": []}
    findings = detect_findings(code)
    # Flag caveats are decided HERE, deterministically — the LLM never gets a
    # vote on whether an unevidenced symbol is rewritten.
    caveats = [flag_caveat(f) for f in findings if f["action"] == "flag"]
    return {"error": None, "findings": findings, "caveats": caveats}


def _route_after_detect(state: MigrateState) -> str:
    # Nothing actionable -> END without touching an LLM: the input is returned
    # verbatim (a model would reformat, and a reformat is an unearned change).
    if state.get("error") or not state.get("findings"):
        return END
    return "research"


def _research_node(state: MigrateState) -> dict:
    _emit_node("research", "active")
    if state.get("attempts") and state.get("evidence"):
        # Verify-retry pass: the evidence (and citation numbering) is already
        # gathered; re-retrieving would only duplicate sink entries.
        return {}
    debug = tools_mod._debug_sink.get()
    evidence: list[dict] = []
    for f in state.get("findings", []):
        verdict = _check_api_status(f["symbol"])
        n_before = len(debug) if debug is not None else 0
        if f["action"] == "modernize":
            # Ground the REWRITE: the v1.0 corpus is where the replacement is
            # taught, so that is what the change will cite.
            passages = _rag_search(_research_query(f), "1.0")
        else:
            # Flag findings need the legacy semantics established, and those
            # live where the symbol is actually taught (its doc_version corpus).
            passages = _rag_search(f["symbol"], f["doc_version"])
        if debug is not None:
            for entry in debug[n_before:]:
                _emit({"type": "retrieval", "v": entry})
        evidence.append(
            {
                "symbol": f["symbol"],
                "action": f["action"],
                "verdict": verdict,
                "passages": passages,
            }
        )
    return {"evidence": evidence}


def _research_query(finding: dict) -> str:
    """Build the v1.0 retrieval query for a modernize finding.

    For `moved` symbols the old name has ZERO v1.0 mentions by definition of
    the status, so including it only adds vector noise that drags retrieval
    toward generically agent-ish pages (measured: mig-006/007 cited sql-agent
    instead of the curated evidence page). Instead ask for the replacement the
    way the v1.0 docs actually spell it — as an import statement derived from
    the map's dotted path. For deprecated/renamed the old name still appears
    in (or near) the v1.0 teaching passage, so symbol + replacement works.
    """
    repl = finding.get("replacement") or ""
    if finding["status"] == "moved" and re.fullmatch(r"[\w.]+\.\w+", repl):
        module, _, name = repl.rpartition(".")
        return f"from {module} import {name}"
    return f"{finding['symbol']} {repl}".strip()


def _route_after_research(state: MigrateState) -> str:
    # Flag-only input: the caveats are already set and the code must not be
    # rewritten, so there is nothing for the LLM to do.
    if any(f["action"] == "modernize" for f in state.get("findings", [])):
        return "rewrite"
    return END


_REWRITE_SYSTEM = (
    "You are the rewrite engine of a LangGraph v0.x -> v1.0 migration tool. "
    "You get a legacy Python file, verified FINDINGS (deprecated symbols with "
    "their v1.0 replacements), and numbered documentation passages [n] from "
    "the pinned LangGraph docs. Rewrite the WHOLE file, applying ONLY the "
    "replacements the findings require, plus whatever import changes those "
    "replacements need. Ground every replacement in the passages; if the "
    "passages do not show how the replacement is used, leave that code "
    "unchanged instead of guessing. Everything else must stay exactly as "
    "written: same names, same order, same formatting, no added comments, no "
    "style improvements. The replaced legacy symbols must not appear anywhere "
    "in your output — not in code, not in comments, not in strings. Symbols "
    "listed under KEEP-AS-IS are unevidenced; keep them exactly as they are. "
    'Return ONLY a JSON object: {"code": "<the full rewritten file>", '
    '"changes": [{"description": "<one specific change>", '
    '"citations": [<passage numbers that evidence it>]}]}. '
    "Every change entry must carry at least one passage number."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _build_rewrite_prompt(state: MigrateState) -> str:
    by_symbol = {e["symbol"]: e for e in state.get("evidence", [])}
    replace_lines: list[str] = []
    keep_lines: list[str] = []
    passages: list[str] = []
    for f in state.get("findings", []):
        ev = by_symbol.get(f["symbol"], {})
        if f["action"] == "modernize":
            replace_lines.append(
                f"- {f['symbol']} ({f['status']}) -> {f['replacement']}. "
                f"Verdict: {ev.get('verdict', 'n/a')}"
            )
            if ev.get("passages"):
                passages.append(ev["passages"])
        else:
            keep_lines.append(
                f"- {f['symbol']}: unevidenced in the pinned v1.0 corpus — "
                "DO NOT change it in any way."
            )
    parts = [
        "LEGACY FILE:\n```python\n" + state["code"] + "\n```",
        "FINDINGS — REPLACE:\n" + "\n".join(replace_lines),
    ]
    if keep_lines:
        parts.append("FINDINGS — KEEP-AS-IS:\n" + "\n".join(keep_lines))
    parts.append("DOCUMENTATION PASSAGES:\n\n" + "\n\n---\n\n".join(passages))
    if state.get("verify_feedback"):
        parts.append(
            "YOUR PREVIOUS ATTEMPT FAILED VERIFICATION: "
            f"{state['verify_feedback']}. Produce a corrected full file."
        )
    return "\n\n".join(parts)


def _rewrite_node(state: MigrateState) -> dict:
    _emit_node("rewrite", "active")
    attempts = state.get("attempts", 0) + 1
    try:
        text = _chat(
            [
                {"role": "system", "content": _REWRITE_SYSTEM},
                {"role": "user", "content": _build_rewrite_prompt(state)},
            ],
            name="migrate.rewrite",
            response_format={"type": "json_object"},
        )
        match = _JSON_RE.search(text or "")
        parsed = json.loads(match.group(0)) if match else None
    except Exception:  # noqa: BLE001 - a failed call becomes a failed attempt, not a crash
        parsed = None
    if not isinstance(parsed, dict):
        # Verify will fail this attempt and drive the (single) retry.
        return {"rewritten": None, "changes": [], "attempts": attempts}
    raw = str(parsed.get("code", ""))
    # Only de-fence when a fence is actually there: _strip_fences rebuilds the
    # string from splitlines() and would silently eat a trailing newline.
    code = _strip_fences(raw) if "```" in raw else raw
    if raw.endswith("\n") and not code.endswith("\n"):
        code += "\n"
    changes: list[dict] = []
    for c in parsed.get("changes", []):
        if not (isinstance(c, dict) and c.get("description")):
            continue
        ns = [
            int(n)
            for n in c.get("citations", [])
            if isinstance(n, int) or (isinstance(n, str) and n.isdigit())
        ]
        changes.append({"description": str(c["description"]), "citations": ns})
    return {"rewritten": code, "changes": changes, "attempts": attempts}


def _verify_node(state: MigrateState) -> dict:
    _emit_node("verify", "active")
    problems = verify_rewrite(state.get("rewritten"), state.get("findings", []))
    if not problems:
        return {"verify_ok": True, "verify_feedback": None}
    if state.get("attempts", 0) < MAX_REWRITE_ATTEMPTS:
        return {"verify_ok": False, "verify_feedback": "; ".join(problems)}
    # Out of attempts: give up gracefully with the best available result.
    caveats = list(state.get("caveats", []))
    rewritten = state.get("rewritten")
    if rewritten and _parses(rewritten):
        # Parseable but imperfect (e.g. a symbol survived): worth returning,
        # loudly. Dropping it would hide work the user can still review.
        caveats.append(
            "Verification failed after a retry: " + "; ".join(problems) + ". "
            "The rewrite is returned anyway — review it before use."
        )
    else:
        rewritten = None  # falls back to the original code downstream
        caveats.append(
            "The migration could not be completed safely ("
            + "; ".join(problems)
            + "); the original code is returned unchanged."
        )
    return {
        "verify_ok": False,
        "verify_feedback": None,
        "rewritten": rewritten,
        "changes": state.get("changes", []) if rewritten else [],
        "caveats": caveats,
    }


def _route_after_verify(state: MigrateState) -> str:
    if state.get("verify_feedback"):
        return "research"  # bounded: attempts check already gated this
    return END


@lru_cache
def _graph():
    g = StateGraph(MigrateState)
    g.add_node("detect", _detect_node)
    g.add_node("research", _research_node)
    g.add_node("rewrite", _rewrite_node)
    g.add_node("verify", _verify_node)
    g.add_edge(START, "detect")
    g.add_conditional_edges("detect", _route_after_detect, {"research": "research", END: END})
    g.add_conditional_edges("research", _route_after_research, {"rewrite": "rewrite", END: END})
    g.add_edge("rewrite", "verify")
    g.add_conditional_edges("verify", _route_after_verify, {"research": "research", END: END})
    return g.compile()  # stateless pipeline: no checkpointer on purpose


# --- drivers -----------------------------------------------------------------


def _build_result(
    original: str, state: dict, sink: list, debug: list
) -> MigrateResult:
    if state.get("error"):
        return MigrateResult(
            original=original,
            rewritten=original,
            error=state["error"],
            verified=False,
        )
    findings = state.get("findings", [])
    has_modernize = any(f["action"] == "modernize" for f in findings)
    # None/empty rewritten covers three paths at once: clean passthrough,
    # flag-only input, and the give-up fallback — all return the input
    # BYTE-IDENTICAL (never round-tripped through an LLM).
    rewritten = state.get("rewritten") or original
    by_n = {s["n"]: s for s in sink}
    changes: list[dict] = []
    for c in state.get("changes", []):
        ns = [n for n in c.get("citations", []) if n in by_n]
        slugs = list(
            dict.fromkeys(by_n[n]["slug"] for n in ns if by_n[n].get("slug"))
        )
        changes.append(
            {"description": c["description"], "citations": ns, "citation_slugs": slugs}
        )
    cited_ns = sorted({n for c in changes for n in c["citations"]})
    return MigrateResult(
        original=original,
        rewritten=rewritten,
        changes=changes,
        caveats=list(state.get("caveats", [])),
        diff=make_diff(original, rewritten),
        findings=findings,
        citations=[by_n[n] for n in cited_ns],
        retrieval_traces=list(debug),
        attempts=state.get("attempts", 0),
        verified=bool(state.get("verify_ok")) if has_modernize else True,
    )


def _summary_text(res: MigrateResult) -> str:
    """Deterministic human-readable summary (the stream's `token` payload)."""
    if not res.findings:
        return (
            "No deprecated or unevidenced LangGraph APIs detected — the code "
            "is already v1.0-idiomatic and is returned unchanged."
        )
    lines = [
        f"Migration finished: {len(res.changes)} change(s), "
        f"{len(res.caveats)} caveat(s)."
    ]
    for c in res.changes:
        marks = "".join(f"[{n}]" for n in c["citations"])
        lines.append(f"- {c['description']} {marks}".rstrip())
    for cv in res.caveats:
        lines.append(f"- Caveat: {cv}")
    return "\n".join(lines)


def run_migrate(code: str) -> MigrateResult:
    """Run the migration graph end-to-end (non-streaming)."""
    sink = begin_citation_capture()
    debug = begin_debug_capture()
    state = _graph().invoke({"code": code, "attempts": 0})
    return _build_result(code, dict(state), sink, debug)


async def astream_migrate(code: str):
    """Stream the migration run for a live UI.

    Same event vocabulary as astream_agent — node | retrieval | token |
    citations | done — plus one `result` event carrying
    {original, rewritten, changes, caveats, diff}. Node "active" events and
    per-call retrieval traces travel through LangGraph's custom stream
    (emitted inside the nodes); node "done" events come from updates mode.
    Node ids follow the S1.3 <AgentGraph> conventions: real nodes by name,
    a synthetic __end__ terminal marker before `done`.
    """
    # Context-local sinks MUST be set in the task that iterates the graph
    # (same hazard as astream_agent).
    sink = begin_citation_capture()
    debug = begin_debug_capture()
    final: dict = {"code": code, "attempts": 0}
    async for mode, payload in _graph().astream(
        {"code": code, "attempts": 0}, stream_mode=["updates", "custom"]
    ):
        if mode == "custom":
            yield payload  # node-active / retrieval events, emitted in-node
        elif mode == "updates":
            for node_name, delta in payload.items():
                if isinstance(delta, dict):
                    final.update(delta)
                yield {"type": "node", "v": {"name": node_name, "status": "done"}}
    res = _build_result(code, final, sink, debug)
    if res.error:
        yield {"type": "token", "v": res.error}
        yield {"type": "node", "v": {"name": "__end__", "status": "done"}}
        yield {"type": "done"}
        return
    yield {"type": "token", "v": _summary_text(res)}
    if res.citations:
        yield {"type": "citations", "v": res.citations}
    yield {
        "type": "result",
        "v": {
            "original": res.original,
            "rewritten": res.rewritten,
            "changes": res.changes,
            "caveats": res.caveats,
            "diff": res.diff,
        },
    }
    yield {"type": "node", "v": {"name": "__end__", "status": "done"}}
    yield {"type": "done"}
