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

export type AgentStreamHandlers = {
  onTools?: (tools: string[]) => void;
  onToken?: (delta: string) => void;
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
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line; a frame may span reads.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const payload = dataLine.slice(5).trim();
      if (!payload) continue;
      let ev: { type: string; v?: unknown; thread_id?: string; tools_used?: string[] };
      try {
        ev = JSON.parse(payload);
      } catch {
        continue;
      }
      if (ev.type === "token") handlers.onToken?.(String(ev.v ?? ""));
      else if (ev.type === "tools") handlers.onTools?.((ev.v as string[]) ?? []);
      else if (ev.type === "done")
        handlers.onDone?.({
          thread_id: ev.thread_id ?? "",
          tools_used: ev.tools_used ?? [],
        });
    }
  }
}
