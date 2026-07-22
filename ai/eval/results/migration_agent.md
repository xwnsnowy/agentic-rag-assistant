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

## How to read a perfect score (do not overclaim this table)

A row of 1.000s deserves scrutiny, so here is what each column did and did not earn.

**`deprecated_removed` and `idiom_present` are largely true by construction.** `detect`
walks the AST against `deprecations.json`, and the dataset is derived from that same
map — so detection cannot miss, and a symbol the detector found is a symbol the rewrite
was explicitly told to replace. That is the architecture working as designed (the whole
point of the baseline was that a bare LLM never *notices*), but it is not evidence that
the system generalises to deprecations the map has never heard of. **This tool's coverage
equals `deprecations.json`'s coverage: 16 symbols.**

**`citation_coverage` was genuinely earned — it failed first.** The initial run scored
0.800: a `moved` symbol has zero v1.0 mentions by definition, so searching for the old
name returned vector noise and citations landed on plausible-but-wrong pages. The fix
changed the *system* (query the replacement the way the v1.0 docs spell it), not the
dataset and not the metric.

**`clean_passthrough` and `flagged_not_rewritten` are earned here.** They were free for
the do-nothing baseline; a tool that actively rewrites has to decide *not* to touch these,
which is the harder behaviour.

**What no column measures: whether the rewritten code actually runs.** The metrics are
string- and AST-level. In practice the rewrite does more than they ask — replacing
`set_entry_point` also requires adding `START`/`END` to the imports, which it does, and
without which the "migrated" file would raise `NameError`. That secondary-edit competence
is real but **unmeasured**; an execution-based check (import the module, compile the
graph) is the honest next metric.
