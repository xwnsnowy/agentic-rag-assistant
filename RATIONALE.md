# Design rationale & FAQ

Why this system is built the way it is — and honest answers to the questions a
careful reader will ask.

## Q: How is this different from just asking ChatGPT? ChatGPT can answer about LangGraph too.

The sharpest question, and the honest answer has two layers.

**The technical differences (RAG vs a plain LLM):**

| | ChatGPT (LLM only) | This system (RAG) |
|---|---|---|
| Source of the answer | Training memory (can be stale or hallucinated) | Retrieves the **actual pinned v1.0 docs**, answers only from them |
| Citations | None / fabricated | **Every answer cites** the source chunk — auditable |
| Versioning | Mixes old/new (may suggest the deprecated `set_entry_point()`) | **Pinned to v1.0** → current idioms (`add_edge(START, ...)`) |
| "I don't know" | Tends to answer confidently anyway | **Abstains** on out-of-scope questions (neg-handling 1.000) |
| Measurability | Black box for your domain | **Numbers**: MRR 0.93, faithfulness 0.92, etc. |
| Control | Can't change it | You own the corpus, chunking, prompts, guardrails |

Concrete example this project surfaced: the eval found a version drift — v1.0 uses
`create_agent` (from `langchain`), not the older `create_react_agent`. A memory-based
answer gets this wrong; a doc-grounded, version-pinned system gets it right.

**The honest layer:** for **public, well-known** docs like LangGraph, a frontier model
*will* answer reasonably well — it has seen LangGraph. So as a *product over public docs*,
the edge over ChatGPT is limited, and pretending otherwise is a red flag.

**Where the real value is:** this project isn't "beat ChatGPT at LangGraph Q&A". It's a
**demonstration of the engineering skills** — retrieval engineering, evaluation, agent
orchestration, guardrails — that apply to the real use case ChatGPT *can't* serve:
**private / internal / proprietary data the model never saw and that you must build and
measure yourself** (company docs, internal codebases, contracts). LangGraph docs are just
a convenient, **publicly verifiable** corpus to demonstrate the techniques — the same
pipeline runs unchanged on private data.

> One-liner: *"For public docs a big model is competitive. RAG's value is grounding,
> citations, knowing-when-it-doesn't-know, version pinning, and being measurable — and
> those skills transfer to private data, where ChatGPT isn't an option. The docs are just
> a verifiable demo corpus; the engineering is the point."*

## Q: Why hybrid search + reranking instead of just vector search?

- **Hybrid (vector + keyword via Reciprocal Rank Fusion):** dense retrieval misses exact
  terms (API names, error strings); keyword misses paraphrases. RRF fuses both by rank
  position, so the two score scales don't need calibrating.
- **Rerank (cross-encoder):** first-stage retrieval is a cheap bi-encoder; a reranker
  scores (query, passage) jointly — more accurate but too slow for the whole corpus. So:
  retrieve a wide pool cheaply, rerank it, keep top-k. The eval shows it wins on every
  metric (MRR 0.90 → 0.93), at ~2× latency — a real precision/latency tradeoff.

## Q: What does "eval-first" actually buy you?

It catches problems a demo hides. This project's eval found, then fixed:
1. **Dataset language mismatch** (VN questions vs EN corpus) breaking lexical retrieval.
2. **Version drift** in a ground-truth answer (create_react_agent → create_agent).
3. **Weak handling of trap questions** (the system over-answered) — diagnosed two causes
   (lenient prompt + a mis-framed metric) and fixed it to neg-handling 1.000.

> *"I can tell when the system gets worse — I don't just build it to run."*

## Q: Is the agent just one API call?

No. It's a **LangGraph state machine** (agent ⇄ tools loop) that picks among `rag_search`,
`calculator`, `list_doc_topics` (tool-selection accuracy 0.917), with **guardrails**: max
tool rounds, tool-error recovery, input validation, and prompt-injection resistance
(measured 1.000 over 8 attacks). It also has **multi-turn memory** via a LangGraph
checkpointer — built with the very mechanism the docs describe.

## Q: Why LangGraph and not LlamaIndex (or LangChain alone)?

They solve different layers, and I picked per layer rather than adopting one framework
end-to-end:

- **Retrieval layer:** I wrote it directly (chunking, pgvector + full-text, RRF, rerank)
  instead of `LlamaIndex`. LlamaIndex is excellent for *getting a RAG pipeline standing
  fast*, but the whole point here was to **engineer and measure** each retrieval stage — a
  high-level index abstraction would hide exactly the parts I wanted to own and eval.
- **Agent layer:** `LangGraph` over plain LangChain because I needed an explicit **state
  machine with guardrails** (max tool rounds, conditional routing, a checkpointer for
  multi-turn memory). LangChain's higher-level agents hide the control flow; LangGraph
  exposes the graph, which is the thing being demonstrated.
- So: LlamaIndex is a valid alternative for the retrieval half and I can speak to the
  trade-off — I chose hand-built + LangGraph because *measurability and explicit control*
  were the goals, not time-to-first-demo.

## Q: You expose the tools over MCP too — why?

The agent's three tools (`rag_search`, `calculator`, `list_doc_topics`) are also published
as an **MCP (Model Context Protocol) server** (`app.mcp_server`). One tool implementation,
two front doors: the internal LangGraph agent *and* any external MCP client (Claude
Desktop, IDEs, other agents). The MCP handlers forward to the *same* LangChain tools, so
the two surfaces can't drift. It's a small amount of code because the capability already
existed — MCP is just the standard wrapper that makes it reusable outside this app.

## Q: Why pgvector (Postgres) instead of a dedicated vector DB (Pinecone/Weaviate/Qdrant)?

- **One source of truth.** Vectors, metadata (`jsonb`), and the keyword index
  (`tsvector`) live in the **same database** as the relational data (documents, chat
  logs). No sync pipeline between two systems, no consistency drift, one connection.
- **Hybrid search needs both halves together.** Fusing pgvector similarity with Postgres
  full-text is one query in one DB — not a cross-system join.
- **It's enough.** HNSW indexing scales well past this corpus; a specialised vector DB
  adds infra, cost, and a sync job you only need at very large scale.
- Honest: at massive scale (billions of vectors, heavy metadata filtering) a dedicated
  engine may win. For app-sized RAG, Postgres+pgvector is simpler and sufficient — *don't
  add a system you don't need yet.*

## Q: Why chunk by heading/section instead of fixed-size?

- **Semantic units, not arbitrary cuts.** A heading + its content is one coherent idea.
  Fixed-size splitting cuts mid-sentence — broken context hurts both retrieval and the
  answer.
- **Never split a code block.** The corpus is code-heavy; half a snippet teaches nothing.
  Heading-based chunking keeps the heading and its code together (with a size cap that
  packs whole blocks, never splitting fenced code).
- **Citations fall out for free.** Page title, section breadcrumb, source URL, and anchor
  attach per section → precise, linkable citations.
- Tradeoff: variable chunk sizes. Worth it vs. the cost of broken context.

## Q: Why pin the corpus to LangGraph v1.0 (tag 1.0.10)?

AI libraries move fast and a plausible answer can be wrong for your version. Pinning makes
answers **reproducible and verifiable** against a fixed reference, and makes eval
**comparable over time** (same tag → same corpus). It's also how the eval caught a
version-drift bug in a ground-truth answer.

## Q: Why two languages (TypeScript + Python)?

A deliberate production split: **TS/Next.js for the app** (UI, auth, chat history),
**Python for the AI/eval layer** — because the ecosystem (LangGraph, Ragas, embeddings)
lives in Python. It mirrors how real teams are organised; forcing the AI layer into TS
would fight the tooling.

## Q: Why gpt-4o-mini, not a frontier model?

That's the point of RAG: **retrieval supplies the facts, so a small model answers
accurately when grounded** — faithfulness 0.92 with gpt-4o-mini proves it, at cents for
the whole eval. The lever is good retrieval + citations, not model size. Swapping in a
bigger model is a one-line config change if a task ever needs it.

## Q: Why both a custom LLM-judge AND Ragas for evaluation?

Retrieval metrics (hit@k / MRR / precision) are deterministic from labels. But "is this
answer grounded and relevant?" needs judgment → **LLM-as-judge**. **Ragas** is the standard
library for the same metrics, so running both **corroborates** the numbers (independent
check) and using the recognised tool is a credibility signal — they agreed closely on
faithfulness and context-precision.

## Q: What are the limitations? (don't dodge this)

- **Cohere trial key expired** → the live demo's rerank degrades to hybrid (the eval table
  was produced while the key was valid; degradation is graceful, no 500).
- **Semantic cache + multi-turn memory are in-process** (MemorySaver) — fine for one
  instance; Redis / `PostgresSaver` are the production swaps.
- **Corpus is 12 pages / 244 chunks**, dataset is 50 items — enough to prove the method,
  not a full knowledge base.
- **Render free tier cold-starts** (~60s first request), mitigated by a keep-warm cron.

Knowing these is the point — a system you can't critique is one you don't understand.
