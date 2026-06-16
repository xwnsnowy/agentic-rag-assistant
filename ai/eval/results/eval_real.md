# Eval results (top-5)

- Embedding vectors: **real**
- LLM-judge: **on**  ·  answerable items: 10  ·  negatives: 1

| Config | hit@k | MRR | P@k | latency (ms) | faithfulness | relevancy | abstention |
|---|---|---|---|---|---|---|---|
| keyword | 0.700 | 0.453 | 0.432 | 344 | 0.630 | 0.680 | 1.000 |
| baseline | 0.900 | 0.783 | 0.600 | 1260 | 0.810 | 0.870 | 1.000 |
| hybrid | 0.900 | 0.758 | 0.500 | 1614 | 0.820 | 0.900 | 1.000 |
| hybrid+rerank | 0.900 | 0.758 | 0.500 | 1497 | 0.840 | 0.900 | 1.000 |