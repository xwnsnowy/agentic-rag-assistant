import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
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

const HOW_IT_WORKS = [
  {
    Icon: Search,
    title: "Hybrid retrieval",
    body: "Combines pgvector semantic search with Postgres full-text keyword search, fused by Reciprocal Rank Fusion — so it catches both meaning and exact terms.",
  },
  {
    Icon: Layers,
    title: "Cross-encoder rerank",
    body: "A reranking pass reorders the top candidates for relevance before generation, lifting precision on every retrieval metric over the vector baseline.",
  },
  {
    Icon: Network,
    title: "LangGraph agent",
    body: "An agent built with LangGraph picks its own tools — RAG search, a calculator, or topic listing — with guardrails on loops, tool errors, and prompt injection.",
  },
  {
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

export default function LandingPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <div className="mx-auto max-w-4xl px-5 pb-24">
        {/* Nav */}
        <header className="flex items-center justify-between gap-4 py-7">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/30">
              <Network className="size-4.5" />
            </div>
            <span className="text-[15px] font-bold tracking-tight">{siteConfig.shortName}</span>
          </div>
          <nav className="flex items-center gap-2">
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
        </header>

        {/* Hero */}
        <section className="py-14 text-center sm:py-20">
          <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
            <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" />
            Built with LangGraph · answers about LangGraph
          </span>
          <h1 className="mx-auto mt-6 max-w-3xl text-balance text-4xl font-bold tracking-tight sm:text-5xl">
            Agentic RAG assistant for the{" "}
            <span className="bg-gradient-to-br from-indigo-500 to-violet-500 bg-clip-text text-transparent">
              LangGraph documentation
            </span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
            Ask questions about LangGraph v1.0 and get grounded answers with citations.
            Hybrid retrieval, cross-encoder reranking, and a tool-using agent — built
            eval-first, with real numbers to back every design choice.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition-opacity hover:opacity-90"
            >
              Try the assistant <ArrowRight className="size-4" />
            </Link>
            <Link
              href="/eval"
              className="inline-flex items-center gap-2 rounded-xl border bg-card px-6 py-3 text-sm font-semibold shadow-sm transition-colors hover:border-input"
            >
              <BarChart3 className="size-4" /> See the eval results
            </Link>
          </div>
        </section>

        {/* Headline stats */}
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {HEADLINE.map((s) => (
            <div key={s.label} className="rounded-2xl border bg-card p-4 shadow-sm">
              <div className="bg-gradient-to-br from-indigo-500 to-violet-500 bg-clip-text text-2xl font-bold text-transparent">
                {s.value}
              </div>
              <div className="mt-1 text-[12.5px] font-medium">{s.label}</div>
              <div className="text-[11px] text-muted-foreground">{s.sub}</div>
            </div>
          ))}
        </section>

        {/* How it works */}
        <section className="mt-24">
          <h2 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">
            How it works
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-sm leading-relaxed text-muted-foreground">
            Four layers turn a question into a grounded, cited answer.
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {HOW_IT_WORKS.map(({ Icon, title, body }) => (
              <div key={title} className="rounded-2xl border bg-card p-6 shadow-sm">
                <div className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </div>
                <h3 className="mt-4 text-base font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Eval results */}
        <section className="mt-24">
          <div className="flex flex-col items-center text-center">
            <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
              <ListChecks className="size-3.5" /> Eval-first, not eval-last
            </span>
            <h2 className="mt-5 text-2xl font-bold tracking-tight sm:text-3xl">
              Real numbers, not a demo
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Retrieval configs compared on a golden dataset. Hybrid + cross-encoder rerank
              wins on every metric over the vector baseline.
            </p>
          </div>
          <div className="mt-8 overflow-x-auto rounded-2xl border bg-card shadow-sm">
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
                    <td className="px-3 py-2.5 font-medium first:pl-4">
                      {r.config}
                      {r.best && (
                        <span className="ml-2 rounded-md bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                          best
                        </span>
                      )}
                    </td>
                    {r.values.map((v, i) => (
                      <td key={i} className="px-3 py-2.5 text-muted-foreground">
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-center text-xs leading-relaxed text-muted-foreground">{META}</p>
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
        <section className="mt-24">
          <h2 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">
            Frequently asked questions
          </h2>
          <div className="mx-auto mt-10 max-w-2xl divide-y rounded-2xl border bg-card px-6 shadow-sm">
            {FAQ.map((f) => (
              <details key={f.q} className="group py-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-semibold">
                  {f.q}
                  <ArrowRight className="size-4 flex-none text-muted-foreground transition-transform group-open:rotate-90" />
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Bottom CTA */}
        <section className="mt-24 rounded-3xl border bg-gradient-to-br from-indigo-500/10 to-violet-500/10 p-10 text-center shadow-sm">
          <ShieldCheck className="mx-auto size-8 text-primary" />
          <h2 className="mt-4 text-2xl font-bold tracking-tight">Ask it anything about LangGraph</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
            Grounded answers with citations, or let the agent pick its own tools.
          </p>
          <Link
            href="/chat"
            className="mt-7 inline-flex items-center gap-2 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition-opacity hover:opacity-90"
          >
            Open the assistant <ArrowRight className="size-4" />
          </Link>
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
