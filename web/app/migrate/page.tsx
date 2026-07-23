import type { Metadata } from "next";
import MigrateClient from "./migrate-client";

export const metadata: Metadata = {
  title: "Migration Workbench",
  description:
    "Paste legacy LangGraph v0.x code and get a v1.0 migration diff where every change cites the pinned docs — or an honest 'no changes' / 'needs review' verdict.",
  alternates: { canonical: "/migrate" },
  openGraph: {
    title: "Migration Workbench — Agentic RAG",
    description:
      "Legacy LangGraph in, cited v1.0 diff out. Deterministic detection, doc-grounded rewriting.",
    url: "/migrate",
  },
};

export default function MigratePage() {
  return <MigrateClient />;
}
