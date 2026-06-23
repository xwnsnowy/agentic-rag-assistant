"""MCP server (Model Context Protocol) exposing the Phase 2 tools.

Why this exists: the agent in `app.agent` already calls `rag_search` / `calculator`
/ `list_doc_topics` internally. MCP lets the *same* tools be consumed by any MCP
client (Claude Desktop, IDEs, other agents) over a standard protocol — one tool
implementation, two front doors (internal LangGraph agent + external MCP).

We deliberately reuse the LangChain tools from `app.tools` rather than reimplement
them, so the MCP surface can never drift from what the agent uses. Each handler
just forwards to the underlying tool via `.invoke(...)`.

Run (stdio transport — what Claude Desktop / most clients expect):
    cd ai && python -m app.mcp_server

Register with an MCP client (e.g. Claude Desktop config):
    "langgraph-docs-rag": {
        "command": "python",
        "args": ["-m", "app.mcp_server"],
        "cwd": "<abs path>/ai"
    }
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

# Importing app.tools also triggers app.__init__ (truststore TLS injection).
from app.tools import calculator as _calculator
from app.tools import list_doc_topics as _list_doc_topics
from app.tools import rag_search as _rag_search

mcp = FastMCP("langgraph-docs-rag")


@mcp.tool()
def rag_search(query: str) -> str:
    """Search the LangGraph v1.0 documentation for an answer.

    Returns numbered passages with their source URLs so the answer can cite them
    as [n]. Use for any LangGraph concept / API / how-to question.
    """
    return _rag_search.invoke({"query": query})


@mcp.tool()
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression (e.g. '2 * (3 + 4) ** 2').

    Safe AST evaluation, no Python eval(). Knows nothing about LangGraph.
    """
    return _calculator.invoke({"expression": expression})


@mcp.tool()
def list_doc_topics() -> str:
    """List the LangGraph documentation pages available in the corpus.

    Use for meta questions like "what topics can you answer about?".
    """
    return _list_doc_topics.invoke({})


def main() -> None:
    # stdio transport: the client launches this process and speaks MCP over
    # stdin/stdout. No port, no network — works the same locally and when a
    # client spawns it.
    mcp.run()


if __name__ == "__main__":
    main()
