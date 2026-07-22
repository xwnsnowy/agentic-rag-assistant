"""Pure tests for the migration workbench core (app/migrate.py, S2.4).

No LLM, no DB, no network: detect and verify are the deterministic halves of
the pipeline and must be fully trustable in CI — they are what closed the
baseline's blindness gap, so they get the direct coverage.
"""

import ast

from app.migrate import (
    MAX_CODE_CHARS,
    collect_symbols,
    detect_findings,
    flag_caveat,
    make_diff,
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
