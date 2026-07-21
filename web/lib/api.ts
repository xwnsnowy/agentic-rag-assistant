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

// Streaming variant of runAgent: reads the SSE body with a stream reader (no
// Vercel AI SDK needed — the backend is FastAPI) and fires handlers per event.
export async function runAgentStream(
  question: string,
  threadId: string | undefined,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/agent/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, thread_id: threadId }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  // Frame re-assembly lives in lib/sse.ts (unit-tested; a frame may span
  // reads). This loop only decodes bytes and dispatches parsed events.
  // Unknown event types are deliberately ignored — that additivity is what
  // lets backend and frontend deploy in either order.
  const parser = createSseParser((payload) => {
    let ev: { type: string; v?: unknown; thread_id?: string; tools_used?: string[] };
    try {
      ev = JSON.parse(payload);
    } catch {
      return;
    }
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
  });

  for (;;) {
    // An abort fired mid-stream rejects this read() with an AbortError —
    // that's the mechanism "New chat" / the stop button use to cancel.
    const { done, value } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true }));
  }
}
