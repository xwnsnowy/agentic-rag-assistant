import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  HEADLINE,
  META,
  RAGAS,
  RETRIEVAL_COLS,
  RETRIEVAL_ROWS,
} from "@/lib/eval-data";

export const metadata = {
  // title template in layout appends " — Agentic RAG" automatically.
  title: "Eval",
  description: "Retrieval, generation, agent and safety metrics for the Agentic RAG system.",
  alternates: { canonical: "/eval" },
  openGraph: {
    title: "Eval — Agentic RAG",
    description: "Retrieval, generation, agent and safety metrics for the Agentic RAG system.",
    url: "/eval",
  },
};

export default function EvalPage() {
  return (
    <div className="mx-auto max-w-3xl px-5 pb-20">
      <header className="flex items-center justify-between gap-4 py-7">
        <Link
          href="/chat"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> back to chat
        </Link>
        <ThemeToggle />
      </header>

      <h1 className="text-2xl font-bold tracking-tight">Evaluation</h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        This system is built eval-first. Below are real numbers — not a demo. {META}
      </p>

      {/* Headline stats */}
      <div className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {HEADLINE.map((s) => (
          <div key={s.label} className="rounded-2xl border bg-card p-4 shadow-sm">
            <div className="bg-gradient-to-br from-indigo-500 to-violet-500 bg-clip-text text-2xl font-bold text-transparent">
              {s.value}
            </div>
            <div className="mt-1 text-[12.5px] font-medium">{s.label}</div>
            <div className="text-[11px] text-muted-foreground">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Retrieval comparison */}
      <h2 className="mt-10 text-lg font-semibold">Retrieval — config comparison</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Hybrid + cross-encoder rerank wins on every metric over the vector baseline.
      </p>
      <div className="mt-4 overflow-x-auto rounded-2xl border bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-[12px] text-muted-foreground">
              {RETRIEVAL_COLS.map((c) => (
                <th key={c} className="px-3 py-2.5 font-medium first:pl-4">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {RETRIEVAL_ROWS.map((r) => (
              <tr
                key={r.config}
                className={
                  r.best
                    ? "border-b bg-primary/5 last:border-0"
                    : "border-b last:border-0"
                }
              >
                <td className="px-3 py-2.5 pl-4 font-medium">
                  {r.config}
                  {r.best && (
                    <span className="ml-2 rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                      best
                    </span>
                  )}
                </td>
                {r.values.map((v, i) => (
                  <td
                    key={i}
                    className={`px-3 py-2.5 tabular-nums ${r.best ? "font-semibold text-foreground" : "text-muted-foreground"}`}
                  >
                    {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Ragas */}
      <h2 className="mt-10 text-lg font-semibold">Generation — Ragas (real library)</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Independent scoring with the actual Ragas library on the production config.
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {RAGAS.map((m) => (
          <div key={m.label} className="rounded-2xl border bg-card p-4 shadow-sm">
            <div className="text-xl font-bold tabular-nums">{m.value.toFixed(3)}</div>
            <div className="mt-1 text-[12px] text-muted-foreground">{m.label}</div>
          </div>
        ))}
      </div>

      <p className="mt-10 text-xs text-muted-foreground">
        Reproduce:{" "}
        <code className="rounded border bg-muted px-1.5 py-0.5 font-mono text-[11px]">
          python -m scripts.run_eval --judge
        </code>{" "}
        · methodology in the repo&apos;s{" "}
        <span className="font-mono">ai/eval/README.md</span>.
      </p>
    </div>
  );
}
