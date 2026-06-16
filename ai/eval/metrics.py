"""Retrieval metrics with slug-level relevance.

The golden dataset marks, per question, which corpus doc page(s) (`expected_slugs`)
a correct retrieval should surface. A retrieved chunk is "relevant" if its source
slug is in that set. This gives well-defined metrics without hand-labelling every
one of the 244 chunks:

  hit@k          : did ANY of the top-k come from an expected page? (0/1)
  reciprocal_rank: 1 / rank of the first relevant chunk (0 if none) -> MRR when averaged
  precision@k    : fraction of the top-k that are relevant
"""

from __future__ import annotations


def _slug(chunk_metadata: dict) -> str:
    return (chunk_metadata or {}).get("slug", "")


def relevance_flags(results, expected_slugs: list[str]) -> list[bool]:
    expected = set(expected_slugs)
    return [_slug(r.metadata) in expected for r in results]


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
