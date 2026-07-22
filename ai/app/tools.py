"""Tools the agent can call (Phase 2, extended in Phase 3 S2.2).

Four tools with distinct purposes so the agent has a real tool-selection
decision to make:
  - rag_search       : the Phase 1 retrieval pipeline, wrapped as a tool
  - calculator       : safe arithmetic (a non-RAG capability)
  - list_doc_topics  : what the corpus actually covers (meta questions)
  - check_api_status : does a LangGraph symbol still exist in v1.0, and what
                       replaced it (migration/deprecation questions)

Each tool has a typed signature + docstring; LangChain turns those into the JSON
schema the model sees when choosing a tool.
"""

from __future__ import annotations

import ast
import contextvars
import json
import math
import operator
from dataclasses import asdict, replace
from pathlib import Path

from langchain_core.tools import tool

from app.pipeline import HYBRID_RERANK, retrieve_with_trace

_DATA = Path(__file__).resolve().parents[1] / "data"
_MANIFEST = _DATA / "manifest.json"
_DEPRECATIONS = _DATA / "deprecations.json"

# Per-turn citation capture. The agent may call rag_search several times in one
# turn; we number passages GLOBALLY across those calls (so the model sees [1..k],
# then [k+1..]) and stash the structured source for each number here. The final
# answer's inline [n] then map 1:1 onto these sources — giving the agent path the
# same clickable citations as the RAG path. Set per turn via begin_citation_capture();
# when unset (e.g. the MCP server or a direct call) rag_search numbers from 1 and
# captures nothing, preserving standalone behaviour.
_citation_sink: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "citation_sink", default=None
)


def begin_citation_capture() -> list:
    """Start a fresh citation sink for the current turn; returns the list to read later."""
    sink: list = []
    _citation_sink.set(sink)
    return sink


# Per-turn retrieval-trace capture — the _citation_sink pattern again, for a
# different payload. rag_search's return STRING is a frozen contract (it is
# what the agent prompt was tuned on, what MCP clients receive, and it already
# costs ~5 passages of agent context — 20 scored pool entries would bloat it
# for zero answer quality). So the structured trace leaves out-of-band through
# this sink instead of in-band through the return value. Set per turn via
# begin_debug_capture(); when unset (MCP server, direct calls, eval) nothing
# is captured and behaviour is byte-identical.
_debug_sink: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "debug_sink", default=None
)


def begin_debug_capture() -> list:
    """Start a fresh debug (retrieval-trace) sink for the current turn; returns the list."""
    sink: list = []
    _debug_sink.set(sink)
    return sink


@tool
def rag_search(query: str, docs_version: str = "1.0") -> str:
    """Search the LangGraph documentation for an answer.

    Use this for any question about LangGraph concepts, APIs, or how-to. Returns
    numbered passages with their source URLs so the answer can cite them as [n].
    docs_version picks the corpus: "1.0" (default - the current docs; almost
    always what you want) or "0.2" (legacy docs - only to understand what old
    v0.x code meant, never to answer how things work today).
    """
    docs_version = (docs_version or "1.0").strip().lstrip("vV")
    if docs_version not in ("1.0", "0.2"):
        # Refuse rather than silently clamp: answering a "0.3" request from the
        # 1.0 corpus would imply a corpus we don't have.
        return (
            f"Unknown docs_version {docs_version!r}: "
            'the pinned corpora are "1.0" (current) and "0.2" (legacy).'
        )
    # replace() keeps the whole HYBRID_RERANK strategy and swaps only the corpus
    # filter; for "1.0" the config is equal to HYBRID_RERANK itself, so the
    # default path retrieves from an identical candidate set as before.
    results, trace = retrieve_with_trace(query, replace(HYBRID_RERANK, version=docs_version))
    debug = _debug_sink.get()
    if not results:
        if debug is not None:
            debug.append({"tool_call_query": query, "citation_ns": [], **asdict(trace)})
        return "No relevant passages found in the LangGraph documentation."
    sink = _citation_sink.get()
    start = len(sink) if sink is not None else 0  # continue numbering across calls
    blocks = []
    citation_ns: list[int] = []
    for i, r in enumerate(results):
        n = start + i + 1
        citation_ns.append(n)
        m = r.metadata or {}
        if sink is not None:
            sink.append(
                {
                    "n": n,
                    "chunk_id": r.chunk_id,
                    "page_title": m.get("page_title"),
                    "heading": m.get("heading"),
                    "source_url": m.get("source_url"),
                }
            )
        blocks.append(
            f"[{n}] {m.get('page_title', '?')} — {m.get('heading', '')}\n"
            f"URL: {m.get('source_url', '')}\n{r.content}"
        )
    if debug is not None:
        # citation_ns lets the UI badge pool rows that made it into the answer's
        # [n] markers; the rest of the entry is the serialized RetrievalTrace.
        debug.append({"tool_call_query": query, "citation_ns": citation_ns, **asdict(trace)})
    return "\n\n---\n\n".join(blocks)


# Safe arithmetic: evaluate a tiny AST whitelist, never Python's eval().
#
# Exponentiation needs a magnitude guard on top of the whitelist: Python ints
# are arbitrary-precision, so "9**9**9**9" is *safe* but not *cheap* — a single
# intermediate like 9**387420489 burns CPU for as long as we let it, which is a
# denial-of-service surface on a public endpoint (the agent calls this tool on
# user input). The guard estimates the result's bit length as
# |exp| * log2(|base|) BEFORE computing the power — O(1), so hostile input is
# rejected in microseconds — and caps it at ~1000 bits (~300 decimal digits).
# That is far beyond any arithmetic a user genuinely asks ("2**16", "1.5**3",
# even 2**1000 passes) and also keeps the returned number small: the result
# string goes straight back into the agent's context.
_MAX_POW_BITS = 1000


class _PowTooLargeError(ValueError):
    """Raised when an exponentiation would exceed _MAX_POW_BITS."""


def _checked_pow(base, exp):
    if abs(base) > 1 and abs(exp) * math.log2(abs(base)) > _MAX_POW_BITS:
        raise _PowTooLargeError
    return operator.pow(base, exp)


_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: _checked_pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression (e.g. '2 * (3 + 4) ** 2').

    Use this for math; it does not know anything about LangGraph.
    """
    try:
        return str(_eval_node(ast.parse(expression, mode="eval").body))
    except _PowTooLargeError:
        # Same "Could not evaluate" shape as every other failure, plus the
        # reason, so the agent can relay WHY instead of just shrugging.
        return (
            f"Could not evaluate expression: {expression!r} "
            "(the result of an exponentiation would be too large)"
        )
    except Exception:  # noqa: BLE001 - return a clean error the agent can relay
        return f"Could not evaluate expression: {expression!r}"


@tool
def list_doc_topics() -> str:
    """List the LangGraph documentation pages available in the corpus.

    Use this for meta questions like "what topics can you answer about?".
    """
    # Deliberately v1.0-only: the product answers questions about v1.0, so the
    # advertised topic list is the v1.0 manifest. The legacy v0.2 corpus is
    # reference material for migration checks, not answerable coverage — it
    # gets one closing sentence, not a topic listing, so the agent never
    # advertises legacy pages as things it answers questions from.
    try:
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        titles = "; ".join(f["title"] for f in manifest["files"])
        return (
            f"{titles}. (These are the pinned LangGraph v1.0 docs; a legacy v0.2 "
            "corpus also exists purely as migration reference — see check_api_status.)"
        )
    except Exception:  # noqa: BLE001
        return "Topic list is unavailable."


# --- check_api_status (Phase 3 S2.2) ----------------------------------------
#
# Two sources, combined on purpose:
#   1. data/deprecations.json — a CURATED verdict per symbol, every entry
#      verified by hand against the two pinned corpora on disk. Counts alone
#      cannot distinguish *removed* from *renamed*, and they can never name
#      the replacement — only curation can.
#   2. live per-version occurrence counts from the chunks table (the
#      chunks_docs_version_idx btree makes the GROUP BY cheap). A curated
#      table alone is an ungrounded lookup — the counts tie the verdict to
#      the corpus the user can actually read, and they still say something
#      useful for symbols the map has never heard of.
# Together the answer is authoritative (curated) AND evidenced (counted).


def _normalize_symbol(symbol: str) -> str:
    """Canonicalise user/model spellings: `set_entry_point()` -> set_entry_point."""
    s = (symbol or "").strip().strip("`'\"")
    if s.endswith("()"):
        s = s[:-2]
    # "graph.update_state" / "langgraph.prebuilt.ToolNode" -> last segment
    return s.rsplit(".", 1)[-1].strip()


def _deprecation_entry(symbol: str) -> dict | None:
    doc = json.loads(_DEPRECATIONS.read_text(encoding="utf-8"))
    by_symbol = {e["symbol"].lower(): e for e in doc["entries"]}
    return by_symbol.get(symbol.lower())


def _symbol_counts(symbol: str) -> dict[str, int] | None:
    """Chunks mentioning `symbol`, grouped by docs_version; None if the DB is down."""
    # Escape LIKE wildcards so set_entry_point matches literally, not as a pattern.
    escaped = symbol.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
    try:
        from app.db import get_connection

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT docs_version, count(*) FROM chunks "
                "WHERE content ILIKE %s GROUP BY docs_version",
                (f"%{escaped}%",),
            )
            rows = cur.fetchall()
    except Exception:  # noqa: BLE001 - evidence is best-effort, verdict still stands
        return None
    counts = {"1.0": 0, "0.2": 0}
    for version, n in rows:
        counts[str(version)] = int(n)
    return counts


_STATUS_PHRASES = {
    "deprecated": "still works in v1.0 but is deprecated — prefer {replacement}",
    "renamed": "renamed in v1.0 — use {replacement}",
    "moved": "moved in v1.0 — use {replacement}",
    "unchanged": "unchanged between v0.2 and v1.0 — no migration needed",
    "unevidenced": (
        "taught by the v0.2 docs but absent from the pinned v1.0 corpus; "
        "the corpora cannot confirm whether it was removed"
    ),
}


def render_api_status(symbol: str, entry: dict | None, counts: dict[str, int] | None) -> str:
    """Pure renderer (unit-testable without DB): curated verdict + count evidence."""
    if counts is None:
        evidence = "corpus mention counts unavailable (database unreachable)"
    else:
        evidence = (
            f"{counts.get('0.2', 0)} chunk(s) of the v0.2 docs and "
            f"{counts.get('1.0', 0)} chunk(s) of the v1.0 docs mention it"
        )
    if entry is None:
        # No curated verdict — report ONLY the counts, and say what they
        # cannot tell. Implying removed/renamed here would be a guess.
        return (
            f"`{symbol}`: not in the curated deprecations map, so no verified "
            f"verdict. Corpus evidence: {evidence}. Counts alone cannot say "
            "whether a symbol was removed or renamed — treat this as unverified."
        )
    phrase = _STATUS_PHRASES[entry["status"]].format(replacement=entry["replacement"])
    parts = [f"`{entry['symbol']}`: {phrase}."]
    if entry["status"] == "unevidenced" and entry["replacement"]:
        parts.append(f"The v1.0 docs teach {entry['replacement']} instead.")
    parts.append(f"Evidence: {evidence}.")
    if entry.get("note"):
        parts.append(entry["note"])
    parts.append(f"[{entry['doc_slug']}]")
    return " ".join(parts)


@tool
def check_api_status(symbol: str) -> str:
    """Check whether a LangGraph API symbol still exists in v1.0 and what replaced it.

    Use this for migration/deprecation questions — "does set_entry_point still
    work?", "what replaced config_schema?", "is StateGraph still current?".
    Returns a corpus-verified verdict (deprecated / renamed / moved / unchanged)
    with the replacement to use, plus how often the symbol appears in the pinned
    v0.2 vs v1.0 doc corpora as evidence.
    """
    name = _normalize_symbol(symbol)
    if not name:
        return "Please provide a symbol name to check."
    return render_api_status(name, _deprecation_entry(name), _symbol_counts(name))


TOOLS = [rag_search, calculator, list_doc_topics, check_api_status]
