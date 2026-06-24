import { cn } from "@/lib/utils";

// A small, cute AI mascot rendered as inline SVG so it scales crisply and
// animates with CSS only (keyframes live in globals.css under "AI mascot").
// It reacts to three states:
//   idle      → floats + blinks
//   thinking  → wobbles + a row of bobbing dots
//   answering → happy curved eyes (used while a reply streams in)
export type MascotState = "idle" | "thinking" | "answering";

export function AiMascot({
  state = "idle",
  className,
}: {
  state?: MascotState;
  className?: string;
}) {
  const happy = state === "answering";
  return (
    <span className={cn("mascot inline-block", className)} data-state={state} aria-hidden>
      <svg viewBox="0 0 120 140" className="size-full overflow-visible">
        <defs>
          <linearGradient id="mascotBody" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#6366f1" />
            <stop offset="0.55" stopColor="#8b5cf6" />
            <stop offset="1" stopColor="#a78bfa" />
          </linearGradient>
          <radialGradient id="mascotGlow" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#8b5cf6" stopOpacity="0.5" />
            <stop offset="1" stopColor="#8b5cf6" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* soft glow */}
        <ellipse cx="60" cy="74" rx="52" ry="50" fill="url(#mascotGlow)" />

        {/* antenna */}
        <line x1="60" y1="30" x2="60" y2="15" stroke="#a78bfa" strokeWidth="3" strokeLinecap="round" />
        <circle className="mascot-antenna" cx="60" cy="11" r="5.5" fill="#22d3ee" />

        {/* head body */}
        <g className="mascot-body">
          <rect x="18" y="30" width="84" height="80" rx="27" fill="url(#mascotBody)" />
          {/* glossy top highlight */}
          <ellipse cx="46" cy="48" rx="22" ry="11" fill="#ffffff" opacity="0.18" />
          {/* little ears */}
          <rect x="10" y="60" width="9" height="22" rx="4.5" fill="#8b5cf6" />
          <rect x="101" y="60" width="9" height="22" rx="4.5" fill="#8b5cf6" />

          {/* face screen */}
          <rect x="30" y="46" width="60" height="48" rx="20" fill="#0b1020" />

          {/* cheeks */}
          <circle cx="40" cy="80" r="5" fill="#fb7185" opacity="0.55" />
          <circle cx="80" cy="80" r="5" fill="#fb7185" opacity="0.55" />

          {/* eyes */}
          {happy ? (
            <>
              <path d="M40 70 q6 -8 12 0" fill="none" stroke="#f8fafc" strokeWidth="4" strokeLinecap="round" />
              <path d="M68 70 q6 -8 12 0" fill="none" stroke="#f8fafc" strokeWidth="4" strokeLinecap="round" />
            </>
          ) : (
            <>
              <rect className="mascot-eye" x="42" y="62" width="9" height="13" rx="4.5" fill="#f8fafc" />
              <rect className="mascot-eye" x="69" y="62" width="9" height="13" rx="4.5" fill="#f8fafc" />
              {/* eye shines */}
              <circle cx="49" cy="65" r="1.6" fill="#22d3ee" />
              <circle cx="76" cy="65" r="1.6" fill="#22d3ee" />
            </>
          )}

          {/* mouth */}
          {happy ? (
            <path d="M50 82 q10 8 20 0" fill="none" stroke="#f8fafc" strokeWidth="3.2" strokeLinecap="round" />
          ) : (
            <path d="M52 82 q8 5 16 0" fill="none" stroke="#f8fafc" strokeWidth="3" strokeLinecap="round" opacity="0.85" />
          )}
        </g>

        {/* thinking dots */}
        {state === "thinking" && (
          <g>
            <circle className="mascot-think-dot" cx="46" cy="124" r="4" fill="#8b5cf6" />
            <circle className="mascot-think-dot" cx="60" cy="124" r="4" fill="#a78bfa" />
            <circle className="mascot-think-dot" cx="74" cy="124" r="4" fill="#22d3ee" />
          </g>
        )}
      </svg>
    </span>
  );
}
