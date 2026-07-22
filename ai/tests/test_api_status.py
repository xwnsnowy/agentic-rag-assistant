"""Unit tests for check_api_status (S2.2): verdict logic + rendering.

Pure - the occurrence counts come from a fake table (monkeypatched), never the
DB, and the curated entries are inline fixtures so a map edit can't silently
change what these tests assert. One integration-ish test reads the real
deprecations.json to pin the set_entry_point verdict the whole step hinges on.
"""

import app.tools as tools_mod
from app.tools import (
    _deprecation_entry,
    _normalize_symbol,
    check_api_status,
    render_api_status,
)


def _entry(status: str, replacement=None, symbol="some_symbol") -> dict:
    return {
        "symbol": symbol,
        "status": status,
        "replacement": replacement,
        "note": "test note.",
        "doc_slug": "graph-api",
        "doc_version": "1.0",
    }


COUNTS = {"0.2": 6, "1.0": 0}


# --- normalization -----------------------------------------------------------


def test_normalize_strips_calls_quotes_and_dotted_prefixes():
    assert _normalize_symbol("set_entry_point()") == "set_entry_point"
    assert _normalize_symbol("`set_entry_point`") == "set_entry_point"
    assert _normalize_symbol("graph.update_state") == "update_state"
    assert _normalize_symbol(" langgraph.prebuilt.ToolNode ") == "ToolNode"
    assert _normalize_symbol("") == ""


# --- rendering: every status must read sensibly ------------------------------


def test_deprecated_renders_replacement_and_still_works():
    out = render_api_status("s", _entry("deprecated", "add_edge(START, node)"), COUNTS)
    assert "still works in v1.0" in out and "add_edge(START, node)" in out
    assert "[graph-api]" in out


def test_renamed_and_moved_render_the_replacement():
    assert "use context_schema" in render_api_status(
        "s", _entry("renamed", "context_schema"), COUNTS
    )
    assert "use langchain.agents.create_agent" in render_api_status(
        "s", _entry("moved", "langchain.agents.create_agent"), COUNTS
    )


def test_unchanged_says_no_migration_needed():
    out = render_api_status("s", _entry("unchanged"), {"0.2": 3, "1.0": 9})
    assert "no migration needed" in out
    assert "3 chunk(s) of the v0.2" in out and "9 chunk(s) of the v1.0" in out


def test_unevidenced_claims_no_verdict_it_does_not_have():
    out = render_api_status("s", _entry("unevidenced", "interrupt()"), COUNTS)
    assert "cannot confirm" in out
    assert "interrupt() instead" in out


def test_unknown_symbol_reports_counts_only_and_no_verdict():
    out = render_api_status("mystery_fn", None, {"0.2": 2, "1.0": 0})
    assert "no verified verdict" in out
    assert "2 chunk(s) of the v0.2" in out
    # It must say what counts CANNOT tell, not imply a removal.
    assert "Counts alone cannot say" in out
    assert "removed" in out


def test_db_down_degrades_to_verdict_without_counts():
    out = render_api_status("s", _entry("renamed", "context_schema"), None)
    assert "use context_schema" in out
    assert "unavailable" in out


# --- the tool end-to-end (counts faked, real curated map) --------------------


def test_tool_normalizes_input_and_uses_the_real_map(monkeypatch):
    monkeypatch.setattr(tools_mod, "_symbol_counts", lambda s: {"0.2": 0, "1.0": 2})
    out = check_api_status.invoke({"symbol": "builder.set_entry_point()"})
    # The corpus-verified verdict: NOT removed - v1.0 graph-api.md says both
    # methods are valid but add_edge(START, ...) is the recommended syntax.
    assert "still works in v1.0" in out
    assert "add_edge(START, node)" in out
    assert "[graph-api]" in out


def test_tool_empty_symbol_asks_for_one(monkeypatch):
    monkeypatch.setattr(tools_mod, "_symbol_counts", lambda s: COUNTS)
    assert "provide a symbol" in check_api_status.invoke({"symbol": "  "})


def test_real_map_lookup_is_case_insensitive():
    assert _deprecation_entry("stategraph")["symbol"] == "StateGraph"
    assert _deprecation_entry("no_such_symbol_xyz") is None
