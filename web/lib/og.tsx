import { ImageResponse } from "next/og";
import { siteConfig } from "@/lib/site";

// Standard Open Graph / Twitter card dimensions.
export const OG_SIZE = { width: 1200, height: 630 } as const;
export const OG_CONTENT_TYPE = "image/png";

// Shared renderer for the social preview image. Used by both opengraph-image
// and twitter-image so they stay identical. Note: next/og (Satori) only
// understands inline styles + flexbox — no Tailwind classes here.
export function renderOgImage(): ImageResponse {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px",
          background: "#0b0a13",
          backgroundImage:
            "radial-gradient(900px 500px at 85% -10%, rgba(139,92,246,0.35), transparent 60%), radial-gradient(700px 420px at -5% 110%, rgba(99,102,241,0.28), transparent 55%)",
          color: "#fafafa",
          fontFamily: "sans-serif",
        }}
      >
        {/* Top row: logo mark + badge */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
            <div
              style={{
                display: "flex",
                width: "72px",
                height: "72px",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "20px",
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                fontSize: "32px",
                fontWeight: 800,
                color: "#ffffff",
              }}
            >
              AR
            </div>
            <span style={{ fontSize: "30px", fontWeight: 700, letterSpacing: "-0.02em" }}>
              {siteConfig.shortName}
            </span>
          </div>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              borderRadius: "999px",
              border: "1px solid rgba(255,255,255,0.18)",
              padding: "12px 22px",
              fontSize: "22px",
              color: "#c4b5fd",
            }}
          >
            Built with LangGraph · about LangGraph
          </span>
        </div>

        {/* Title block */}
        <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
          <div style={{ display: "flex", flexDirection: "column", fontSize: "76px", fontWeight: 800, lineHeight: 1.05, letterSpacing: "-0.03em" }}>
            <span>Agentic RAG assistant for the</span>
            <span
              style={{
                backgroundImage: "linear-gradient(135deg, #818cf8, #c084fc)",
                backgroundClip: "text",
                WebkitBackgroundClip: "text",
                color: "transparent",
              }}
            >
              LangGraph documentation
            </span>
          </div>
          <span style={{ fontSize: "30px", color: "#a1a1aa", maxWidth: "900px", lineHeight: 1.4 }}>
            Grounded answers with citations · hybrid retrieval + rerank · a tool-using agent.
          </span>
        </div>

        {/* Bottom row: metric chips */}
        <div style={{ display: "flex", gap: "16px" }}>
          {[
            "hit@5 1.00",
            "tool accuracy 0.917",
            "0 injection leaks",
            "eval-first",
          ].map((chip) => (
            <span
              key={chip}
              style={{
                display: "flex",
                alignItems: "center",
                borderRadius: "14px",
                background: "rgba(255,255,255,0.07)",
                border: "1px solid rgba(255,255,255,0.12)",
                padding: "14px 24px",
                fontSize: "24px",
                color: "#e4e4e7",
              }}
            >
              {chip}
            </span>
          ))}
        </div>
      </div>
    ),
    { ...OG_SIZE }
  );
}
