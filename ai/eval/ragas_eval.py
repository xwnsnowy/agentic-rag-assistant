"""Score the exported samples with the real Ragas library.

Runs in the SEPARATE .venv-ragas (Python 3.12, langchain 0.3.x). It reads
eval/results/ragas_input.json (produced by scripts.export_for_ragas in the main
venv) and computes the four standard Ragas metrics with gpt-4o-mini + OpenAI
embeddings, then writes eval/results/ragas_scores.{json,md}.

Run (from ai/):  .venv-ragas/Scripts/python -m eval.ragas_eval
"""

import json
import os
from pathlib import Path

import truststore

truststore.inject_into_ssl()  # OS trust store (corporate/local CA)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # noqa: E402
from ragas import EvaluationDataset, evaluate  # noqa: E402
from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms import LangchainLLMWrapper  # noqa: E402
from ragas.metrics import (  # noqa: E402
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)

RESULTS = Path(__file__).resolve().parents[1] / "eval" / "results"
INPUT = RESULTS / "ragas_input.json"
INPUT_COLS = {"user_input", "response", "retrieved_contexts", "reference"}


def main() -> None:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    dataset = EvaluationDataset.from_list(payload["samples"])

    llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=os.environ.get("OPENROUTER_BASE", "https://api.openai.com/v1"),
            temperature=0,
        )
    )
    embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
            api_key=os.environ["EMBEDDING_API_KEY"],
            base_url=os.environ.get("EMBEDDING_API_BASE", "https://api.openai.com/v1"),
        )
    )

    result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
        ],
        llm=llm,
        embeddings=embeddings,
    )

    df = result.to_pandas()
    metric_cols = [c for c in df.columns if c not in INPUT_COLS]
    means = {c: round(float(df[c].mean()), 3) for c in metric_cols}

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "ragas_scores.json").write_text(
        json.dumps({"config": payload.get("config"), "n": len(df), "scores": means}, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Ragas eval (real library)",
        "",
        f"- config: **{payload.get('config')}**  ·  samples: {len(df)}  ·  judge: gpt-4o-mini",
        "",
        "| metric | score |",
        "|---|---|",
        *[f"| {c} | {means[c]:.3f} |" for c in metric_cols],
    ]
    (RESULTS / "ragas_scores.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved -> {RESULTS / 'ragas_scores.md'}")


if __name__ == "__main__":
    main()
