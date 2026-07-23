"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  BarChart3,
  ChevronRight,
  GitCompare,
  Loader2,
  MessageSquare,
  Square,
} from "lucide-react";
import {
  API_URL,
  runMigrateStream,
  type Citation,
  type MigrationResult,
  type NodeEvent,
  type RetrievalTrace,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { AiMascot } from "@/components/ai-mascot";
import { AgentGraph, type GraphTopology } from "@/components/agent-graph";
import { RetrievalInspector } from "@/components/retrieval-inspector";
import { DiffView } from "@/components/diff-view";
import { cn } from "@/lib/utils";

// The S2.4 migration graph, as <AgentGraph> topology. detect/verify are
// deterministic AST code; research hits the corpora; rewrite is the one LLM
// call. Clean input ends after detect and flag-only input after research —
// so idle rewrite/verify pills are the graph telling the truth, not a stall.
const MIGRATE_TOPOLOGY: GraphTopology = {
  nodes: [
    { id: "__start__", label: "start" },
    { id: "detect", label: "detect" },
    { id: "research", label: "research" },
    { id: "rewrite", label: "rewrite" },
    { id: "verify", label: "verify" },
    { id: "__end__", label: "end" },
  ],
  edges: [
    ["__start__", "detect"],
    ["detect", "research"],
    ["research", "rewrite"],
    ["rewrite", "verify"],
    ["verify", "research"], // the bounded verify-driven retry
    ["verify", "__end__"],
  ],
};

// Real snippets from ai/eval/migration_dataset.json — one per behaviour, so
// the demo shows all three verdicts including "nothing to change".
const EXAMPLES: { label: string; hint: string; code: string }[] = [
  {
    label: "deprecated entry points",
    hint: "set_entry_point / set_finish_point → START/END edges (mig-003)",
    code: `import time

from typing_extensions import TypedDict
from langgraph.graph import StateGraph


class State(TypedDict):
    x: int
    result: int


def expensive_node(state: State) -> dict:
    time.sleep(2)
    return {"result": state["x"] * 2}


builder = StateGraph(State)
builder.add_node("expensive_node", expensive_node)
builder.set_entry_point("expensive_node")
builder.set_finish_point("expensive_node")
graph = builder.compile()
`,
  },
  {
    label: "unevidenced API",
    hint: "SqliteSaver — kept unchanged, flagged for review (mig-015)",
    code: `from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
graph = builder.compile(checkpointer=checkpointer)
`,
  },
  {
    label: "already v1.0",
    hint: "modern message-state idioms — nothing to change (mig-018)",
    code: `from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class State(MessagesState):
    documents: list[str]
`,
  },
];

type Run = {
  nodes: NodeEvent[];
  traces: RetrievalTrace[];
  citations: Citation[];
  summary: string; // deterministic backend summary — secondary to the diff
  result: MigrationResult | null;
};

const EMPTY_RUN: Run = { nodes: [], traces: [], citations: [], summary: "", result: null };

export default function MigrateClient() {
  const [code, setCode] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Pre-warm the API like /chat does (Render free tier cold starts).
  useEffect(() => {
    fetch(`${API_URL}/health`, { cache: "no-store" }).catch(() => {});
  }, []);

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

  async function migrate(input: string) {
    if (!input.trim() || loading) return;
    setError(null);
    setLoading(true);
    setRun({ ...EMPTY_RUN });
    const controller = new AbortController();
    abortRef.current = controller;
    const patch = (fn: (r: Run) => Run) => setRun((r) => (r ? fn(r) : r));
    try {
      await runMigrateStream(
        input,
        {
          onNode: (n) => patch((r) => ({ ...r, nodes: [...r.nodes, n] })),
          onRetrieval: (t) => patch((r) => ({ ...r, traces: [...r.traces, t] })),
          onToken: (d) => patch((r) => ({ ...r, summary: r.summary + d })),
          onCitations: (c) => patch((r) => ({ ...r, citations: c })),
          onResult: (res) => patch((r) => ({ ...r, result: res })),
        },
        controller.signal,
      );
    } catch (err) {
      // A user-initiated stop is not an error — keep whatever streamed.
      const aborted =
        controller.signal.aborted ||
        (err instanceof DOMException && err.name === "AbortError");
      if (!aborted) setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setLoading(false);
    }
  }

  return (
    <>
      {/* Same agentic backdrop as / and /chat — one system. */}
      <div className="aurora" aria-hidden>
        <span className="a1" />
        <span className="a2" />
        <span className="a3" />
      </div>
      <div className="agentic-grid" aria-hidden />

      <div className="mx-auto flex min-h-dvh max-w-6xl flex-col px-5">
        {/* Header */}
        <header className="flex items-start justify-between gap-4 pb-5 pt-7">
          <Link href="/" className="flex items-center gap-3">
            <AiMascot state={loading ? "thinking" : "idle"} className="size-11 flex-none" />
            <div>
              <h1 className="text-[17px] font-bold tracking-tight">
                Migration Workbench — LangGraph v0.x → v1.0
              </h1>
              <p className="text-xs text-muted-foreground">
                Paste legacy code · every change cites the pinned v1.0 docs
              </p>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            <Link
              href="/chat"
              className="inline-flex size-9 items-center justify-center rounded-md border bg-card text-muted-foreground shadow-sm transition-colors hover:text-foreground"
              aria-label="Chat"
              title="Chat"
            >
              <MessageSquare className="size-4" />
            </Link>
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

        {/* Two panes: input left, streamed run right; stacks on mobile. */}
        <main className="grid flex-1 items-start gap-5 pb-10 lg:grid-cols-2">
          {/* ── left: legacy code in ── */}
          <section aria-label="Legacy code input" className="glass flex flex-col rounded-2xl p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label htmlFor="legacy-code" className="text-[13px] font-semibold">
                Legacy Python
              </label>
              <span className="text-[11px] text-muted-foreground">
                covers the curated deprecations set, one file at a time
              </span>
            </div>

            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex.label}
                  type="button"
                  onClick={() => setCode(ex.code)}
                  title={ex.hint}
                  className={cn(
                    "rounded-full border bg-card px-3 py-1.5 text-[11.5px] text-muted-foreground shadow-sm transition-colors hover:border-input hover:text-foreground",
                    code === ex.code && "border-primary/50 bg-primary/10 text-primary",
                  )}
                >
                  {ex.label}
                </button>
              ))}
            </div>

            {/* A plain textarea on purpose (S2.5 scope): the interaction is
                paste → read a diff, not edit. A code editor is megabytes of
                dependency for zero demo value. */}
            <textarea
              id="legacy-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  migrate(code);
                }
              }}
              spellCheck={false}
              placeholder={"# Paste legacy LangGraph code, or pick an example above…\nbuilder.set_entry_point(\"my_node\")"}
              className="mt-3 min-h-[300px] flex-1 resize-y rounded-xl border bg-background/60 p-3.5 font-mono text-[12.5px] leading-relaxed outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-ring sm:min-h-[380px]"
            />

            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="text-[11px] text-muted-foreground/70">
                <kbd className="rounded border bg-card px-1.5 py-0.5 font-mono text-[10px]">Ctrl</kbd>+
                <kbd className="rounded border bg-card px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd> to run
              </p>
              {loading ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => abortRef.current?.abort()}
                  className="gap-2"
                >
                  <Square className="size-3.5 fill-current" /> Stop
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={() => migrate(code)}
                  disabled={!code.trim()}
                  className="gap-2 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/30 hover:opacity-90"
                >
                  <GitCompare className="size-4" /> Migrate
                </Button>
              )}
            </div>
          </section>

          {/* ── right: the run, streamed ── */}
          <section aria-label="Migration result" className="flex min-w-0 flex-col gap-3.5">
            {run === null ? (
              <Placeholder />
            ) : (
              <>
                <AgentGraph topology={MIGRATE_TOPOLOGY} events={run.nodes} />

                {/* Visible pipeline status; aria-live so the stage changes are
                    announced (the graph's own live region covers per-node
                    detail — this is the run-level headline). */}
                <p aria-live="polite" className="flex items-center gap-2 px-1 text-[12px] text-muted-foreground">
                  {loading ? (
                    <>
                      <Loader2 className="size-3.5 animate-spin text-primary" />
                      {slow
                        ? "Waking up the server — free tier, first request can take ~40s…"
                        : "Running the migration pipeline…"}
                    </>
                  ) : run.result ? (
                    <>Done — {verdictLabel(run.result)}</>
                  ) : run.summary ? (
                    <>Stopped before a result.</>
                  ) : null}
                </p>

                {error && (
                  <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
                    {error}
                  </p>
                )}

                {/* Input-guardrail message (not valid Python, too large, …):
                    the backend sends it as the summary token with no result. */}
                {!loading && !error && run.result === null && run.summary && (
                  <p className="rounded-xl border border-amber-500/40 bg-amber-500/[0.08] px-3.5 py-2.5 text-sm leading-relaxed text-foreground/85">
                    {run.summary}
                  </p>
                )}

                {run.result && <DiffView result={run.result} citations={run.citations} />}

                {run.citations.length > 0 && (
                  <ul className="flex flex-col gap-2 border-t border-dashed pt-3.5">
                    {run.citations.map((c) => (
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
                          <span className="min-w-0">
                            {c.page_title} — {c.heading}
                            {c.docs_version ? (
                              <span className="ml-1.5 rounded border bg-card px-1 py-px align-middle font-mono text-[9.5px] text-muted-foreground">
                                v{c.docs_version}
                              </span>
                            ) : null}
                          </span>
                          <ArrowUpRight className="ml-auto size-3.5 flex-none opacity-60" />
                        </a>
                      </li>
                    ))}
                  </ul>
                )}

                {run.traces.length > 0 && (
                  <details className="group rounded-xl border bg-card/50 px-3.5 py-2.5">
                    <summary className="flex cursor-pointer select-none list-none items-center gap-1.5 text-[12px] font-medium text-muted-foreground transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
                      <ChevronRight
                        className="size-3.5 flex-none transition-transform group-open:rotate-90"
                        aria-hidden
                      />
                      Show work
                      <span className="font-normal text-muted-foreground/60">
                        · {run.traces.length === 1
                          ? "1 retrieval call"
                          : `${run.traces.length} retrieval calls`}
                      </span>
                    </summary>
                    <RetrievalInspector
                      traces={run.traces}
                      citations={run.citations}
                      className="mt-3 border-t border-dashed pt-3"
                    />
                  </details>
                )}

                {/* The deterministic run summary — secondary to the diff by
                    design, so it sits last, quiet and monospaced. On the clean
                    path it would repeat the "already idiomatic" panel verbatim,
                    so it only renders when there was something to report. */}
                {run.result &&
                  run.summary &&
                  (run.result.changes.length > 0 || run.result.caveats.length > 0) && (
                  <p className="whitespace-pre-wrap border-t border-dashed px-1 pt-3 font-mono text-[11px] leading-relaxed text-muted-foreground/80">
                    {run.summary}
                  </p>
                )}
              </>
            )}
          </section>
        </main>
      </div>
    </>
  );
}

function verdictLabel(result: MigrationResult): string {
  if (result.diff) {
    const n = result.changes.length;
    return `${n} cited change${n === 1 ? "" : "s"}${result.caveats.length ? `, ${result.caveats.length} caveat${result.caveats.length === 1 ? "" : "s"}` : ""}.`;
  }
  if (result.caveats.length > 0) {
    return "kept unchanged — see the caveats.";
  }
  return "already idiomatic v1.0, no changes.";
}

// What the right pane shows before the first run: the pipeline, honestly.
function Placeholder() {
  const stages: { name: string; body: string }[] = [
    { name: "detect", body: "AST scan against a curated deprecations map — no LLM, no guessing." },
    { name: "research", body: "retrieves the v1.0 replacement from the pinned docs (hybrid search + trace)." },
    { name: "rewrite", body: "one LLM call, grounded in the retrieved passages — every change must cite them." },
    { name: "verify", body: "deterministic re-check: parses, deprecated symbols gone, flagged ones untouched." },
  ];
  return (
    <div className="glass flex flex-col gap-4 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="grid size-10 flex-none place-items-center rounded-xl bg-primary/10 text-primary">
          <GitCompare className="size-5" />
        </div>
        <div>
          <h2 className="text-[15px] font-semibold">Legacy in, cited diff out</h2>
          <p className="text-[12.5px] text-muted-foreground">
            The pipeline lights up here while it runs.
          </p>
        </div>
      </div>
      <ol className="flex flex-col gap-2.5">
        {stages.map((s, i) => (
          <li key={s.name} className="flex items-start gap-2.5 text-[13px] leading-relaxed">
            <span className="mt-0.5 grid size-5 flex-none place-items-center rounded-full border bg-card font-mono text-[10px] text-muted-foreground">
              {i + 1}
            </span>
            <span>
              <span className="font-mono text-[12px] font-semibold text-primary">{s.name}</span>{" "}
              <span className="text-muted-foreground">— {s.body}</span>
            </span>
          </li>
        ))}
      </ol>
      <p className="rounded-xl border border-dashed bg-muted/40 px-3.5 py-2.5 text-[12px] leading-relaxed text-muted-foreground">
        Honesty rules: already-idiomatic code comes back untouched, and APIs the
        pinned corpus can&apos;t evidence are flagged for review instead of being
        rewritten on faith.
      </p>
    </div>
  );
}
