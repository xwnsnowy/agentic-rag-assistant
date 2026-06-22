"use client";

import { useState } from "react";
import {
  ArrowUpRight,
  BookOpen,
  Calculator,
  FolderTree,
  Network,
  Send,
} from "lucide-react";
import { ask, runAgent, type Citation } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
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
  const [error, setError] = useState<string | null>(null);

  async function send(q: string) {
    if (!q.trim() || loading) return;
    setInput("");
    setError(null);
    setLoading(true);
    try {
      if (mode === "agent") {
        const res = await runAgent(q);
        setTurns((t) => [
          { question: q, label: "agent", answer: res.answer, citations: [], toolsUsed: res.tools_used },
          ...t,
        ]);
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
          <span className="text-xs text-muted-foreground/70">
            {loading ? "choosing tools…" : "agent decides which tools to use"}
          </span>
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
                <div className="prose-answer whitespace-pre-wrap rounded-2xl border bg-card p-4 text-[14.5px] leading-relaxed shadow-sm">
                  {t.answer ?? "(no answer)"}
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
