# Eval results (top-5)

- Embedding vectors: **real**
- LLM-judge: **on**  ·  answerable items: 44  ·  negatives: 6

| Config | hit@k | MRR | P@k | latency (ms) | faithfulness | relevancy | ctx-prec | ctx-recall | neg-handling |
|---|---|---|---|---|---|---|---|---|---|
| keyword | 0.386 | 0.330 | 0.298 | 429 | 0.432 | 0.455 | 0.430 | 0.416 | 1.000 |
| baseline | 0.977 | 0.902 | 0.627 | 1422 | 0.895 | 0.920 | 0.889 | 0.877 | 1.000 |
| hybrid | 0.977 | 0.896 | 0.627 | 2028 | 0.898 | 0.927 | 0.899 | 0.886 | 1.000 |
| hybrid+rerank | 1.000 | 0.928 | 0.727 | 3001 | 0.918 | 0.927 | 0.918 | 0.914 | 1.000 |