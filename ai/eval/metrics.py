"""Retrieval metrics with (docs_version, slug)-level relevance.

The golden dataset marks, per question, which corpus doc page(s) (`expected_slugs`)
a correct retrieval should surface. Every `ground_truth` was verified against the
pinned **v1.0** docs, so `expected_slugs` name v1.0 pages — and slug alone is NOT
a page identity once two corpus versions coexist: `persistence` and `streaming`
exist in both v0.2 and v1.0, naming different documents. A retrieved chunk is
therefore "relevant" only if it is a v1.0 chunk whose slug is in the expected set.

Judging by slug alone would let a v0.2 `persistence` chunk score as a correct hit
for a v1.0 `persistence` question — inflating precisely the mixed-corpus row that
is supposed to show degradation (an error in the flattering direction).

Version handling is deliberate, not defaulted: migration 003 guarantees every
chunk carries `docs_version` in metadata, so a missing/blank value means broken
provenance and the chunk counts as NOT relevant. That failure mode can only
deflate scores, never inflate them — the safe direction for an eval.

  hit@k          : did ANY of the top-k come from an expected page? (0/1)
  reciprocal_rank: 1 / rank of the first relevant chunk (0 if none) -> MRR when averaged
  precision@k    : fraction of the top-k that are relevant
"""

from __future__ import annotations

# The corpus version the golden dataset's expected_slugs (and ground truths)
# were verified against.
GOLDEN_DOCS_VERSION = "1.0"


def _is_relevant(chunk_metadata: dict, expected: set[str]) -> bool:
    m = chunk_metadata or {}
    return m.get("docs_version") == GOLDEN_DOCS_VERSION and m.get("slug") in expected


def relevance_flags(results, expected_slugs: list[str]) -> list[bool]:
    expected = set(expected_slugs)
    return [_is_relevant(r.metadata, expected) for r in results]


def hit_at_k(results, expected_slugs: list[str]) -> float:
    return 1.0 if any(relevance_flags(results, expected_slugs)) else 0.0


def reciprocal_rank(results, expected_slugs: list[str]) -> float:
    for i, rel in enumerate(relevance_flags(results, expected_slugs), 1):
        if rel:
            return 1.0 / i
    return 0.0


def precision_at_k(results, expected_slugs: list[str]) -> float:
    flags = relevance_flags(results, expected_slugs)
    return sum(flags) / len(flags) if flags else 0.0
