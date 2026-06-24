import type { Metadata } from "next";
import ChatApp from "./chat-client";

export const metadata: Metadata = {
  title: "Chat",
  description:
    "Ask the Agentic RAG assistant about LangGraph v1.0 — grounded answers with citations, plus an agent that picks its own tools.",
  alternates: { canonical: "/chat" },
  openGraph: {
    title: "Chat — Agentic RAG",
    description:
      "Ask the Agentic RAG assistant about LangGraph v1.0 — grounded answers with citations.",
    url: "/chat",
  },
};

export default function ChatPage() {
  return <ChatApp />;
}
