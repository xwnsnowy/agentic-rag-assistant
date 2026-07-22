"""Integrity tests for eval/migration_dataset.json (S2.3).

The golden set is scored deterministically, so a malformed item would fail
silently as a wrong number rather than loudly as an error - these tests make
the dataset itself part of the contract. Pure file checks: no DB, no network,
no keys.
"""

import ast
import json
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
DATASET = AI / "eval" / "migration_dataset.json"
DEPRECATIONS = AI / "data" / "deprecations.json"

REQUIRED_KEYS = {
    "id",
    "kind",
    "symbols",
    "legacy_code",
    "must_not_contain",
    "must_contain",
    "expected_citation_slugs",
    "taught_in",
    "note",
}
KINDS = {"modernize", "flag", "clean"}

# kind of a dataset item <-> status of the deprecations.json entries it uses.
# This weld is the point: the dataset is *derived* from the map, so the two
# can never drift apart without a test failing.
KIND_TO_STATUSES = {
    "modernize": {"deprecated", "renamed", "moved"},
    "flag": {"unevidenced"},
    "clean": {"unchanged"},
}


def _items():
    return json.loads(DATASET.read_text(encoding="utf-8"))["items"]


def _dep_entries():
    doc = json.loads(DEPRECATIONS.read_text(encoding="utf-8"))
    return {e["symbol"]: e for e in doc["entries"]}


def _manifest_slugs():
    slugs = set()
    for name in ("manifest.json", "manifest-0.2.json"):
        manifest = json.loads((AI / "data" / name).read_text(encoding="utf-8"))
        slugs |= {f["slug"] for f in manifest["files"]}
    return slugs


def test_dataset_is_wellformed_with_unique_ids():
    items = _items()
    assert len(items) >= 18
    ids = [it["id"] for it in items]
    assert len(ids) == len(set(ids))
    for it in items:
        missing = REQUIRED_KEYS - set(it)
        assert not missing, f"{it.get('id')}: missing keys {missing}"
        assert it["kind"] in KINDS, f"{it['id']}: bad kind {it['kind']!r}"
        assert it["symbols"], f"{it['id']}: empty symbols"
        assert it["taught_in"].strip(), f"{it['id']}: taught_in must cite the corpus"


def test_all_three_kinds_are_covered():
    # A set without clean items cannot catch a tool that always "fixes"
    # something; a set without flag items cannot measure the epistemics.
    counts = {}
    for it in _items():
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
    assert counts.get("modernize", 0) >= 6
    assert counts.get("flag", 0) >= 4
    assert counts.get("clean", 0) >= 3


def test_every_legacy_snippet_parses():
    # Snippets must be syntactically complete: the harness's `parses` metric
    # is meaningless if the *input* was already broken.
    for it in _items():
        ast.parse(it["legacy_code"])


def test_must_not_contain_actually_occurs_in_legacy_code():
    # Otherwise deprecated_removed would be vacuously true.
    for it in _items():
        for bad in it["must_not_contain"]:
            assert bad in it["legacy_code"], f"{it['id']}: {bad!r} not in legacy_code"


def test_expectations_match_kind():
    for it in _items():
        if it["kind"] == "modernize":
            assert it["must_not_contain"], f"{it['id']}: modernize needs must_not_contain"
            assert it["must_contain"], f"{it['id']}: modernize needs must_contain"
            assert it["expected_citation_slugs"], f"{it['id']}: modernize needs slugs"
        else:
            # flag: what's measured is the caveat + untouched code, not strings;
            # clean: correct output reports no changes, so nothing to cite.
            assert not it["must_not_contain"], f"{it['id']}: {it['kind']} must not ban strings"
            assert not it["must_contain"], f"{it['id']}: {it['kind']} must not require strings"
        if it["kind"] == "flag":
            assert it["expected_citation_slugs"], f"{it['id']}: flag needs evidence slugs"
        if it["kind"] == "clean":
            assert not it["expected_citation_slugs"], f"{it['id']}: clean cites nothing"


def test_citation_slugs_exist_in_a_corpus_manifest():
    slugs = _manifest_slugs()
    for it in _items():
        for slug in it["expected_citation_slugs"]:
            assert slug in slugs, f"{it['id']}: slug {slug!r} not in any manifest"


def test_symbols_exist_in_deprecations_map_and_statuses_agree():
    deps = _dep_entries()
    for it in _items():
        for sym in it["symbols"]:
            assert sym in deps, f"{it['id']}: symbol {sym!r} not in deprecations.json"
            status = deps[sym]["status"]
            allowed = KIND_TO_STATUSES[it["kind"]]
            assert status in allowed, (
                f"{it['id']}: symbol {sym!r} has status {status!r}, "
                f"incompatible with kind {it['kind']!r}"
            )


def test_flag_symbols_appear_in_their_snippets():
    # A flag item's snippet must actually use the unevidenced symbol,
    # or flagged_not_rewritten measures nothing.
    for it in _items():
        if it["kind"] == "flag":
            for sym in it["symbols"]:
                assert sym in it["legacy_code"], f"{it['id']}: {sym!r} not in snippet"
