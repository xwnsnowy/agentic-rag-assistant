"""Run the agent tool-selection eval and print/save the table.

Usage (from ai/):  python -m scripts.run_agent_eval
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.agent_harness import render, run_agent_eval  # noqa: E402

RESULTS = Path(__file__).resolve().parents[1] / "eval" / "results"


def main() -> None:
    summary = run_agent_eval()
    md = render(summary)
    print(md)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "agent_eval.md").write_text(md, encoding="utf-8")
    (RESULTS / "agent_eval.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved -> {RESULTS / 'agent_eval.md'}")


if __name__ == "__main__":
    main()
