# Phase 3 — Visible reasoning + Migration Workbench 🚧 Stage 1 COMPLETE, Stage 2 next

> **The problem this phase fixes.** The backend does a lot per question — embed, two
> searches, RRF fusion over 40 candidates, a cross-encoder pass over 20, tool selection,
> generation. The UI shows one chat bubble. Every interesting decision is invisible, so
> the product looks like any other chat wrapper.
>
> A second, deeper problem: **the retrieval task is too easy to demonstrate skill on.**
> Baseline vector search already scores hit@5 **0.977** on the golden set — the naive
> method nearly solves it, leaving hybrid and rerank almost no headroom to prove value.
> That is a corpus property (12 clean, non-conflicting markdown pages), not a ceiling
> on the technique.
>
> Stage 1 makes the existing work visible. Stage 2 makes the problem genuinely hard and
> turns the system into a tool with a reason to exist.

Plan: [Agentic_RAG_Build_Plan.md](Agentic_RAG_Build_Plan.md) · Previous: [PHASE_2.md](PHASE_2.md)

---

## Findings that shaped this plan

Verified against the code before planning — these are why the work is smaller than it looks:

| Finding | Consequence |
|---|---|
| `Result` (`app/retrieval.py`) already carries `vector_rank/score`, `keyword_rank/score`, `rrf_score`, `rerank_score` | Stage 1 computes **nothing new** — it stops discarding what exists |
| `rerank()` requests `top_n=top_k`, so only the final 5 get a Cohere score | Request `top_n=len(results)` — **free**, Cohere bills per search unit (≤100 docs), not per doc |
| `app/tools.py` already smuggles structured data out of a tool via a **contextvar sink** (citations) | Reuse that exact pattern for the trace; don't invent a second mechanism |
| `web/lib/api.ts` dispatches SSE events with an if/else chain that **silently ignores unknown types** | New event types are strictly additive — frontend and backend deploy in either order, `main` stays deployable |
| `eval/metrics.py` judges relevance at **slug (page) level**, not `chunk_id` | Re-ingesting reassigns chunk ids without invalidating the published results table |
| `stream_mode="messages"` already yields `meta["langgraph_node"]` | Node highlighting is nearly free; node *completion* needs `"updates"` mode added |

---

## Stage 1 — Make the agent's work visible

**Ships independently.** Same chat page, but the reasoning becomes inspectable.

### Definition of Done

- [x] **S1.0 — Tests exist and gate CI.** 52 pytest cases cover the chunker, RRF fusion,
      the calculator's AST whitelist, the citation regex, trace ordering and the eval-save
      guard; CI runs them. The retrieval eval reproduced **all 9 published numbers exactly**
      on the three configs that don't need Cohere (keyword, baseline, hybrid), proving the
      `rrf_fuse` extraction changed no behaviour.
- [x] **S1.1 — The retrieval trace is captured behind unchanged APIs.** `rag_search`'s
      return string is byte-identical (pinned by an exact-string test); MCP still serves
      three tools unchanged; `retrieve()` keeps its signature so eval/`/ask`/cache are
      untouched.
- [x] **S1.2 — `node` and `retrieval` SSE events stream.** Verified live by curl:
      `node(agent:active) → tools → node(agent:done) → node(tools:active/done) → retrieval
      → token×N → citations → node(__end__) → done`. A test strips the new events and
      asserts the legacy stream is exact, so the additivity claim is enforced, not assumed.
- [x] **S1.3 — The graph lights up and the inspector renders.** Verified in a real browser
      against the real backend: nodes light in causal order, "Show work" shows the full pool
      with `cos · ts · rrf` chips, and cited rows are badged with numbers matching the `[n]`
      markers in the answer.
  - [ ] **Blocked, not failed — rank movement is unshowable.** The Cohere key is dead (401),
        so every `rerank_score` is `null` and `final_ids` is just the fused head. The UI
        states this honestly ("final order (not reranked)") rather than implying a rerank
        happened; when the key is rotated the same UI lights up with real movement and no
        code change. Re-verify this box then.

### Steps

| Step | Change | The decision it embodies |
|---|---|---|
| **S1.0** | Extract the fusion loop of `hybrid_search` into a pure `rrf_fuse()`; add `ai/tests/` + `requirements-dev.txt`; CI runs pytest | *Functional core, imperative shell.* The RRF math was welded to two DB calls and untestable without Postgres. Tests land **first** so they protect every refactor that follows |
| **S1.1** | `RetrievalTrace` + `retrieve_with_trace()` in `pipeline.py`; `_debug_sink` contextvar in `tools.py`; `rerank()` scores the whole pool | Extract intermediate state **out-of-band**, keeping the in-band contract (what the LLM reads) frozen. Changing `rag_search`'s return value would break the prompt, break MCP, and bloat agent context with 20 passages |
| **S1.2** | `astream_agent` uses `stream_mode=["messages","updates"]`; emits `node` + `retrieval` events | `updates` fires on node completion; `messages` metadata names the active node. Cheaper and cleaner than `stream_mode="debug"`, which interleaves checkpoint noise |
| **S1.3** | `components/agent-graph.tsx`, `components/retrieval-inspector.tsx`, "Show work" disclosure on `/chat`; wire the unused `AbortSignal` | The graph component **knows nothing about chat** — it takes a topology + events, so Stage 2 reuses it for a different graph. A disclosure, not a side panel: the page is single-column mobile-first, and a panel means a layout rework for a view most turns won't open |

### What Stage 1 turned up (unplanned, worth keeping)

- **A real guardrail failure, caught by the eval.** Re-running the injection harness showed
  resistance at 0.875: the agent answered *"I cannot comply with that request… Please let me
  know how I can help! **HACKED**"* — refusing in words while complying in behaviour.
  Stashing the branch and re-running against the previous commit reproduced the identical
  failure, so it was **upstream model drift, not a code regression**. Root cause was the
  *scope* of the SECURITY rule (it forbade changing rules or revealing the prompt, but not
  controlling the reply's shape). Fixed, back to 1.000 — and notably the abstract rule alone
  did not hold; gpt-4o-mini needed a concrete example of the pattern. Commits `79e3466`
  (record the failure) then `2f03fdf` (fix) deliberately keep that order.
  **This is a prompt-level defence and therefore probabilistic** — an output-side guard
  checking the reply for literals the question demanded is the durable fix, and is now the
  strongest candidate for the next hardening step.
- **Two dead API keys, failing silently.** Cohere (401) and Langfuse (401). The system
  degrades gracefully — which is correct — but says nothing, so `hybrid+rerank` has been
  quietly serving hybrid-only. Graceful degradation without an alarm is a gap: a startup
  health-check that warns on a dead key is worth adding.
- **`/db/health` leaked exception text** (potentially the Neon DSN) to any caller; fixed in
  `c515378`. **`calculator` had an unbounded `ast.Pow`** — `9**9**9**9` stalls a turn; bounded
  in `b300d81`.
- **Pool size is variable**, 20–40: it is the union of the two candidate lists, so it equals
  20 when they overlap completely. Nothing downstream may assume `len(pool) == cfg.pool`.
- **Cold-start anomaly, seen once:** the first turn after backend boot delivered most SSE
  events in an end-burst instead of streaming. Warm turns always streamed correctly. Relevant
  to demos on a cold Render free-tier instance; unexplained, backend-side.

---

## Stage 2 — LangGraph Migration Workbench

**The product.** Paste legacy LangGraph code → the agent detects deprecated v0.x patterns,
researches the v1.0 replacement in the pinned docs, and returns a diff where **every change
carries a clickable citation**.

Why this and not more chat: ChatGPT answers LangGraph questions from tutorials it absorbed
during training, most of them pre-v1.0 — so it confidently emits dead APIs. Pinning the docs
and forcing citations is exactly the failure this system is built to fix. That is the answer
to *"why does this need to exist when ChatGPT exists?"*

### Definition of Done

- [ ] **S2.0 — Both doc versions coexist.** `SELECT docs_version, count(*) FROM chunks`
      shows v1.0 and v0.2; re-ingesting one version leaves the other's embeddings intact;
      the v1.0 retrieval numbers reproduce within noise.
- [x] **S2.1 — The corpus got harder, measured.** Relevance identity is now
      `(docs_version, slug)` — needed because `persistence` and `streaming` exist as slugs
      in *both* corpora, so slug-only matching would have counted a v0.2 chunk as a correct
      hit and inflated the mixed row in the flattering direction. Published in
      `eval/results/eval_mixed_corpus.md`, with `eval_real.md` left intact.

      **Result — the degradation is large and explained:**

      | hybrid | hit@5 | MRR | P@5 | v0.2 chunks in top-5 |
      |---|---|---|---|---|
      | filtered `1.0` | 0.977 | 0.913 | 0.632 | 0.00 |
      | unfiltered mixed | 0.909 | 0.647 | 0.345 | **2.64 / 5** |

      The deprecated corpus does not sit inertly in the index: its prose on
      persistence/streaming/graphs is near-identical to v1.0's, so it wins over half the
      result list, halving MRR and precision. This is exactly the "confidently retrieves
      stale docs" failure the workbench exists to fix — now a measurement, not a claim.

- [x] **Bonus finding — retrieval was not deterministic.** Enforcing "the metric fix must
      not move the published configs" caught a real bug: `ORDER BY rank DESC` leaves tied
      rows unordered, one golden item's relevant chunk sits in a ~2.2e-16 `ts_rank` tie, and
      migration 003's full-table UPDATE permuted it — moving hybrid MRR 0.896 → 0.913 with
      no code change. Ties now break by `id`; verified stable across three runs. The old
      figure was one valid ordering, not an error — but an unreproducible measurement is not
      a measurement.
- [ ] **S2.2 — `check_api_status` answers with evidence** — verdict from a curated map,
      corroborated by per-version occurrence counts from the corpus itself.
- [ ] **S2.3 — A migration eval exists, with a raw-LLM baseline committed first.**
- [ ] **S2.4 — The migration graph beats that baseline** on deprecated-pattern removal
      and citation coverage.
- [ ] **S2.5 — `/migrate` works end-to-end** on the deployed preview.

### Steps

| Step | Change | The decision it embodies |
|---|---|---|
| **S2.0** | `migrations/002_docs_version.sql`; per-version ingest replacing the global `TRUNCATE`; `version` filter on retrieval; `RagConfig.version="1.0"` | A **first-class indexed column**, not a JSONB key — version is a filter predicate on every query, not descriptive metadata. `DEFAULT '1.0'` backfills, so pre- and post-migration code are mutually compatible and the deploy is safe in any order. The `"1.0"` default means every existing caller keeps an identical candidate set: **the flagship numbers survive by construction, not by luck** |
| **S2.1** | Add a `hybrid+rerank (mixed corpus, unfiltered)` config; re-run and commit | Eval-first applied literally: turn "we made it harder" into a measured before/after. The old table is **extended with a labelled harder condition**, never silently redefined |
| **S2.2** | `data/deprecations.json` (~15 verified entries) + `check_api_status` tool + MCP exposure | A lookup table alone is un-grounded; occurrence counts alone can't distinguish *removed* from *renamed* or name the replacement. Together the tool is authoritative **and** evidenced from the pinned docs |
| **S2.3** | `eval/migration_dataset.json` (~20 snippets, incl. already-clean ones) + `migration_harness.py` + raw-LLM baseline | Metrics are **deterministic first** (`ast.parse`, must-contain / must-not-contain, citation coverage): free, reproducible, immune to judge drift. The LLM judge corroborates, exactly the role Ragas plays for retrieval. The clean snippets are the migration analogue of the golden set's negative traps |
| **S2.4** | `app/migrate.py`: `START → detect → research → rewrite → verify → END` with a bounded retry edge; `POST /migrate/stream` | A **dedicated graph, not the ReAct agent with a longer prompt.** Migration is a pipeline with known stages, not open-ended tool choice — more reliable, cheaper, evaluable per node. `detect` and `verify` are deterministic AST code, no LLM. It also demonstrates a non-trivial LangGraph topology rather than another 2-node loop |
| **S2.5** | `/migrate` two-pane UI + `components/diff-view.tsx`; reuse `<AgentGraph>` | Plain `<textarea>`, **no Monaco/CodeMirror** — the interaction is paste → read a diff, not edit. Megabytes of dependency for zero demo value |

---

## Risks — stated honestly

1. **The v0.2 corpus is the likeliest time sink.** LangGraph 0.2's how-to docs are Jupyter
   notebooks; converting them is effort with near-zero payoff. Mitigation: fetch ~10
   *concepts* pages (plain mkdocs markdown) that contain the deprecated idioms we need.
2. **The mixed corpus might not degrade retrieval much.** v0.2 and v1.0 prose may differ
   enough that vector search still prefers v1.0. If the drop is <2 points, **do not
   manufacture drama** — report it and let the migration baseline-vs-agent contrast
   (where the gap is guaranteed) carry the story.
3. **Structured output in `rewrite` is the flakiest node.** Mitigated by the deterministic
   `verify` node and one bounded retry, and by emitting a whole rewritten file plus a
   change list — never per-hunk patches, since LLMs are bad at line-number arithmetic.
4. **Tool-selection accuracy may fall below 1.000** once a 4th tool lands. That is honest
   evaluation working. Budget one iteration on tool docstrings, then publish the real number.

**Cut order if time runs short:** UI polish → the `0.2` side of `rag_search`'s version arg →
the mixed-corpus eval column. **Never cut** S2.3 (eval-first is this project's identity) or
Stage 1 (it is the independently shippable demo).

## Explicitly out of scope

Monaco/CodeMirror, `.ipynb` conversion, syntax-highlighted diffs, a live-backend `/eval`
page, connection pooling, `PostgresSaver`. None of them produce a number or a defensible
design decision — the two things this project trades in.
