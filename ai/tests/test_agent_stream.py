"""Unit tests for the S1.2 SSE event stream (app/agent.py::astream_agent).

Pure: `_graph` is monkeypatched to a fake whose astream() replays a scripted
sequence of (mode, payload) tuples — no LLM, no DB, no network. The script can
also contain callables, which run in the SAME task/context that iterates the
graph; that is how the tests simulate rag_search depositing into the
context-local citation/debug sinks mid-stream (exactly what ToolNode does live).

What must hold:
  - the pre-S1.2 event contract (tools | token | citations | done) is
    byte-identical — the deployed frontend depends on it;
  - `node` "active" fires once per node per turn (dedup), "done" per updates
    event, and a synthetic __end__ lands just before `done`;
  - each captured retrieval trace becomes its OWN `retrieval` event, drained
    right after the tools node completes.
"""

import asyncio

from langchain_core.messages import AIMessageChunk, ToolMessage

import app.agent as agent_mod
import app.tools as tools_mod
from app.agent import astream_agent


class _FakeGraph:
    def __init__(self, script):
        self.script = script
        self.stream_mode_seen = None

    async def astream(self, _input, config=None, stream_mode=None):
        self.stream_mode_seen = stream_mode
        for item in self.script:
            if callable(item):
                item()  # simulate a tool writing to the context-local sinks
            else:
                yield item


def _run(monkeypatch, script, question="What is a StateGraph?"):
    fake = _FakeGraph(script)
    monkeypatch.setattr(agent_mod, "_graph", lambda: fake)
    monkeypatch.setattr(agent_mod, "_tracing_callbacks", list)

    async def _collect():
        return [ev async for ev in astream_agent(question)]

    return asyncio.run(_collect()), fake


def _ai(content="", tool_call_chunks=None):
    return AIMessageChunk(content=content, tool_call_chunks=tool_call_chunks or [])


def _rag_tool_chunk():
    return {"name": "rag_search", "args": "", "id": "call_1", "index": 0,
            "type": "tool_call_chunk"}


_TRACE_A = {"tool_call_query": "state graph", "citation_ns": [1],
            "pool": [{"chunk_id": 10}], "final_ids": [10],
            "timings_ms": {"retrieve": 12.5, "rerank": None}}
_TRACE_B = {"tool_call_query": "reducers", "citation_ns": [2],
            "pool": [{"chunk_id": 11}], "final_ids": [11],
            "timings_ms": {"retrieve": 9.0, "rerank": 3.0}}


def _deposit(trace, citation_n):
    """What rag_search does inside the tools node: write to both sinks."""

    def _do():
        tools_mod._debug_sink.get().append(dict(trace))
        tools_mod._citation_sink.get().append(
            {"n": citation_n, "chunk_id": trace["final_ids"][0],
             "page_title": "P", "heading": "H", "source_url": "u"}
        )

    return _do


# One full ReAct turn: agent plans a rag_search call, tools runs it, agent answers.
def _full_turn_script():
    return [
        ("messages", (_ai(tool_call_chunks=[_rag_tool_chunk()]), {"langgraph_node": "agent"})),
        ("updates", {"agent": {"messages": []}}),
        _deposit(_TRACE_A, 1),
        ("messages", (ToolMessage(content="[1] ...", tool_call_id="call_1"),
                      {"langgraph_node": "tools"})),
        ("updates", {"tools": {"messages": []}}),
        ("messages", (_ai(content="A StateGraph"), {"langgraph_node": "agent"})),
        ("messages", (_ai(content=" is a graph [1]."), {"langgraph_node": "agent"})),
        ("updates", {"agent": {"messages": []}}),
    ]


def test_full_turn_event_sequence(monkeypatch):
    events, fake = _run(monkeypatch, _full_turn_script())

    assert fake.stream_mode_seen == ["messages", "updates"]
    assert [(e["type"], e["v"].get("name") if e["type"] == "node" else None) for e in events] == [
        ("node", "agent"),        # first messages chunk from agent -> active
        ("tools", None),
        ("node", "agent"),        # updates: agent round 1 done
        ("node", "tools"),        # ToolMessage arrives -> tools active
        ("node", "tools"),        # updates: tools done
        ("retrieval", None),      # drained right after tools completes
        ("token", None),
        ("token", None),
        ("node", "agent"),        # updates: agent round 2 done
        ("citations", None),
        ("node", "__end__"),      # synthetic terminal marker...
        ("done", None),           # ...immediately before done
    ]
    statuses = [e["v"]["status"] for e in events if e["type"] == "node"]
    assert statuses == ["active", "done", "active", "done", "done", "done"]


def test_legacy_contract_payloads_are_unchanged(monkeypatch):
    """Strip the new node/retrieval events: what remains must be exactly the
    pre-S1.2 stream the deployed frontend was built against."""
    events, _ = _run(monkeypatch, _full_turn_script())

    legacy = [e for e in events if e["type"] in ("tools", "token", "citations", "done")]
    assert legacy[0] == {"type": "tools", "v": ["rag_search"]}
    assert legacy[1] == {"type": "token", "v": "A StateGraph"}
    assert legacy[2] == {"type": "token", "v": " is a graph [1]."}
    assert legacy[3]["type"] == "citations"
    assert [c["n"] for c in legacy[3]["v"]] == [1]
    assert legacy[4]["type"] == "done"
    assert legacy[4]["tools_used"] == ["rag_search"]
    assert legacy[4]["thread_id"].startswith("ephemeral-")


def test_node_active_fires_once_per_node(monkeypatch):
    script = [
        ("messages", (_ai(content="a"), {"langgraph_node": "agent"})),
        ("messages", (_ai(content="b"), {"langgraph_node": "agent"})),
        ("messages", (_ai(content="c"), {"langgraph_node": "agent"})),
    ]
    events, _ = _run(monkeypatch, script)

    actives = [e for e in events if e["type"] == "node" and e["v"]["status"] == "active"]
    assert len(actives) == 1
    assert actives[0]["v"]["name"] == "agent"


def test_multiple_traces_become_separate_retrieval_events_in_order(monkeypatch):
    script = [
        _deposit(_TRACE_A, 1),
        _deposit(_TRACE_B, 2),
        ("updates", {"tools": {"messages": []}}),
    ]
    events, _ = _run(monkeypatch, script)

    retrievals = [e for e in events if e["type"] == "retrieval"]
    assert len(retrievals) == 2  # never merged: one event per rag_search call
    assert retrievals[0]["v"]["tool_call_query"] == "state graph"
    assert retrievals[1]["v"]["tool_call_query"] == "reducers"
    assert retrievals[0]["v"]["pool"] == [{"chunk_id": 10}]


def test_non_tools_updates_do_not_emit_retrieval_even_with_pending_traces(monkeypatch):
    script = [
        _deposit(_TRACE_A, 1),
        ("updates", {"agent": {"messages": []}}),
    ]
    events, _ = _run(monkeypatch, script)

    assert [e["type"] for e in events if e["type"] == "retrieval"] == []
    # The agent-done node event still fired.
    assert {"type": "node", "v": {"name": "agent", "status": "done"}} in events


def test_no_traces_means_no_retrieval_events(monkeypatch):
    script = [
        ("messages", (_ai(content="hi"), {"langgraph_node": "agent"})),
        ("updates", {"agent": {"messages": []}}),
        ("updates", {"tools": {"messages": []}}),  # tools ran, captured nothing
    ]
    events, _ = _run(monkeypatch, script)

    assert all(e["type"] != "retrieval" for e in events)
    assert events[-1]["type"] == "done"
    assert events[-2] == {"type": "node", "v": {"name": "__end__", "status": "done"}}


def test_guardrail_early_returns_keep_their_exact_stream(monkeypatch):
    # These paths never touch the graph — no node/retrieval events may appear.
    async def _collect(q):
        return [ev async for ev in astream_agent(q)]

    events = asyncio.run(_collect("   "))
    assert [e["type"] for e in events] == ["token", "done"]
    assert events[0]["v"] == "Please ask a question."

    events = asyncio.run(_collect("x" * 3000))
    assert [e["type"] for e in events] == ["token", "done"]
    assert events[0]["v"] == "Your question is too long; please shorten it."
