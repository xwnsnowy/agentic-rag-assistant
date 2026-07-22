"""Pure tests for eval/migration_harness.py (S2.3): every metric against
synthetic before/after pairs. No LLM, no DB, no keys - the deterministic
scoring is the part of the eval that must be trustable in CI.
"""

from eval.migration_harness import (
    Change,
    MigrationOutput,
    normalize_code,
    render_markdown,
    run_migration_eval,
    score_item,
)

# --- synthetic items ---------------------------------------------------------

MODERNIZE = {
    "id": "syn-mod",
    "kind": "modernize",
    "symbols": ["set_entry_point"],
    "legacy_code": 'builder.set_entry_point("a")\n',
    "must_not_contain": ["set_entry_point"],
    "must_contain": ["add_edge(START"],
    "expected_citation_slugs": ["graph-api"],
    "note": "",
}

FLAG = {
    "id": "syn-flag",
    "kind": "flag",
    "symbols": ["update_state"],
    "legacy_code": 'graph.update_state(config, {"foo": 2})\n',
    "must_not_contain": [],
    "must_contain": [],
    "expected_citation_slugs": ["persistence"],
    "note": "",
}

CLEAN = {
    "id": "syn-clean",
    "kind": "clean",
    "symbols": ["StateGraph"],
    "legacy_code": "def f(x):\n    return x + 1\n",
    "must_not_contain": [],
    "must_contain": [],
    "expected_citation_slugs": [],
    "note": "",
}


# --- normalize_code ----------------------------------------------------------

def test_normalize_ignores_blank_lines_and_trailing_whitespace():
    a = "def f(x):\n    return x\n"
    b = "def f(x):   \n\n\n    return x"
    assert normalize_code(a) == normalize_code(b)


def test_normalize_keeps_indentation_and_tokens_strict():
    assert normalize_code("def f(x):\n    return x") != normalize_code(
        "def f(x):\n        return x"
    )
    assert normalize_code("x = 'a'") != normalize_code('x = "a"')


def test_normalize_strips_markdown_fences():
    fenced = "```python\ndef f(x):\n    return x\n```"
    assert normalize_code(fenced) == normalize_code("def f(x):\n    return x")


# --- parses ------------------------------------------------------------------

def test_parses_rejects_broken_code():
    s = score_item(MODERNIZE, MigrationOutput(code="def broken(:\n"))
    assert s["parses"] is False


def test_parses_accepts_fenced_code():
    out = MigrationOutput(code="```python\nx = 1\n```")
    assert score_item(CLEAN, out)["parses"] is True


# --- modernize metrics -------------------------------------------------------

def test_modernize_good_rewrite_scores_full():
    out = MigrationOutput(
        code='builder.add_edge(START, "a")\n',
        changes=(Change("entry point -> START edge", citations=("graph-api",)),),
    )
    s = score_item(MODERNIZE, out)
    assert s["deprecated_removed"] is True
    assert s["idiom_present"] is True
    assert s["citation_coverage"] == 1.0


def test_modernize_surviving_deprecated_string_fails():
    out = MigrationOutput(
        code='builder.set_entry_point("a")\nbuilder.add_edge(START, "a")\n'
    )
    s = score_item(MODERNIZE, out)
    assert s["deprecated_removed"] is False
    assert s["idiom_present"] is True


def test_modernize_missing_idiom_fails():
    out = MigrationOutput(code='builder.add_edge("__start__", "a")\n')
    assert score_item(MODERNIZE, out)["idiom_present"] is False


def test_citation_coverage_zero_when_no_changes_reported():
    # A modernize item that reports nothing has hidden its work: score 0.
    out = MigrationOutput(code='builder.add_edge(START, "a")\n')
    assert score_item(MODERNIZE, out)["citation_coverage"] == 0.0


def test_citation_coverage_zero_for_wrong_or_missing_slug():
    out = MigrationOutput(
        code='builder.add_edge(START, "a")\n',
        changes=(
            Change("did it", citations=("streaming",)),
            Change("did it again", citations=()),
        ),
    )
    assert score_item(MODERNIZE, out)["citation_coverage"] == 0.0


def test_citation_coverage_is_a_fraction():
    out = MigrationOutput(
        code='builder.add_edge(START, "a")\n',
        changes=(
            Change("cited", citations=("graph-api",)),
            Change("uncited", citations=()),
        ),
    )
    assert score_item(MODERNIZE, out)["citation_coverage"] == 0.5


# --- clean_passthrough -------------------------------------------------------

def test_clean_unchanged_passes_even_with_whitespace_noise():
    out = MigrationOutput(code="def f(x):   \n\n    return x + 1\n\n")
    assert score_item(CLEAN, out)["clean_passthrough"] is True


def test_clean_any_token_change_fails():
    out = MigrationOutput(code="def f(x):\n    return x + 2\n")
    assert score_item(CLEAN, out)["clean_passthrough"] is False


# --- flagged_not_rewritten ---------------------------------------------------

def test_flag_unchanged_with_named_caveat_passes():
    out = MigrationOutput(
        code=FLAG["legacy_code"],
        caveats=("update_state is absent from the pinned v1.0 corpus; kept as-is.",),
    )
    assert score_item(FLAG, out)["flagged_not_rewritten"] is True


def test_flag_silently_rewritten_scores_zero():
    out = MigrationOutput(code='graph.invoke(Command(resume="x"), config=config)\n')
    assert score_item(FLAG, out)["flagged_not_rewritten"] is False


def test_flag_rewritten_even_with_caveat_scores_zero():
    # Rewriting on unevidenced grounds is wrong even when admitted: the map's
    # own epistemics say absence from 12 pages is not proof of removal.
    out = MigrationOutput(
        code='graph.invoke(Command(resume="x"), config=config)\n',
        caveats=("update_state might be removed",),
    )
    assert score_item(FLAG, out)["flagged_not_rewritten"] is False


def test_flag_unchanged_but_generic_caveat_scores_zero():
    # A boilerplate "please review" that names nothing is not a flag.
    out = MigrationOutput(code=FLAG["legacy_code"], caveats=("please review manually",))
    assert score_item(FLAG, out)["flagged_not_rewritten"] is False


def test_flag_unchanged_without_caveat_scores_zero():
    out = MigrationOutput(code=FLAG["legacy_code"])
    assert score_item(FLAG, out)["flagged_not_rewritten"] is False


# --- run_migration_eval ------------------------------------------------------

def test_run_eval_aggregates_and_survives_a_crashing_runner(monkeypatch):
    import eval.migration_harness as mh

    monkeypatch.setattr(mh, "load_dataset", lambda: [MODERNIZE, FLAG, CLEAN])

    def runner(item):
        if item["kind"] == "modernize":
            raise RuntimeError("boom")  # one bad item must not kill the run
        return MigrationOutput(
            code=item["legacy_code"],
            caveats=("update_state kept: unevidenced in the v1.0 corpus",),
        )

    summary = mh.run_migration_eval(runner, label="synthetic")
    assert summary["n"] == 3
    assert summary["by_kind"] == {"modernize": 1, "flag": 1, "clean": 1}
    m = summary["metrics"]
    assert m["clean_passthrough"] == 1.0
    assert m["flagged_not_rewritten"] == 1.0
    # the crashed modernize item scores zero everywhere, including parses ""
    assert m["deprecated_removed"] == 0.0
    assert m["citation_coverage"] == 0.0
    err_row = next(r for r in summary["rows"] if r["id"] == "syn-mod")
    assert err_row["error"] and "boom" in err_row["error"]

    md = render_markdown(summary)
    assert "syn-clean" in md and "flagged_not_rewritten" in md


def test_crashed_item_fails_parses_metric(monkeypatch):
    import eval.migration_harness as mh

    monkeypatch.setattr(mh, "load_dataset", lambda: [CLEAN])
    summary = mh.run_migration_eval(
        lambda item: (_ for _ in ()).throw(ValueError("x")), label="synthetic"
    )
    assert summary["metrics"]["parses"] == 0.0
