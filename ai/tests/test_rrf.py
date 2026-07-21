"""Unit tests for Reciprocal Rank Fusion (app/retrieval.py:rrf_fuse).

Pure: rrf_fuse takes two ranked Result lists and returns the fused ranking,
so no Postgres is needed. Also includes a behaviour-preservation test that
runs the pre-refactor inline fusion loop (copied verbatim from the old
hybrid_search) against the extracted rrf_fuse on the same fixture.
"""

import copy

from app.retrieval import Result, rrf_fuse


def vec_result(chunk_id: int, rank: int, **meta) -> Result:
    """A Result as vector_search would build it (rank is 1-based)."""
    return Result(
        chunk_id=chunk_id,
        content=f"content-{chunk_id}",
        metadata={"page_title": f"page-{chunk_id}", **meta},
        vector_rank=rank,
        vector_score=1.0 - rank * 0.01,
    )


def kw_result(chunk_id: int, rank: int, **meta) -> Result:
    """A Result as keyword_search would build it (rank is 1-based)."""
    return Result(
        chunk_id=chunk_id,
        content=f"content-{chunk_id}",
        metadata={"page_title": f"page-{chunk_id}", **meta},
        keyword_rank=rank,
        keyword_score=0.9 - rank * 0.01,
    )


def test_chunk_in_both_lists_beats_single_list_number_one():
    vec = [vec_result(1, 1), vec_result(2, 2)]
    kw = [kw_result(1, 1), kw_result(3, 2)]
    fused = rrf_fuse(vec, kw)

    assert fused[0].chunk_id == 1  # #1 in both > #1 in only one list
    # Both per-method ranks were merged onto the surviving Result.
    assert fused[0].vector_rank == 1
    assert fused[0].keyword_rank == 1


def test_score_is_exactly_reciprocal_rank_sum_with_default_k():
    vec = [vec_result(1, 1), vec_result(2, 2)]
    kw = [kw_result(2, 1), kw_result(3, 2)]
    fused = {r.chunk_id: r for r in rrf_fuse(vec, kw)}

    assert fused[1].rrf_score == 1.0 / (60 + 1)  # vector-only, rank 1
    assert fused[2].rrf_score == 1.0 / (60 + 2) + 1.0 / (60 + 1)  # both lists
    assert fused[3].rrf_score == 1.0 / (60 + 2)  # keyword-only, rank 2


def test_keyword_only_chunk_survives_with_metadata_intact():
    vec = [vec_result(1, 1)]
    kw = [kw_result(7, 1, source_url="https://example.com/x#frag", heading="H")]
    fused = rrf_fuse(vec, kw)

    survivor = next(r for r in fused if r.chunk_id == 7)
    assert survivor.metadata["source_url"] == "https://example.com/x#frag"
    assert survivor.metadata["heading"] == "H"
    assert survivor.keyword_rank == 1
    assert survivor.vector_rank is None
    assert survivor.content == "content-7"


def test_rrf_k_override_is_honoured():
    vec = [vec_result(1, 1)]
    kw = [kw_result(1, 2)]
    fused = rrf_fuse(vec, kw, rrf_k=10)
    assert fused[0].rrf_score == 1.0 / (10 + 1) + 1.0 / (10 + 2)


def test_equal_scores_tiebreak_keeps_vector_hits_before_keyword_only():
    # id 1 (vector rank 2) and id 2 (keyword rank 2) score identically:
    # sorted() is stable, so the vector-list entry (inserted first) stays first.
    vec = [vec_result(9, 1), vec_result(1, 2)]
    kw = [kw_result(9, 1), kw_result(2, 2)]
    fused = rrf_fuse(vec, kw)
    assert fused[0].chunk_id == 9
    assert fused[1].rrf_score == fused[2].rrf_score
    assert [r.chunk_id for r in fused[1:]] == [1, 2]


def _old_inline_fusion(vec, kw, k, *, pool_unused=None, rrf_k=60):
    """The fusion loop exactly as it lived inside hybrid_search before S1.0
    (commit a8270d9 and earlier), minus the two DB calls around it."""
    merged = {}
    for r in vec:
        merged[r.chunk_id] = r
    for r in kw:
        if r.chunk_id in merged:
            merged[r.chunk_id].keyword_rank = r.keyword_rank
            merged[r.chunk_id].keyword_score = r.keyword_score
        else:
            merged[r.chunk_id] = r

    for r in merged.values():
        score = 0.0
        if r.vector_rank:
            score += 1.0 / (rrf_k + r.vector_rank)
        if r.keyword_rank:
            score += 1.0 / (rrf_k + r.keyword_rank)
        r.rrf_score = score

    ranked = sorted(merged.values(), key=lambda r: r.rrf_score or 0.0, reverse=True)
    return ranked[:k]


def test_rrf_fuse_matches_pre_refactor_inline_logic():
    """Behaviour preservation: old inline loop and new rrf_fuse must produce
    identical output (scores, ordering, tie-breaks, merged metadata) on a
    fixture with overlap, single-list survivors, and exact score ties."""
    vec = [vec_result(1, 1), vec_result(2, 2), vec_result(3, 3), vec_result(4, 4)]
    kw = [kw_result(3, 1), kw_result(5, 2), kw_result(2, 3), kw_result(6, 4)]
    k = 5

    old = _old_inline_fusion(copy.deepcopy(vec), copy.deepcopy(kw), k)
    new = rrf_fuse(copy.deepcopy(vec), copy.deepcopy(kw))[:k]

    assert old == new  # dataclass equality: every field of every Result
    assert [r.chunk_id for r in old] == [r.chunk_id for r in new]
    assert [r.rrf_score for r in old] == [r.rrf_score for r in new]
