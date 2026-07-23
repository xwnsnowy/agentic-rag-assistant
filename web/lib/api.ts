import { createSseParser } from "@/lib/sse";

// Single source of truth for the AI service base URL.
// Never hardcode localhost/ports — read from env (deploy-aware).
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type HealthResult =
  | { ok: true; data: unknown }
  | { ok: false; error: string };

// Server-side fetch helper for the FastAPI health endpoints.
export async function getHealth(path = "/health"): Promise<HealthResult> {
  try {
    const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    return { ok: true, data: await res.json() };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export type Citation = {
  n: number;
  chunk_id: number;
  page_title: string;
  heading: string;
  source_url: string;
  // Additive (S2.5): present on /migrate citations (and newer /agent streams);
  // older payloads simply omit them, so both stay optional.
  slug?: string | null;
  docs_version?: string | null;
};

export type AskResponse = {
  question: string;
  config: string;
  answer: string | null;
  citations: Citation[];
};

export async function ask(
  question: string,
  config: string,
): Promise<AskResponse> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, config }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export type AgentResponse = {
  question: string;
  answer: string;
  tools_used: string[];
  rounds: number;
  thread_id: string;
  citations: Citation[];
};

export async function runAgent(
  question: string,
  threadId?: string,
): Promise<AgentResponse> {
  const res = await fetch(`${API_URL}/agent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, thread_id: threadId }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── S1.2 stream event payloads (mirror ai/app/agent.py + pipeline.py) ────────

// {"type":"node","v":{...}} — lifecycle of a LangGraph node this turn.
// "active" is deduped per turn by the backend (a second agent round emits no
// new active), and "done" can repeat — consumers must fold these tolerantly.
export type NodeEvent = {
  name: string; // "agent" | "tools" | "__end__" for the chat agent graph
  status: "active" | "done";
};

// One fused-pool candidate from a rag_search call. Ranks/scores are null when
// that side didn't surface the chunk (e.g. keyword-only hit has no
// vector_rank); rerank_score is null when the reranker didn't score it —
// either it sat past the rerank window, or reranking was unavailable.
export type PoolEntry = {
  chunk_id: number;
  page_title: string | null;
  heading: string | null;
  source_url: string | null;
  vector_rank: number | null;
  vector_score: number | null;
  keyword_rank: number | null;
  keyword_score: number | null;
  rrf_score: number | null;
  rerank_score: number | null;
  // Additive (S2.5): which corpus the chunk belongs to. Load-bearing on the
  // /migrate flag path, which retrieves from the v0.2 docs by design — without
  // the tag those trace rows would read as a retrieval bug.
  slug?: string | null;
  docs_version?: string | null;
};

// {"type":"retrieval","v":{...}} — one per rag_search call in the turn.
export type RetrievalTrace = {
  tool_call_query: string; // the query string the agent passed to the tool
  citation_ns: number[]; // the [n] markers this call's passages received
  query: string;
  rewritten_query: string | null; // set iff the LLM rewrite step ran
  pool: PoolEntry[]; // PRE-truncation fused candidates, in hybrid (RRF) order
  final_ids: number[]; // chunk_ids in post-rerank order (len == k)
  timings_ms: { retrieve: number; rerank: number | null }; // null = didn't run
};

export type AgentStreamHandlers = {
  onTools?: (tools: string[]) => void;
  onToken?: (delta: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onNode?: (node: NodeEvent) => void;
  onRetrieval?: (trace: RetrievalTrace) => void;
  onDone?: (info: { thread_id: string; tools_used: string[] }) => void;
};

// One JSON event off either SSE stream. Extra top-level fields (thread_id,
// tools_used on the agent's `done`) ride along untyped.
type SseEvent = {
  type: string;
  v?: unknown;
  thread_id?: string;
  tools_used?: string[];
};

// Shared POST-and-stream plumbing for /agent/stream and /migrate/stream: one
// fetch, one reader loop, one frame parser (lib/sse.ts — unit-tested; a frame
// may span reads). Each caller only supplies its own event dispatch, so there
// is exactly one SSE reader in the codebase.
async function postSseStream(
  path: string,
  body: unknown,
  onEvent: (ev: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser((payload) => {
    let ev: SseEvent;
    try {
      ev = JSON.parse(payload);
    } catch {
      return;
    }
    onEvent(ev);
  });

  for (;;) {
    // An abort fired mid-stream rejects this read() with an AbortError —
    // that's the mechanism the stop buttons / "New chat" use to cancel.
    const { done, value } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true }));
  }
}

// Streaming variant of runAgent: reads the SSE body with a stream reader (no
// Vercel AI SDK needed — the backend is FastAPI) and fires handlers per event.
// Unknown event types are deliberately ignored — that additivity is what
// lets backend and frontend deploy in either order.
export async function runAgentStream(
  question: string,
  threadId: string | undefined,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  await postSseStream(
    "/agent/stream",
    { question, thread_id: threadId },
    (ev) => {
      if (ev.type === "token") handlers.onToken?.(String(ev.v ?? ""));
      else if (ev.type === "tools") handlers.onTools?.((ev.v as string[]) ?? []);
      else if (ev.type === "citations") handlers.onCitations?.((ev.v as Citation[]) ?? []);
      else if (ev.type === "node") {
        const v = ev.v as NodeEvent | undefined;
        if (v?.name && v.status) handlers.onNode?.(v);
      } else if (ev.type === "retrieval") {
        const v = ev.v as RetrievalTrace | undefined;
        if (v) handlers.onRetrieval?.(v);
      } else if (ev.type === "done")
        handlers.onDone?.({
          thread_id: ev.thread_id ?? "",
          tools_used: ev.tools_used ?? [],
        });
    },
    signal,
  );
}

// ── S2.5 migration workbench (mirror ai/app/migrate.py) ─────────────────────

// One reported change in the rewrite; `citations` are [n] markers into the
// citations list the same stream delivered.
export type Change = {
  description: string;
  citations: number[];
  citation_slugs?: string[];
};

// A caveat is a plain sentence (deterministic, backend-built). On the flag
// path it names the unevidenced symbol — it IS the product on that path.
export type Caveat = string;

// The `result` event of /migrate/stream: `diff` is a server-side unified diff
// (stdlib difflib), empty when nothing changed; `rewritten` === `original` on
// the clean and flag paths.
export type MigrationResult = {
  original: string;
  rewritten: string;
  changes: Change[];
  caveats: Caveat[];
  diff: string;
};

export type MigrateStreamHandlers = {
  onToken?: (delta: string) => void; // deterministic summary (or an input error)
  onCitations?: (citations: Citation[]) => void;
  onNode?: (node: NodeEvent) => void;
  onRetrieval?: (trace: RetrievalTrace) => void;
  onResult?: (result: MigrationResult) => void;
  onDone?: () => void;
};

// Streaming client for POST /migrate/stream. Same event vocabulary as the
// agent stream (node | retrieval | token | citations | done) plus one
// `result` event carrying the diff — dispatched over the same shared reader.
export async function runMigrateStream(
  code: string,
  handlers: MigrateStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  await postSseStream(
    "/migrate/stream",
    { code },
    (ev) => {
      if (ev.type === "token") handlers.onToken?.(String(ev.v ?? ""));
      else if (ev.type === "citations") handlers.onCitations?.((ev.v as Citation[]) ?? []);
      else if (ev.type === "node") {
        const v = ev.v as NodeEvent | undefined;
        if (v?.name && v.status) handlers.onNode?.(v);
      } else if (ev.type === "retrieval") {
        const v = ev.v as RetrievalTrace | undefined;
        if (v) handlers.onRetrieval?.(v);
      } else if (ev.type === "result") {
        const v = ev.v as MigrationResult | undefined;
        if (v) handlers.onResult?.(v);
      } else if (ev.type === "done") handlers.onDone?.();
    },
    signal,
  );
}
