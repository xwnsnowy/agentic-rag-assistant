/**
 * Central site metadata used by SEO (canonical URLs, sitemap, robots, OG tags).
 *
 * `siteUrl` resolves in this order:
 *  1. NEXT_PUBLIC_SITE_URL — set this to the real domain in prod (no trailing slash).
 *  2. VERCEL_PROJECT_PRODUCTION_URL — Vercel injects the stable production domain.
 *  3. VERCEL_URL — the per-deployment preview domain.
 *  4. http://localhost:3000 — local dev fallback.
 *
 * Never hardcode the host (per CLAUDE.md deploy rules) — read it from env.
 */
function resolveSiteUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL;
  if (explicit) return explicit.replace(/\/$/, "");

  const vercelProd = process.env.VERCEL_PROJECT_PRODUCTION_URL;
  if (vercelProd) return `https://${vercelProd}`;

  const vercelUrl = process.env.VERCEL_URL;
  if (vercelUrl) return `https://${vercelUrl}`;

  return "http://localhost:3000";
}

export const siteConfig = {
  name: "Agentic RAG Assistant",
  shortName: "Agentic RAG",
  title: "Agentic RAG — LangGraph docs",
  description:
    "Ask about LangGraph v1.0 — grounded answers with citations, and an agent that picks its tools. A demo of retrieval engineering, evaluation, and agent orchestration.",
  url: resolveSiteUrl(),
  locale: "en_US",
  keywords: [
    "Agentic RAG",
    "LangGraph",
    "RAG",
    "retrieval augmented generation",
    "LLM agent",
    "pgvector",
    "hybrid search",
    "reranking",
    "AI engineering",
  ],
} as const;
