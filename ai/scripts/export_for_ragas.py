"""Export (question, answer, contexts, ground_truth) for the Ragas eval.

Runs in the MAIN venv (langchain 1.x): for the production config (hybrid+rerank)
it retrieves + generates over the answerable golden items and writes a plain JSON
file. The separate Ragas venv then reads that file — no shared imports, so the
incompatible langchain stacks never meet.

Usage (from ai/):  python -m scripts.export_for_ragas
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.generation import generate  # noqa: E402
from app.pipeline import HYBRID_RERANK, retrieve  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "golden_dataset_langgraph.json"
OUT = Path(__file__).resolve().parents[1] / "eval" / "results" / "ragas_input.json"


def main() -> None:
    items = json.loads(DATASET.read_text(encoding="utf-8"))["items"]
    answerable = [i for i in items if i.get("expected_slugs")]

    rows = []
    for i, item in enumerate(answerable, 1):
        results = retrieve(item["question"], HYBRID_RERANK)
        ans = generate(item["question"], results)
        rows.append({
            "user_input": item["question"],
            "response": ans.text or "",
            "retrieved_contexts": [r.content for r in results],
            "reference": item["ground_truth"],
        })
        print(f"  [{i}/{len(answerable)}] {item['id']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"config": "hybrid+rerank", "samples": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(rows)} samples -> {OUT}")


if __name__ == "__main__":
    main()
