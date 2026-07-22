"""Schema/consistency tests for data/deprecations.json (S2.2).

The map is the ground truth the migration workbench will run on, so it gets
the same treatment as code: every entry must be well-formed, carry a verdict
from the allowed vocabulary, and point at a doc page that actually exists in
the corpus manifest it claims. Pure file checks - no DB, no network.
"""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

ALLOWED_STATUSES = {"deprecated", "renamed", "moved", "unchanged", "unevidenced"}
REQUIRED_KEYS = {"symbol", "status", "replacement", "note", "doc_slug", "doc_version"}


def _load():
    return json.loads((DATA / "deprecations.json").read_text(encoding="utf-8"))


def _manifest_slugs(name: str) -> set[str]:
    manifest = json.loads((DATA / name).read_text(encoding="utf-8"))
    return {f["slug"] for f in manifest["files"]}


def test_map_is_well_formed_and_nonempty():
    doc = _load()
    assert isinstance(doc["entries"], list) and len(doc["entries"]) >= 12


def test_every_entry_has_required_keys_and_valid_status():
    for e in _load()["entries"]:
        missing = REQUIRED_KEYS - set(e)
        assert not missing, f"{e.get('symbol')}: missing keys {missing}"
        assert e["status"] in ALLOWED_STATUSES, f"{e['symbol']}: bad status {e['status']}"
        assert e["symbol"].strip() and e["note"].strip()


def test_doc_slug_exists_in_the_claimed_corpus_manifest():
    slugs = {"1.0": _manifest_slugs("manifest.json"), "0.2": _manifest_slugs("manifest-0.2.json")}
    for e in _load()["entries"]:
        assert e["doc_version"] in slugs, f"{e['symbol']}: unknown doc_version"
        assert e["doc_slug"] in slugs[e["doc_version"]], (
            f"{e['symbol']}: doc_slug {e['doc_slug']!r} not in the "
            f"v{e['doc_version']} manifest"
        )


def test_actionable_statuses_name_a_replacement():
    # A verdict that implies migration must say what to migrate TO;
    # 'unchanged' must NOT invent one.
    for e in _load()["entries"]:
        if e["status"] in {"deprecated", "renamed", "moved"}:
            assert e["replacement"], f"{e['symbol']}: {e['status']} without a replacement"
        if e["status"] == "unchanged":
            assert e["replacement"] is None, f"{e['symbol']}: unchanged with a replacement"


def test_no_chunk_ids_stored():
    # Chunk ids are reassigned on every re-ingest; keying on them would rot.
    raw = (DATA / "deprecations.json").read_text(encoding="utf-8")
    assert "chunk_id" not in raw and '"id"' not in raw


def test_symbols_are_unique():
    symbols = [e["symbol"] for e in _load()["entries"]]
    assert len(symbols) == len(set(symbols))


def test_map_covers_both_verdict_directions():
    # A map that can only say 'deprecated' cannot be trusted to say 'this is
    # fine' - the workbench needs both verdicts (see PHASE_3.md S2.2).
    statuses = {e["status"] for e in _load()["entries"]}
    assert "unchanged" in statuses
    assert statuses & {"deprecated", "renamed", "moved"}
