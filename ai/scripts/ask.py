"""Ask the full RAG pipeline a question (retrieve -> rerank -> generate).

Usage (from ai/):
  python -m scripts.ask "How do I add short-term memory to a graph?"
  python -m scripts.ask "..." --config hybrid+rerank

Without OPENROUTER_API_KEY it runs dry: prints the retrieved context that WOULD
be sent to the LLM (so you can sanity-check retrieval before spending tokens).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import CONFIGS, HYBRID_RERANK, answer_question  # noqa: E402

BY_NAME = {c.name: c for c in CONFIGS}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--config", choices=BY_NAME, default=HYBRID_RERANK.name)
    args = ap.parse_args()

    ans = answer_question(args.query, BY_NAME[args.config])

    if ans.text is None:
        print(f"[dry-run: no OPENROUTER_API_KEY] retrieved {len(ans.context)} chunks:\n")
        for i, r in enumerate(ans.context, 1):
            m = r.metadata or {}
            print(f"[{i}] {m.get('page_title','?')} > {m.get('heading','')}  (chunk {r.chunk_id})")
        return

    print("ANSWER:\n" + ans.text)
    print("\nCITATIONS:")
    for c in ans.citations:
        print(f"  [{c['n']}] {c['page_title']} > {c['heading']}  {c['source_url']}")


if __name__ == "__main__":
    main()
