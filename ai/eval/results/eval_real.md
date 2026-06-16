# Eval results (top-5)

- Embedding vectors: **real**
- LLM-judge: **on**  ·  answerable items: 10  ·  negatives: 1

| Config | hit@k | MRR | P@k | latency (ms) | faithfulness | relevancy | abstention |
|---|---|---|---|---|---|---|---|
| keyword | 0.700 | 0.453 | 0.432 | 536 | 0.630 | 0.680 | 1.000 |
| baseline | 0.900 | 0.783 | 0.600 | 1555 | 0.830 | 0.870 | 1.000 |
| hybrid | 0.900 | 0.758 | 0.500 | 1657 | 0.840 | 0.900 | 1.000 |
| hybrid+rerank | 1.000 | 0.900 | 0.700 | 2576 | 0.770 | 0.790 | 1.000 |