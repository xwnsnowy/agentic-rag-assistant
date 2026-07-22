"""Pure tests for the migration workbench (app/migrate.py, S2.4).

No LLM, no DB, no network: detect and verify are the deterministic halves of
the pipeline and must be fully trustable in CI — they are what closed the
baseline's blindness gap, so they get the direct coverage. The graph-level
tests monkeypatch the three seams (_chat, _rag_search, _check_api_status) and
run the real compiled LangGraph.
"""

import ast
import asyncio
import json

import app.migrate as migrate_mod
import app.tools as tools_mod
from app.migrate import (
    MAX_CODE_CHARS,
    collect_symbols,
    detect_findings,
    flag_caveat,
    make_diff,
    run_migrate,
    validate_input,
    verify_rewrite,
)
from eval.migration_harness import load_dataset

# --- validate_input (guardrails) ---------------------------------------------


def test_empty_input_rejected():
    assert validate_input("") is not None
    assert validate_input("   \n  ") is not None


def test_oversized_input_rejected_with_limit_in_message():
    msg = validate_input("x = 1\n" * 2000)  # 12000 chars > 8000
    assert msg is not None
    assert str(MAX_CODE_CHARS) in msg


def test_unparseable_input_rejected_with_line_number():
    msg = validate_input("def broken(:\n    pass\n")
    assert msg is not None
    assert "line 1" in msg


def test_valid_input_passes():
    assert validate_input("x = 1\n") is None


# --- collect_symbols ---------------------------------------------------------


def test_collects_every_spelling_the_map_needs():
    code = (
        "from langgraph.prebuilt import create_react_agent\n"
        "from langgraph.checkpoint.sqlite import SqliteSaver\n"
        "builder.set_entry_point('a')\n"
        "g = StateGraph(State, config_schema=Cfg)\n"
        "graph = builder.compile(interrupt_before=['a'])\n"
        "graph.update_state(config, {})\n"
    )
    syms = collect_symbols(ast.parse(code))
    for expected in (
        "create_react_agent",  # from-import name
        "SqliteSaver",  # from-import name / bare name
        "set_entry_point",  # attribute call
        "config_schema",  # keyword argument
        "interrupt_before",  # keyword argument
        "update_state",  # attribute call
    ):
        assert expected in syms, expected


def test_exact_name_matching_interrupt_is_not_interrupt_before():
    syms = collect_symbols(ast.parse("answer = interrupt({'q': 1})\n"))
    assert "interrupt" in syms
    assert "interrupt_before" not in syms


# --- detect_findings against the real dataset --------------------------------
# The dataset's `symbols` name deprecations.json entries and its kinds agree
# with their statuses (enforced by test_migration_dataset.py). So detect must
# find exactly the item's symbols for modernize/flag items, and nothing
# actionable for clean items — this ties the detector to the same map.


def test_detect_finds_each_seeded_symbol_and_only_those():
    for item in load_dataset():
        found = {f["symbol"] for f in detect_findings(item["legacy_code"])}
        if item["kind"] == "clean":
            assert found == set(), item["id"]
        else:
            assert found == set(item["symbols"]), item["id"]


def test_detect_actions_match_item_kinds():
    action_for_kind = {"modernize": {"modernize"}, "flag": {"flag"}}
    for item in load_dataset():
        if item["kind"] == "clean":
            continue
        actions = {f["action"] for f in detect_findings(item["legacy_code"])}
        assert actions == action_for_kind[item["kind"]], item["id"]


def test_detect_reports_source_order_and_line_numbers():
    code = (
        "builder = StateGraph(State, config_schema=Cfg)\n"
        "builder.set_entry_point('a')\n"
    )
    findings = detect_findings(code)
    assert [f["symbol"] for f in findings] == ["config_schema", "set_entry_point"]
    assert [f["line"] for f in findings] == [1, 2]


def test_detect_ignores_clean_code_entirely():
    assert detect_findings("from langgraph.graph import StateGraph, START\n") == []


# --- flag caveats ------------------------------------------------------------


def test_flag_caveat_names_the_symbol_and_cites_the_doc_slug():
    findings = detect_findings("graph.update_state(config, {})\n")
    caveat = flag_caveat(findings[0])
    assert "update_state" in caveat
    assert "[persistence]" in caveat


def test_flag_caveat_mentions_taught_replacement_when_the_map_has_one():
    findings = detect_findings("g = b.compile(interrupt_before=['a'])\n")
    caveat = flag_caveat(findings[0])
    assert "interrupt_before" in caveat
    assert "interrupt()" in caveat  # the map's replacement, offered as guidance


# --- research query construction --------------------------------------------


def test_research_query_spells_moved_replacements_as_imports():
    # A moved symbol has zero v1.0 mentions, so querying by the old name is
    # noise; the query must be how the v1.0 docs spell the replacement.
    f = {"symbol": "create_react_agent", "status": "moved",
         "replacement": "langchain.agents.create_agent"}
    assert migrate_mod._research_query(f) == "from langchain.agents import create_agent"


def test_research_query_keeps_symbol_for_deprecated_and_renamed():
    f = {"symbol": "set_entry_point", "status": "deprecated",
         "replacement": "add_edge(START, node)"}
    assert migrate_mod._research_query(f) == "set_entry_point add_edge(START, node)"
    f = {"symbol": "config_schema", "status": "renamed", "replacement": "context_schema"}
    assert migrate_mod._research_query(f) == "config_schema context_schema"


# --- verify_rewrite ----------------------------------------------------------


def _mod_finding(symbol: str) -> dict:
    return {"symbol": symbol, "action": "modernize"}


def _flag_finding(symbol: str) -> dict:
    return {"symbol": symbol, "action": "flag"}


def test_verify_passes_a_good_rewrite():
    problems = verify_rewrite(
        'builder.add_edge(START, "a")\n', [_mod_finding("set_entry_point")]
    )
    assert problems == []


def test_verify_catches_surviving_deprecated_symbol():
    problems = verify_rewrite(
        'builder.set_entry_point("a")\n', [_mod_finding("set_entry_point")]
    )
    assert len(problems) == 1
    assert "set_entry_point" in problems[0]


def test_verify_catches_deprecated_symbol_in_a_comment():
    # Substring on purpose: the harness (and a reader) sees comments too.
    problems = verify_rewrite(
        'builder.add_edge(START, "a")  # was set_entry_point\n',
        [_mod_finding("set_entry_point")],
    )
    assert problems and "set_entry_point" in problems[0]


def test_verify_catches_unparseable_rewrite():
    problems = verify_rewrite("def broken(:\n", [_mod_finding("set_entry_point")])
    assert problems and "not valid Python" in problems[0]


def test_verify_catches_removed_unevidenced_symbol():
    # The LLM "helpfully" replaced update_state — that contradicts the map.
    problems = verify_rewrite(
        'graph.invoke(Command(resume="x"), config=config)\n',
        [_flag_finding("update_state")],
    )
    assert problems and "update_state" in problems[0]


def test_verify_accepts_untouched_unevidenced_symbol():
    assert verify_rewrite(
        "graph.update_state(config, {})\n", [_flag_finding("update_state")]
    ) == []


def test_verify_rejects_empty_output():
    assert verify_rewrite("", [_mod_finding("x")]) != []
    assert verify_rewrite(None, [_mod_finding("x")]) != []


# --- make_diff ---------------------------------------------------------------


def test_diff_empty_when_unchanged():
    assert make_diff("x = 1\n", "x = 1\n") == ""


def test_diff_is_well_formed_unified_diff():
    diff = make_diff(
        'builder.set_entry_point("a")\n',
        'builder.add_edge(START, "a")\n',
    )
    lines = diff.splitlines()
    assert lines[0].startswith("--- legacy.py")
    assert lines[1].startswith("+++ migrated.py")
    assert lines[2].startswith("@@")
    assert '-builder.set_entry_point("a")' in lines
    assert '+builder.add_edge(START, "a")' in lines


# --- the full graph (LLM + retrieval monkeypatched) --------------------------

LEGACY = (
    "from langgraph.graph import StateGraph\n"
    "\n"
    "builder = StateGraph(State)\n"
    'builder.add_node("double", double)\n'
    'builder.set_entry_point("double")\n'
    "graph = builder.compile()\n"
)
GOOD = (
    "from langgraph.graph import StateGraph, START\n"
    "\n"
    "builder = StateGraph(State)\n"
    'builder.add_node("double", double)\n'
    'builder.add_edge(START, "double")\n'
    "graph = builder.compile()\n"
)
BAD = LEGACY  # "rewrite" that left the deprecated call in place


def _good_reply() -> str:
    return json.dumps(
        {
            "code": GOOD,
            "changes": [
                {"description": "entry point -> explicit START edge", "citations": [1]}
            ],
        }
    )


def _install_research_stubs(monkeypatch, slug="graph-api"):
    monkeypatch.setattr(
        migrate_mod, "_check_api_status", lambda symbol: f"`{symbol}`: verdict"
    )

    def fake_rag(query, docs_version):
        sink = tools_mod._citation_sink.get()
        debug = tools_mod._debug_sink.get()
        n = (len(sink) if sink is not None else 0) + 1
        if sink is not None:
            sink.append(
                {
                    "n": n,
                    "chunk_id": 100 + n,
                    "page_title": "Graph API",
                    "heading": "Entry point",
                    "source_url": "https://example.com/graph-api",
                    "slug": slug,
                    "docs_version": docs_version,
                }
            )
        if debug is not None:
            debug.append(
                {
                    "tool_call_query": query,
                    "citation_ns": [n],
                    "pool": [{"chunk_id": 100 + n}],
                    "final_ids": [100 + n],
                    "timings_ms": {"retrieve": 1.0, "rerank": None},
                }
            )
        return f"[{n}] Graph API — Entry point\nURL: https://example.com/graph-api\n..."

    monkeypatch.setattr(migrate_mod, "_rag_search", fake_rag)


def _install_chat(monkeypatch, replies: list[str]) -> list:
    calls: list = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return replies[min(len(calls) - 1, len(replies) - 1)]

    monkeypatch.setattr(migrate_mod, "_chat", fake_chat)
    return calls


def test_no_findings_returns_input_byte_identical_without_llm(monkeypatch):
    calls = _install_chat(monkeypatch, ["SHOULD NEVER BE CALLED"])
    # Deliberately gnarly formatting: trailing spaces, blank runs, no final \n.
    clean = "x = 1   \n\n\ny = x + 1"
    res = run_migrate(clean)
    assert res.rewritten == clean  # byte-identical, not normalize-equal
    assert res.error is None
    assert res.diff == ""
    assert res.changes == [] and res.caveats == []
    assert calls == []  # clean code never round-trips through an LLM


def test_guardrails_reject_oversized_and_unparseable_input(monkeypatch):
    _install_chat(monkeypatch, ["SHOULD NEVER BE CALLED"])
    res = run_migrate("def broken(:\n")
    assert res.error is not None and "parse" in res.error.lower()
    assert res.rewritten == "def broken(:\n"  # echoed back, never rewritten

    res = run_migrate("x = 1\n" * 2000)
    assert res.error is not None and str(MAX_CODE_CHARS) in res.error


def test_flag_only_input_unchanged_with_symbol_naming_caveat(monkeypatch):
    _install_research_stubs(monkeypatch)
    calls = _install_chat(monkeypatch, ["SHOULD NEVER BE CALLED"])
    code = 'graph.update_state(config, {"foo": 2})\n'
    res = run_migrate(code)
    assert res.rewritten == code  # byte-identical
    assert res.changes == []
    assert any("update_state" in c for c in res.caveats)
    assert calls == []  # flag path is deterministic — no LLM
    assert res.verified is True
    # The 0.2 corpus (where update_state is taught) was consulted as evidence.
    assert len(res.retrieval_traces) == 1


def test_modernize_happy_path_rewrites_with_slug_mapped_citations(monkeypatch):
    _install_research_stubs(monkeypatch)
    calls = _install_chat(monkeypatch, [_good_reply()])
    res = run_migrate(LEGACY)
    assert len(calls) == 1
    assert res.rewritten == GOOD
    assert res.verified is True and res.attempts == 1
    assert res.changes[0]["citations"] == [1]
    assert res.changes[0]["citation_slugs"] == ["graph-api"]
    assert [c["n"] for c in res.citations] == [1]
    assert res.diff.startswith("--- legacy.py")


def test_verify_failure_triggers_exactly_one_retry_then_succeeds(monkeypatch):
    _install_research_stubs(monkeypatch)
    bad_reply = json.dumps({"code": BAD, "changes": []})
    calls = _install_chat(monkeypatch, [bad_reply, _good_reply()])
    res = run_migrate(LEGACY)
    assert len(calls) == 2  # initial + exactly one retry
    assert res.rewritten == GOOD
    assert res.verified is True and res.attempts == 2
    # The retry prompt carried the verify feedback naming the survivor.
    retry_user = calls[1][1]["content"]
    assert "FAILED VERIFICATION" in retry_user
    assert "set_entry_point" in retry_user


def test_verify_failure_twice_gives_up_gracefully(monkeypatch):
    _install_research_stubs(monkeypatch)
    bad_reply = json.dumps(
        {"code": BAD, "changes": [{"description": "tried", "citations": [1]}]}
    )
    calls = _install_chat(monkeypatch, [bad_reply, bad_reply])
    res = run_migrate(LEGACY)
    assert len(calls) == 2  # bounded: never a third attempt
    assert res.verified is False
    assert res.rewritten == BAD  # parseable best-effort returned, loudly
    assert any("Verification failed" in c for c in res.caveats)


def test_unparseable_rewrites_fall_back_to_the_original(monkeypatch):
    _install_research_stubs(monkeypatch)
    garbage = json.dumps({"code": "def broken(:\n", "changes": []})
    _install_chat(monkeypatch, [garbage, garbage])
    res = run_migrate(LEGACY)
    assert res.verified is False
    assert res.rewritten == LEGACY  # original, byte-identical
    assert res.changes == []  # no changes claimed for code we didn't return
    assert any("original code is returned unchanged" in c for c in res.caveats)


def test_stream_event_sequence_for_a_modernize_run(monkeypatch):
    _install_research_stubs(monkeypatch)
    _install_chat(monkeypatch, [_good_reply()])

    async def _collect():
        return [ev async for ev in migrate_mod.astream_migrate(LEGACY)]

    events = asyncio.run(_collect())
    kinds = [
        (e["type"], e["v"]["name"]) if e["type"] == "node" else e["type"]
        for e in events
    ]
    assert kinds == [
        ("node", "detect"), ("node", "detect"),
        ("node", "research"), "retrieval", ("node", "research"),
        ("node", "rewrite"), ("node", "rewrite"),
        ("node", "verify"), ("node", "verify"),
        "token", "citations", "result", ("node", "__end__"), "done",
    ]
    statuses = [e["v"]["status"] for e in events if e["type"] == "node"]
    assert statuses == ["active", "done"] * 4 + ["done"]
    result = next(e for e in events if e["type"] == "result")
    assert set(result["v"]) == {"original", "rewritten", "changes", "caveats", "diff"}
    assert result["v"]["rewritten"] == GOOD


def test_stream_clean_input_skips_research_rewrite_verify(monkeypatch):
    calls = _install_chat(monkeypatch, ["SHOULD NEVER BE CALLED"])

    async def _collect():
        return [ev async for ev in migrate_mod.astream_migrate("x = 1\n")]

    events = asyncio.run(_collect())
    node_names = {e["v"]["name"] for e in events if e["type"] == "node"}
    assert node_names == {"detect", "__end__"}
    assert calls == []
    result = next(e for e in events if e["type"] == "result")
    assert result["v"]["rewritten"] == "x = 1\n" and result["v"]["diff"] == ""
    assert events[-1] == {"type": "done"}
