"""Tools the agent can call (Phase 2).

Three tools with distinct purposes so the agent has a real tool-selection
decision to make:
  - rag_search       : the Phase 1 retrieval pipeline, wrapped as a tool
  - calculator       : safe arithmetic (a non-RAG capability)
  - list_doc_topics  : what the corpus actually covers (meta questions)

Each tool has a typed signature + docstring; LangChain turns those into the JSON
schema the model sees when choosing a tool.
"""

from __future__ import annotations

import ast
import json
import operator
from pathlib import Path

from langchain_core.tools import tool

from app.pipeline import HYBRID_RERANK, retrieve

_MANIFEST = Path(__file__).resolve().parents[1] / "data" / "manifest.json"


@tool
def rag_search(query: str) -> str:
    """Search the LangGraph v1.0 documentation for an answer.

    Use this for any question about LangGraph concepts, APIs, or how-to. Returns
    numbered passages with their source URLs so the answer can cite them as [n].
    """
    results = retrieve(query, HYBRID_RERANK)
    if not results:
        return "No relevant passages found in the LangGraph documentation."
    blocks = []
    for i, r in enumerate(results, 1):
        m = r.metadata or {}
        blocks.append(
            f"[{i}] {m.get('page_title', '?')} — {m.get('heading', '')}\n"
            f"URL: {m.get('source_url', '')}\n{r.content}"
        )
    return "\n\n---\n\n".join(blocks)


# Safe arithmetic: evaluate a tiny AST whitelist, never Python's eval().
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
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
    except Exception:  # noqa: BLE001 - return a clean error the agent can relay
        return f"Could not evaluate expression: {expression!r}"


@tool
def list_doc_topics() -> str:
    """List the LangGraph documentation pages available in the corpus.

    Use this for meta questions like "what topics can you answer about?".
    """
    try:
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        return "; ".join(f["title"] for f in manifest["files"])
    except Exception:  # noqa: BLE001
        return "Topic list is unavailable."


TOOLS = [rag_search, calculator, list_doc_topics]
