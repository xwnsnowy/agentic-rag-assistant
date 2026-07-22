"""Relevance identity must be (docs_version, slug), not slug alone.

Two slugs exist in BOTH corpora — `persistence` and `streaming` — so once v0.2
chunks are in the DB, slug-only matching would count a v0.2 `persistence` chunk
as a correct hit for a v1.0 `persistence` question. That inflates exactly the
mixed-corpus row S2.1 exists to measure, in the flattering direction.

Pure tests: no DB, no network. A minimal stand-in object provides `.metadata`,
which is all the metrics read.
"""

from dataclasses import dataclass, field

from eval.metrics import hit_at_k, precision_at_k, reciprocal_rank, relevance_flags


@dataclass
class FakeChunk:
    metadata: dict = field(default_factory=dict)


def v10(slug: str) -> FakeChunk:
    return FakeChunk(metadata={"slug": slug, "docs_version": "1.0"})


def v02(slug: str) -> FakeChunk:
    return FakeChunk(metadata={"slug": slug, "docs_version": "0.2"})


# --- the core identity ------------------------------------------------------


def test_right_version_and_slug_is_relevant():
    assert relevance_flags([v10("persistence")], ["persistence"]) == [True]


def test_same_slug_wrong_version_is_not_relevant():
    # The exact collision case: a v0.2 `persistence` chunk must NOT satisfy a
    # v1.0 `persistence` question.
    assert relevance_flags([v02("persistence")], ["persistence"]) == [False]


def test_right_version_wrong_slug_is_not_relevant():
    assert relevance_flags([v10("streaming")], ["persistence"]) == [False]


# --- deliberate handling of broken provenance -------------------------------


def test_missing_docs_version_is_not_relevant():
    # Migration 003 guarantees docs_version in metadata; if it's absent the
    # chunk's provenance is broken and it must not count as a hit (deflating,
    # never inflating).
    chunk = FakeChunk(metadata={"slug": "persistence"})
    assert relevance_flags([chunk], ["persistence"]) == [False]


def test_blank_docs_version_is_not_relevant():
    chunk = FakeChunk(metadata={"slug": "persistence", "docs_version": ""})
    assert relevance_flags([chunk], ["persistence"]) == [False]


def test_none_metadata_is_not_relevant():
    assert relevance_flags([FakeChunk(metadata=None)], ["persistence"]) == [False]


# --- the derived metrics respect the identity -------------------------------


def test_hit_ignores_wrong_version_chunks():
    results = [v02("persistence"), v02("streaming")]
    assert hit_at_k(results, ["persistence", "streaming"]) == 0.0
    assert hit_at_k(results + [v10("persistence")], ["persistence"]) == 1.0


def test_reciprocal_rank_skips_wrong_version_chunks():
    # First relevant chunk is at rank 3; the v0.2 look-alikes above it don't count.
    results = [v02("persistence"), v02("persistence"), v10("persistence")]
    assert reciprocal_rank(results, ["persistence"]) == 1.0 / 3


def test_precision_counts_only_right_version_matches():
    results = [v10("persistence"), v02("persistence"), v10("other"), v10("streaming")]
    assert precision_at_k(results, ["persistence", "streaming"]) == 2 / 4


def test_empty_results_precision_is_zero():
    assert precision_at_k([], ["persistence"]) == 0.0
