# Eval results (top-5)

- Embedding vectors: **real**
- LLM-judge: **on**  ·  answerable items: 26  ·  negatives: 4

| Config | hit@k | MRR | P@k | latency (ms) | faithfulness | relevancy | neg-handling |
|---|---|---|---|---|---|---|---|
| keyword | 0.462 | 0.367 | 0.351 | 345 | 0.492 | 0.512 | 1.000 |
| baseline | 0.962 | 0.897 | 0.585 | 1284 | 0.858 | 0.900 | 1.000 |
| hybrid | 0.962 | 0.888 | 0.562 | 1767 | 0.862 | 0.912 | 1.000 |
| hybrid+rerank | 1.000 | 0.923 | 0.723 | 3001 | 0.862 | 0.892 | 1.000 |