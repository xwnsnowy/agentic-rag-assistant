# Migration eval — raw-LLM baseline (gpt-4o-mini, no retrieval, no tools)

**S2.3 control condition.** One bare chat call per snippet — no retrieval, no
tools, no pinned docs. The model gets the same output channels the S2.4 agent
will have (unchanged-is-ok, a changes list, a caveats list); what it cannot
have is grounding, so `citation_coverage` is 0 by construction — with no docs
there is nothing real to cite, and asking it to invent slugs would manufacture
fake grounding.

Across all 20 items the bare model reported **0 changes** and
**0 caveats**. Note that `clean_passthrough` and `flagged_not_rewritten`
must be read jointly with `deprecated_removed`: a model that never changes
anything aces the clean items for free while failing every migration — the
clean score is only meaningful once the modernize columns are non-zero.

Reproduce: `python -m scripts.run_migration_eval --mode baseline` (from `ai/`).

- items: 20 (modernize 10 / flag 6 / clean 4)
- parses: **1.000**
- deprecated_removed (modernize): **0.000**
- idiom_present (modernize): **0.000**
- citation_coverage (modernize): **0.000**
- clean_passthrough (clean): **1.000**
- flagged_not_rewritten (flag): **0.000**

| id | kind | parses | removed | idiom | cites | passthrough | flagged | changes | caveats |
|---|---|---|---|---|---|---|---|---|---|
| mig-001 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-002 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-003 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-004 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-005 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-006 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-007 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-008 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-009 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-010 | modernize | ✓ | ✗ | ✗ | 0.00 | — | — | 0 | 0 |
| mig-011 | flag | ✓ | — | — | — | — | ✗ | 0 | 0 |
| mig-012 | flag | ✓ | — | — | — | — | ✗ | 0 | 0 |
| mig-013 | flag | ✓ | — | — | — | — | ✗ | 0 | 0 |
| mig-014 | flag | ✓ | — | — | — | — | ✗ | 0 | 0 |
| mig-015 | flag | ✓ | — | — | — | — | ✗ | 0 | 0 |
| mig-016 | flag | ✓ | — | — | — | — | ✗ | 0 | 0 |
| mig-017 | clean | ✓ | — | — | — | ✓ | — | 0 | 0 |
| mig-018 | clean | ✓ | — | — | — | ✓ | — | 0 | 0 |
| mig-019 | clean | ✓ | — | — | — | ✓ | — | 0 | 0 |
| mig-020 | clean | ✓ | — | — | — | ✓ | — | 0 | 0 |
