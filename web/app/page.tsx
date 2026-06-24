import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  ChevronRight,
  Layers,
  ListChecks,
  Network,
  Search,
  ShieldCheck,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { HEADLINE, META, RETRIEVAL_COLS, RETRIEVAL_ROWS } from "@/lib/eval-data";
import { siteConfig } from "@/lib/site";

// Static landing page lives at "/" — the strongest route for SEO. Real text in the
// HTML at load time is what Google can index; the chat tool lives at /chat.
// Kept a server component on purpose: all motion is CSS-only (see globals.css),
// so nothing here needs "use client".

const HOW_IT_WORKS = [
  {
    step: "01",
    Icon: Search,
    title: "Hybrid retrieval",
    body: "pgvector semantic search fused with Postgres full-text keyword search by Reciprocal Rank Fusion — so it catches both meaning and exact API names.",
  },
  {
    step: "02",
    Icon: Layers,
    title: "Cross-encoder rerank",
    body: "A reranking pass reorders the top candidates for relevance before generation, lifting precision on every retrieval metric over the vector baseline.",
  },
  {
    step: "03",
    Icon: Network,
    title: "LangGraph agent",
    body: "An agent built with LangGraph picks its own tools — RAG search, a calculator, or topic listing — with guardrails on loops, tool errors, and prompt injection.",
  },
  {
    step: "04",
    Icon: BookOpen,
    title: "Grounded, with citations",
    body: "Every answer cites the exact LangGraph v1.0 doc section it came from, and says \"not found\" instead of hallucinating when the docs can't answer.",
  },
];

const FAQ = [
  {
    q: "What is this?",
    a: "An Agentic RAG assistant that answers questions about the LangGraph v1.0 documentation. It demonstrates retrieval engineering, evaluation, and agent orchestration — not just calling an LLM API.",
  },
  {
    q: "What is Agentic RAG?",
    a: "Retrieval-Augmented Generation (RAG) grounds an LLM's answers in retrieved documents. The agentic layer adds a LangGraph agent that decides which tools to use — searching the docs, doing math, or listing available topics — instead of always running a fixed pipeline.",
  },
  {
    q: "How does retrieval work?",
    a: "It uses hybrid search: pgvector semantic similarity plus Postgres full-text keyword matching, fused with Reciprocal Rank Fusion, then a cross-encoder reranking pass. This beats a pure-vector baseline on hit rate, MRR and precision.",
  },
  {
    q: "Which documentation does it cover?",
    a: "The official LangGraph v1.0 Python docs — conceptual guides, the API reference, and how-to guides — pinned to the stable v1.0 release so answers use current idioms.",
  },
  {
    q: "Does it hallucinate?",
    a: "Answers are grounded in retrieved chunks and include citations back to the source section. The system is evaluated against negative traps — questions the docs can't answer — and scores 1.000 on saying \"not found\" instead of inventing an API.",
  },
];

// FAQ structured data — eligible for Google's FAQ rich results.
const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQ.map((f) => ({
    "@type": "Question",
    name: f.q,
    acceptedAnswer: { "@type": "Answer", text: f.a },
  })),
};

// Reusable gradient text — indigo -> violet -> cyan, the "agent" accent palette.
const GRAD = "bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-500 bg-clip-text text-transparent";

// The hero's agent panel: a tool-routing graph + a live-looking reasoning trace.
// It's an illustration of how the LangGraph agent routes a query to a tool, not a
// real-time log — animated purely in CSS.
function AgentPanel() {
  return (
    <div className="relative">
      <div className="glass glow-primary rounded-3xl p-5">
        <div className="mb-3 flex items-center justify-between">
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
            agent.run()
          </span>
          <span className="flex gap-1.5">
            <span className="size-2.5 rounded-full bg-foreground/15" />
            <span className="size-2.5 rounded-full bg-foreground/15" />
            <span className="size-2.5 rounded-full bg-emerald-500/70" />
          </span>
        </div>

        {/* Tool-routing graph */}
        <svg viewBox="0 0 320 150" className="w-full" role="img" aria-label="Agent routing a query to the rag_search tool">
          <defs>
            <linearGradient id="edge" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="oklch(0.62 0.2 277)" />
              <stop offset="1" stopColor="oklch(0.72 0.13 200)" />
            </linearGradient>
          </defs>
          <path d="M58 75 H132" stroke="url(#edge)" strokeWidth="2" fill="none" className="flow-line" />
          <path d="M170 75 C200 75 200 30 244 30" stroke="url(#edge)" strokeWidth="2" fill="none" className="flow-line" />
          <path d="M170 75 H244" stroke="url(#edge)" strokeWidth="2.4" fill="none" className="flow-line" />
          <path d="M170 75 C200 75 200 120 244 120" stroke="url(#edge)" strokeWidth="2" fill="none" className="flow-line" />

          <g className="node-pulse">
            <circle cx="40" cy="75" r="16" fill="oklch(0.62 0.2 277 / 0.18)" stroke="oklch(0.62 0.2 277)" />
          </g>
          <text x="40" y="79" textAnchor="middle" fontSize="9" className="fill-foreground/70 font-mono">ask</text>

          <circle cx="151" cy="75" r="20" fill="oklch(0.72 0.13 200 / 0.16)" stroke="oklch(0.72 0.13 200)" strokeWidth="2" />
          <text x="151" y="73" textAnchor="middle" fontSize="9" className="fill-foreground font-mono">agent</text>
          <text x="151" y="84" textAnchor="middle" fontSize="8" className="fill-foreground/60 font-mono">router</text>

          <g>
            <rect x="244" y="18" width="68" height="24" rx="8" fill="oklch(0.6 0.02 280 / 0.08)" className="stroke-border" />
            <text x="278" y="33" textAnchor="middle" fontSize="8.5" className="fill-foreground/65 font-mono">calculator</text>
          </g>
          <g>
            <rect x="244" y="63" width="68" height="24" rx="8" fill="oklch(0.7 0.15 160 / 0.12)" stroke="oklch(0.7 0.15 160)" />
            <text x="278" y="78" textAnchor="middle" fontSize="8.5" className="fill-emerald-600 dark:fill-emerald-300 font-mono">rag_search ✓</text>
          </g>
          <g>
            <rect x="244" y="108" width="68" height="24" rx="8" fill="oklch(0.6 0.02 280 / 0.08)" className="stroke-border" />
            <text x="278" y="123" textAnchor="middle" fontSize="8" className="fill-foreground/65 font-mono">list_topics</text>
          </g>
        </svg>

        {/* Reasoning trace */}
        <div className="mt-4 space-y-1 rounded-2xl border bg-background/60 p-4 font-mono text-[12px] leading-relaxed">
          <p className="trace-line text-muted-foreground" style={{ animationDelay: "0.2s" }}>
            <span className="text-violet-500 dark:text-violet-300">▸ thought</span> query needs the docs, not math
          </p>
          <p className="trace-line text-muted-foreground" style={{ animationDelay: "0.9s" }}>
            <span className="text-cyan-600 dark:text-cyan-300">▸ tool</span> rag_search(&quot;add_edge START&quot;)
          </p>
          <p className="trace-line text-muted-foreground" style={{ animationDelay: "1.6s" }}>
            <span className="text-emerald-600 dark:text-emerald-300">▸ rerank</span> 24 → top 5 chunks
          </p>
          <p className="trace-line caret text-foreground/90" style={{ animationDelay: "2.3s" }}>
            <span className="text-emerald-600 dark:text-emerald-300">▸ answer</span> grounded · cites low_level.md §Edges
          </p>
        </div>
      </div>

      {/* Floating citation chip */}
      <div className="glass absolute -bottom-4 -left-4 hidden rounded-xl px-3 py-2 text-[11px] shadow-sm sm:block">
        <span className="text-muted-foreground">cited</span>
        <span className="ml-1 font-mono text-emerald-600 dark:text-emerald-300">
          concepts/low_level.md
        </span>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      {/* Agentic backdrop: blueprint grid + drifting aurora (CSS-only, theme-aware). */}
      <div className="aurora" aria-hidden>
        <span className="a1" />
        <span className="a2" />
        <span className="a3" />
      </div>
      <div className="agentic-grid" aria-hidden />

      <div className="mx-auto max-w-5xl px-5 pb-24">
        {/* Nav */}
        <header className="sticky top-3 z-50 mt-3">
          <div className="glass glow-primary flex items-center justify-between gap-4 rounded-2xl px-4 py-3">
            <div className="flex items-center gap-2.5">
              <div className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/30">
                <Network className="size-4.5" />
              </div>
              <span className="text-[15px] font-bold tracking-tight">{siteConfig.shortName}</span>
              <span className="ml-1 hidden rounded-full border bg-card px-2 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline">
                LangGraph v1.0
              </span>
            </div>
            <nav className="flex items-center gap-2">
              <Link
                href="#how"
                className="hidden rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline-flex"
              >
                How it works
              </Link>
              <Link
                href="/eval"
                className="hidden items-center gap-1.5 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline-flex"
              >
                <BarChart3 className="size-4" /> Eval
              </Link>
              <Link
                href="/chat"
                className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition-opacity hover:opacity-90"
              >
                Open app <ArrowRight className="size-4" />
              </Link>
              <ThemeToggle />
            </nav>
          </div>
        </header>

        {/* Hero */}
        <section className="grid gap-12 pt-16 sm:pt-24 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-500 opacity-70" />
                <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
              </span>
              Built <span className="text-foreground/80">with</span> LangGraph · answers{" "}
              <span className="text-foreground/80">about</span> LangGraph
            </span>
            <h1 className="mt-6 text-balance text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
              The agent that
              <br />
              <span className={GRAD}>reasons over the docs</span>
            </h1>
            <p className="mt-6 max-w-xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
              Ask anything about LangGraph v1.0. A tool-using agent does hybrid retrieval,
              cross-encoder reranking, then answers{" "}
              <span className="text-foreground/85">grounded in citations</span> — or says{" "}
              <span className="font-mono text-emerald-600 dark:text-emerald-300">&quot;not found&quot;</span>{" "}
              instead of hallucinating.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition-opacity hover:opacity-90"
              >
                Try the assistant <ArrowRight className="size-4" />
              </Link>
              <Link
                href="/eval"
                className="glass inline-flex items-center gap-2 rounded-xl px-6 py-3.5 text-sm font-semibold shadow-sm transition-colors hover:border-input"
              >
                <BarChart3 className="size-4" /> See the eval results
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <span className="size-1.5 rounded-full bg-violet-500" /> pgvector + RRF hybrid
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="size-1.5 rounded-full bg-cyan-500" /> Cohere rerank
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="size-1.5 rounded-full bg-emerald-500" /> Eval-first
              </span>
            </div>
          </div>

          <AgentPanel />
        </section>

        {/* Headline stats */}
        <section className="mt-20 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {HEADLINE.map((s) => (
            <div key={s.label} className="glass rounded-2xl p-4">
              <div className={`text-2xl font-extrabold ${GRAD}`}>{s.value}</div>
              <div className="mt-1 text-[12.5px] font-medium">{s.label}</div>
              <div className="text-[11px] text-muted-foreground">{s.sub}</div>
            </div>
          ))}
        </section>

        {/* How it works */}
        <section id="how" className="mt-28 scroll-mt-24">
          <div className="text-center">
            <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
              the pipeline
            </span>
            <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
              From question to <span className={GRAD}>grounded answer</span>
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Four layers, each measured against a baseline before it earned its place.
            </p>
          </div>
          <div className="mt-12 grid gap-4 sm:grid-cols-2">
            {HOW_IT_WORKS.map(({ step, Icon, title, body }) => (
              <div key={title} className="glass rounded-2xl p-6">
                <div className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <span className="font-mono text-[11px] text-cyan-600 dark:text-cyan-300">{step}</span>
                  <h3 className="text-base font-semibold">{title}</h3>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Eval results */}
        <section id="eval" className="mt-28 scroll-mt-24">
          <div className="flex flex-col items-center text-center">
            <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
              <ListChecks className="size-3.5" /> Eval-first, not eval-last
            </span>
            <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
              Real numbers, <span className={GRAD}>not a demo</span>
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Retrieval configs compared on a golden dataset. Hybrid + cross-encoder rerank
              wins on every metric over the vector baseline.
            </p>
          </div>
          <div className="glass mt-10 overflow-x-auto rounded-2xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                  {RETRIEVAL_COLS.map((c) => (
                    <th key={c} className="px-3 py-3 font-medium first:pl-4">
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
                        ? "border-b bg-emerald-500/[0.06] last:border-0"
                        : "border-b last:border-0"
                    }
                  >
                    <td className="px-3 py-3 font-medium first:pl-4">
                      {r.config}
                      {r.best && (
                        <span className="ml-2 rounded-md border border-emerald-500/35 bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-300">
                          best
                        </span>
                      )}
                    </td>
                    {r.values.map((v, i) => (
                      <td
                        key={i}
                        className={
                          r.best
                            ? "px-3 py-3 font-medium text-emerald-700 dark:text-emerald-300"
                            : "px-3 py-3 text-muted-foreground"
                        }
                      >
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mx-auto mt-4 max-w-3xl text-center text-xs leading-relaxed text-muted-foreground">
            {META}
          </p>
          <div className="mt-6 text-center">
            <Link
              href="/eval"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary transition-opacity hover:opacity-80"
            >
              Full eval dashboard <ArrowRight className="size-4" />
            </Link>
          </div>
        </section>

        {/* FAQ */}
        <section className="mt-28">
          <h2 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">
            Frequently asked questions
          </h2>
          <div className="glass mx-auto mt-10 max-w-2xl divide-y rounded-2xl px-6">
            {FAQ.map((f, i) => (
              <details key={f.q} className="group py-5" open={i === 0}>
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-semibold">
                  {f.q}
                  <ChevronRight className="size-4 flex-none text-muted-foreground transition-transform group-open:rotate-90" />
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Bottom CTA */}
        <section className="glass glow-primary relative mt-28 overflow-hidden rounded-3xl p-10 text-center">
          <div
            className="pointer-events-none absolute inset-0 opacity-70"
            style={{
              background:
                "radial-gradient(600px 200px at 50% 0%, color-mix(in oklch, var(--primary) 22%, transparent), transparent 70%)",
            }}
            aria-hidden
          />
          <div className="relative">
            <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/30">
              <ShieldCheck className="size-6" />
            </div>
            <h2 className="mt-5 text-2xl font-bold tracking-tight sm:text-3xl">
              Ask it anything about LangGraph
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Grounded answers with citations, or let the agent pick its own tools.
            </p>
            <Link
              href="/chat"
              className="mt-7 inline-flex items-center gap-2 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 px-7 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition-opacity hover:opacity-90"
            >
              Open the assistant <ArrowRight className="size-4" />
            </Link>
          </div>
        </section>

        {/* Footer */}
        <footer className="mt-20 flex flex-col items-center gap-2 border-t pt-8 text-center text-xs text-muted-foreground">
          <p>{siteConfig.name} — a demo of retrieval engineering, evaluation, and agent orchestration.</p>
          <nav className="flex gap-4">
            <Link href="/chat" className="transition-colors hover:text-foreground">Chat</Link>
            <Link href="/eval" className="transition-colors hover:text-foreground">Eval</Link>
          </nav>
        </footer>
      </div>
    </>
  );
}
