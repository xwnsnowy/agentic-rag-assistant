# Migration eval — migration graph (gpt-4o-mini, detect -> research -> rewrite -> verify, pinned corpora)

**S2.4 — the migration graph** (`app/migrate.py`): deterministic AST `detect`
against `data/deprecations.json`, `research` via check_api_status + rag_search
over the pinned corpora, one grounded structured-output `rewrite`, deterministic
`verify` with one bounded retry. Scored by the identical harness code path as
the raw-LLM baseline.

Across all 20 items the graph reported **12 changes** and **7 caveats**.

Reproduce: `python -m scripts.run_migration_eval --mode agent` (from `ai/`).

| metric | raw-LLM baseline | migration graph |
|---|---|---|
| parses | 1.000 | **1.000** |
| deprecated_removed | 0.000 | **1.000** |
| idiom_present | 0.000 | **1.000** |
| citation_coverage | 0.000 | **1.000** |
| clean_passthrough | 1.000 | **1.000** |
| flagged_not_rewritten | 0.000 | **1.000** |

- items: 20 (modernize 10 / flag 6 / clean 4)
- parses: **1.000**
- deprecated_removed (modernize): **1.000**
- idiom_present (modernize): **1.000**
- citation_coverage (modernize): **1.000**
- clean_passthrough (clean): **1.000**
- flagged_not_rewritten (flag): **1.000**

| id | kind | parses | removed | idiom | cites | passthrough | flagged | changes | caveats |
|---|---|---|---|---|---|---|---|---|---|
| mig-001 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 1 | 0 |
| mig-002 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 1 | 0 |
| mig-003 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 2 | 0 |
| mig-004 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 1 | 0 |
| mig-005 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 1 | 0 |
| mig-006 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 1 | 0 |
| mig-007 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 1 | 0 |
| mig-008 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 2 | 0 |
| mig-009 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 1 | 0 |
| mig-010 | modernize | ✓ | ✓ | ✓ | 1.00 | — | — | 1 | 0 |
| mig-011 | flag | ✓ | — | — | — | — | ✓ | 0 | 1 |
| mig-012 | flag | ✓ | — | — | — | — | ✓ | 0 | 1 |
| mig-013 | flag | ✓ | — | — | — | — | ✓ | 0 | 1 |
| mig-014 | flag | ✓ | — | — | — | — | ✓ | 0 | 1 |
| mig-015 | flag | ✓ | — | — | — | — | ✓ | 0 | 1 |
| mig-016 | flag | ✓ | — | — | — | — | ✓ | 0 | 2 |
| mig-017 | clean | ✓ | — | — | — | ✓ | — | 0 | 0 |
| mig-018 | clean | ✓ | — | — | — | ✓ | — | 0 | 0 |
| mig-019 | clean | ✓ | — | — | — | ✓ | — | 0 | 0 |
| mig-020 | clean | ✓ | — | — | — | ✓ | — | 0 | 0 |
