"use client";

import { useState } from "react";
import { ask, type Citation } from "@/lib/api";

type Turn = {
  question: string;
  config: string;
  answer: string | null;
  citations: Citation[];
};

const CONFIGS = ["hybrid+rerank", "hybrid", "baseline", "keyword"];

export default function Home() {
  const [input, setInput] = useState("");
  const [config, setConfig] = useState(CONFIGS[0]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setError(null);
    setLoading(true);
    try {
      const res = await ask(q, config);
      setTurns((t) => [
        { question: q, config: res.config, answer: res.answer, citations: res.citations },
        ...t,
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-dvh bg-zinc-50 dark:bg-black">
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-10">
        <header className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Agentic RAG — LangGraph docs
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Ask about LangGraph v1.0. Answers are grounded in the docs with citations.
          </p>
        </header>

        <form onSubmit={onSubmit} className="flex flex-col gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) onSubmit(e);
            }}
            rows={2}
            placeholder="e.g. How do I add short-term memory with a checkpointer?"
            className="w-full resize-none rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-black outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
          />
          <div className="flex items-center justify-between gap-2">
            <label className="flex items-center gap-2 text-xs text-zinc-500">
              retrieval
              <select
                value={config}
                onChange={(e) => setConfig(e.target.value)}
                className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
              >
                {CONFIGS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-white dark:text-black"
            >
              {loading ? "Thinking…" : "Ask"}
            </button>
          </div>
        </form>

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">
            {error}
          </p>
        )}

        <section className="flex flex-col gap-5">
          {turns.map((t, i) => (
            <article
              key={i}
              className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <p className="mb-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
                {t.question}
                <span className="ml-2 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-normal text-zinc-500 dark:bg-zinc-900">
                  {t.config}
                </span>
              </p>
              <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-700 dark:text-zinc-300">
                {t.answer ?? "(no answer)"}
              </p>
              {t.citations.length > 0 && (
                <ul className="mt-3 space-y-1 border-t border-zinc-100 pt-3 dark:border-zinc-800">
                  {t.citations.map((c) => (
                    <li key={c.n} className="text-xs text-zinc-500">
                      <a
                        href={c.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline dark:text-blue-400"
                      >
                        [{c.n}] {c.page_title} — {c.heading}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
