# Eval results (top-5)

- Embedding vectors: **real**
- LLM-judge: **on**  ·  answerable items: 26  ·  negatives: 4

| Config | hit@k | MRR | P@k | latency (ms) | faithfulness | relevancy | abstention |
|---|---|---|---|---|---|---|---|
| keyword | 0.462 | 0.367 | 0.351 | 441 | 0.469 | 0.492 | 0.500 |
| baseline | 0.962 | 0.897 | 0.585 | 1382 | 0.858 | 0.885 | 0.250 |
| hybrid | 0.962 | 0.888 | 0.562 | 1576 | 0.862 | 0.904 | 0.250 |
| hybrid+rerank | 1.000 | 0.923 | 0.723 | 2350 | 0.854 | 0.869 | 0.500 |