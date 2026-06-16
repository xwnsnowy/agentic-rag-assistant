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
