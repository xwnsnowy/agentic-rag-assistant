"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Calculator,
  FolderTree,
  Loader2,
  Network,
  Plus,
  Send,
} from "lucide-react";
import { API_URL, ask, runAgentStream, type Citation } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { Markdown } from "@/components/markdown";
import { cn } from "@/lib/utils";

type Mode = "agent" | "rag";

type Turn = {
  question: string;
  label: string;
  answer: string | null;
  citations: Citation[];
  toolsUsed: string[];
};

const CONFIGS = ["hybrid+rerank", "hybrid", "baseline", "keyword"];

const TOOL_META: Record<string, { label: string; Icon: typeof BookOpen }> = {
  rag_search: { label: "rag_search", Icon: BookOpen },
  calculator: { label: "calculator", Icon: Calculator },
  list_doc_topics: { label: "list_doc_topics", Icon: FolderTree },
};

const SUGGESTIONS = [
  "What is a StateGraph in LangGraph?",
  "How do I add short-term memory with a checkpointer?",
  "What is a checkpointer, and what is 12 × 9?",
  "What topics can you answer about?",
];

export default function Home() {
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode>("agent");
  const [config, setConfig] = useState(CONFIGS[0]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  // While the agent is streaming, `loading` stays true (locks the composer) but
  // `thinking` flips false once the first token/tool arrives, so we swap the
  // "thinking…" bubble for the answer that's now growing in place.
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string>("");
  const [slow, setSlow] = useState(false);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Pre-warm the API on load so the first question isn't stuck behind a ~40s
  // cold start (Render free tier spins down when idle).
  useEffect(() => {
    fetch(`${API_URL}/health`, { cache: "no-store" }).catch(() => {});
  }, []);

  // After a few seconds of waiting, hint that the free-tier server may be waking up.
  useEffect(() => {
    if (loading) {
      slowTimer.current = setTimeout(() => setSlow(true), 4500);
    } else {
      setSlow(false);
      if (slowTimer.current) clearTimeout(slowTimer.current);
    }
    return () => {
      if (slowTimer.current) clearTimeout(slowTimer.current);
    };
  }, [loading]);

  function newChat() {
    setThreadId(typeof crypto !== "undefined" ? crypto.randomUUID() : String(Date.now()));
    setTurns([]);
    setError(null);
  }

  async function send(q: string) {
    if (!q.trim() || loading) return;
    setInput("");
    setError(null);
    setLoading(true);
    setThinking(true);
    try {
      if (mode === "agent") {
        const tid = threadId || (typeof crypto !== "undefined" ? crypto.randomUUID() : String(Date.now()));
        // Create the (empty) answer turn lazily on the first event, then grow it
        // in place. The streaming turn is always index 0 (composer is locked).
        let created = false;
        const ensureTurn = () => {
          if (created) return;
          created = true;
          setThinking(false);
          setTurns((t) => [
            { question: q, label: "agent", answer: "", citations: [], toolsUsed: [] },
            ...t,
          ]);
        };
        const patchTop = (fn: (top: Turn) => Turn) =>
          setTurns((t) => (t.length ? [fn(t[0]), ...t.slice(1)] : t));

        await runAgentStream(q, tid, {
          onTools: (tools) => {
            ensureTurn();
            patchTop((top) => ({ ...top, toolsUsed: tools }));
          },
          onToken: (delta) => {
            ensureTurn();
            patchTop((top) => ({ ...top, answer: (top.answer ?? "") + delta }));
          },
          onDone: ({ thread_id }) => {
            ensureTurn();
            setThreadId(thread_id || tid);
          },
        });
      } else {
        const res = await ask(q, config);
        setTurns((t) => [
          { question: q, label: res.config, answer: res.answer, citations: res.citations, toolsUsed: [] },
          ...t,
        ]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setThinking(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-5">
      {/* Header */}
      <header className="flex items-start justify-between gap-4 pb-4 pt-7">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/30">
            <Network className="size-5" />
          </div>
          <div>
            <h1 className="text-[17px] font-bold tracking-tight">
              Agentic RAG — LangGraph docs
            </h1>
            <p className="text-xs text-muted-foreground">
              Grounded answers with citations · the agent picks its tools
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full border bg-card px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground shadow-sm sm:inline-flex">
            <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" />
            live
          </span>
          <Link
            href="/eval"
            className="inline-flex size-9 items-center justify-center rounded-md border bg-card text-muted-foreground shadow-sm transition-colors hover:text-foreground"
            aria-label="Eval dashboard"
            title="Eval dashboard"
          >
            <BarChart3 className="size-4" />
          </Link>
          <ThemeToggle />
        </div>
      </header>

      {/* Toolbar */}
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex gap-1 rounded-xl border bg-card p-1 shadow-sm">
          {(["agent", "rag"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "rounded-lg px-4 py-1.5 text-[13px] font-medium transition-colors",
                mode === m
                  ? "bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {m === "agent" ? "Agent" : "RAG"}
            </button>
          ))}
        </div>
        {mode === "rag" ? (
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            retrieval
            <select
              value={config}
              onChange={(e) => setConfig(e.target.value)}
              className="rounded-lg border bg-card px-2 py-1.5 text-xs shadow-sm outline-none"
            >
              {CONFIGS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div className="flex items-center gap-2.5">
            <span className="hidden text-xs text-muted-foreground/70 sm:inline">
              {loading ? "choosing tools…" : "remembers context across turns"}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={newChat}
              disabled={turns.length === 0 && !threadId}
              className="gap-1.5"
            >
              <Plus className="size-3.5" />
              New chat
            </Button>
          </div>
        )}
      </div>

      {/* Chat */}
      <main className="flex flex-1 flex-col gap-6 pb-6">
        {turns.length === 0 && !loading && (
          <div className="my-auto space-y-5 py-10 text-center">
            <h2 className="text-base font-semibold">Ask about LangGraph v1.0</h2>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border bg-card px-3.5 py-2 text-[12.5px] text-muted-foreground shadow-sm transition-colors hover:border-input hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
            {error}
          </p>
        )}

        {loading && thinking && (
          <div className="flex items-start gap-3">
            <div className="grid size-7 flex-none place-items-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow shadow-indigo-500/30">
              <Network className="size-3.5" />
            </div>
            <div className="flex items-center gap-2.5 rounded-2xl border bg-card px-4 py-3 shadow-sm">
              <Loader2 className="size-4 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">
                {slow
                  ? "Waking up the server — free tier, first request can take ~40s…"
                  : mode === "agent"
                    ? "Agent is thinking…"
                    : "Searching the docs…"}
              </span>
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <article key={i} className="flex flex-col gap-3">
            {/* question */}
            <div className="flex items-start gap-3">
              <div className="grid size-7 flex-none place-items-center rounded-lg border bg-card text-[12px] font-semibold text-muted-foreground shadow-sm">
                T
              </div>
              <p className="pt-1 text-[15px] font-semibold leading-snug">
                {t.question}
                <span className="ml-2 rounded-md border bg-card px-1.5 py-0.5 align-middle text-[10px] font-medium text-muted-foreground">
                  {t.label}
                </span>
              </p>
            </div>
            {/* answer */}
            <div className="flex items-start gap-3">
              <div className="grid size-7 flex-none place-items-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow shadow-indigo-500/30">
                <Network className="size-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                {t.toolsUsed.length > 0 && (
                  <div className="mb-2.5 flex flex-wrap gap-1.5">
                    {dedupeTools(t.toolsUsed).map((tool, j) => {
                      const meta = TOOL_META[tool] ?? { label: tool, Icon: BookOpen };
                      const Icon = meta.Icon;
                      return (
                        <span
                          key={j}
                          className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[11.5px] font-semibold text-primary"
                        >
                          <Icon className="size-3" />
                          {meta.label}
                        </span>
                      );
                    })}
                  </div>
                )}
                <div className="rounded-2xl border bg-card p-4 shadow-sm">
                  {t.answer ? <Markdown>{t.answer}</Markdown> : i === 0 && loading ? null : "(no answer)"}
                  {i === 0 && loading && !thinking && (
                    <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-primary align-text-bottom" />
                  )}
                </div>
                {t.citations.length > 0 && (
                  <ul className="mt-3.5 flex flex-col gap-2 border-t border-dashed pt-3.5">
                    {t.citations.map((c) => (
                      <li key={c.n}>
                        <a
                          href={c.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-start gap-2 text-[12.5px] text-muted-foreground transition-colors hover:text-foreground"
                        >
                          <span className="font-mono text-[11px] font-semibold text-primary">
                            [{c.n}]
                          </span>
                          <span>
                            {c.page_title} — {c.heading}
                          </span>
                          <ArrowUpRight className="ml-auto size-3.5 flex-none opacity-60" />
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </article>
        ))}
      </main>

      {/* Composer */}
      <div className="sticky bottom-0 bg-gradient-to-b from-transparent to-background to-30% pb-6 pt-3.5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex items-end gap-2.5 rounded-2xl border bg-card py-2 pl-4 pr-2 shadow-xl"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            rows={1}
            placeholder="Ask about LangGraph… (e.g. How do reducers work?)"
            className="max-h-32 flex-1 resize-none bg-transparent py-2.5 text-[14.5px] outline-none placeholder:text-muted-foreground/70"
          />
          <Button
            type="submit"
            size="icon"
            disabled={loading || !input.trim()}
            className="rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/30 hover:opacity-90"
          >
            <Send className="size-4" />
          </Button>
        </form>
        <p className="mt-2.5 text-center text-[11px] text-muted-foreground/70">
          <kbd className="rounded border bg-card px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd> to send ·{" "}
          <kbd className="rounded border bg-card px-1.5 py-0.5 font-mono text-[10px]">Shift</kbd>+
          <kbd className="rounded border bg-card px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd> newline
        </p>
      </div>
    </div>
  );
}

// The agent may call the same tool across multiple rounds — show each tool once.
function dedupeTools(tools: string[]): string[] {
  return [...new Set(tools)];
}
