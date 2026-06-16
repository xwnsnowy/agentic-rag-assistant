"""Quick CLI to eyeball retrieval results from each strategy.

Usage (from ai/):
  python -m scripts.search "how do I add memory to a graph?"
  python -m scripts.search "persistence checkpointer" --method keyword
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.retrieval import hybrid_search, keyword_search, vector_search  # noqa: E402

METHODS = {"vector": vector_search, "keyword": keyword_search, "hybrid": hybrid_search}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--method", choices=METHODS, default="hybrid")
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args()

    results = METHODS[args.method](args.query, k=args.k)
    print(f"[{args.method}] top {len(results)} for: {args.query!r}\n")
    for i, r in enumerate(results, 1):
        bits = []
        if r.vector_rank:
            bits.append(f"vec#{r.vector_rank}")
        if r.keyword_rank:
            bits.append(f"kw#{r.keyword_rank}")
        if r.rrf_score is not None:
            bits.append(f"rrf={r.rrf_score:.4f}")
        m = r.metadata or {}
        print(f"{i}. chunk {r.chunk_id}  [{' '.join(bits)}]")
        print(f"   {m.get('page_title','?')} > {m.get('heading','')}")
        print(f"   {r.content[:120].replace(chr(10),' ')}...\n")


if __name__ == "__main__":
    main()
