"""Ask the LangGraph agent a question from the CLI.

Usage (from ai/):
  python -m scripts.agent_ask "What is a checkpointer, and what is 12*9?"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import observability as obs  # noqa: E402
from app.agent import run_agent  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: python -m scripts.agent_ask "<question>"')
        raise SystemExit(2)
    res = run_agent(" ".join(sys.argv[1:]))
    obs.flush()
    print(f"tools used : {res.tools_used}  (rounds: {res.rounds})")
    print(f"\n{res.answer}")


if __name__ == "__main__":
    main()
