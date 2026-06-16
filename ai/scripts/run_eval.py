"""Run the eval harness and print/save the comparison table.

Usage (from ai/):
  python -m scripts.run_eval               # retrieval metrics only
  python -m scripts.run_eval --judge       # + faithfulness/relevancy (needs OpenRouter key)
  python -m scripts.run_eval -k 10
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import observability as obs  # noqa: E402
from eval.harness import render_markdown, run_eval, save  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--judge", action="store_true", help="run LLM-as-judge generation metrics")
    args = ap.parse_args()

    summary = run_eval(k=args.k, judge=args.judge)
    print(render_markdown(summary))
    out = save(summary)
    obs.flush()  # ship buffered Langfuse traces before exit
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
