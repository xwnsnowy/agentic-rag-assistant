"use client";

import { Fragment } from "react";
import { Check } from "lucide-react";
import type { NodeEvent } from "@/lib/api";
import { cn } from "@/lib/utils";

// A compact horizontal strip visualizing a LangGraph run: each node lit by
// status (idle | active | done), edges drawn between adjacent nodes.
//
// This component knows NOTHING about chat. It takes a topology (node names +
// edges) plus the raw node-event list and folds the events itself — Stage 2
// reuses it unmodified for the migration graph
// (detect → research → rewrite → verify) by passing a different topology.

export type GraphNodeStatus = "idle" | "active" | "done";

export type GraphTopology = {
  /** Rendered left-to-right, in this order. ids starting with "__" (START/END
   *  sentinels) are drawn as small terminal markers. */
  nodes: { id: string; label: string }[];
  /** Directed edges, used to pick the glyph between adjacent nodes:
   *  a→b renders "→", a→b plus b→a renders "⇄". */
  edges: [string, string][];
};

/** The chat agent's shape — the default so <AgentGraph events={...}/> just works. */
export const CHAT_AGENT_TOPOLOGY: GraphTopology = {
  nodes: [
    { id: "__start__", label: "start" },
    { id: "agent", label: "agent" },
    { id: "tools", label: "tools" },
    { id: "__end__", label: "end" },
  ],
  edges: [
    ["__start__", "agent"],
    ["agent", "tools"],
    ["tools", "agent"],
    ["agent", "__end__"],
  ],
};

// Fold the event stream into one status per node. Deliberately tolerant —
// the backend dedupes "active" per turn (a second agent round emits only
// another "done"), "done" can repeat, and events for unknown nodes must not
// break anything. "active" after "done" re-lights the node (a later round).
function foldStatuses(
  topology: GraphTopology,
  events: NodeEvent[],
): Record<string, GraphNodeStatus> {
  const status: Record<string, GraphNodeStatus> = {};
  for (const n of topology.nodes) status[n.id] = "idle";
  for (const ev of events) {
    if (!(ev.name in status)) continue;
    status[ev.name] = ev.status === "active" ? "active" : "done";
  }
  // Convention: the START sentinel is done as soon as the run emitted anything
  // (backends never report their entry sentinel).
  if (events.length > 0 && status.__start__ === "idle") status.__start__ = "done";
  return status;
}

export function AgentGraph({
  topology = CHAT_AGENT_TOPOLOGY,
  events,
  className,
}: {
  topology?: GraphTopology;
  events: NodeEvent[];
  className?: string;
}) {
  const statuses = foldStatuses(topology, events);
  const has = (a: string, b: string) =>
    topology.edges.some(([x, y]) => x === a && y === b);

  // Announce the latest state change for screen readers — the visual pulse
  // alone would make the graph's progress silently invisible.
  const last = [...events].reverse().find((ev) =>
    topology.nodes.some((n) => n.id === ev.name),
  );
  const lastLabel = last
    ? topology.nodes.find((n) => n.id === last.name)?.label
    : undefined;
  const announcement = last
    ? `${lastLabel} node ${last.status === "active" ? "running" : "finished"}`
    : "";

  return (
    <div
      role="group"
      aria-label="Agent execution graph"
      className={cn(
        "glass flex items-center gap-1.5 overflow-x-auto rounded-xl px-3 py-2 shadow-sm",
        className,
      )}
    >
      {topology.nodes.map((node, i) => {
        const prev = topology.nodes[i - 1];
        return (
          <Fragment key={node.id}>
            {prev && (
              <Edge
                bidirectional={has(prev.id, node.id) && has(node.id, prev.id)}
                hot={
                  statuses[prev.id] === "active" || statuses[node.id] === "active"
                }
              />
            )}
            <NodePill node={node} status={statuses[node.id]} />
          </Fragment>
        );
      })}
      <span aria-live="polite" className="sr-only">
        {announcement}
      </span>
    </div>
  );
}

function NodePill({
  node,
  status,
}: {
  node: { id: string; label: string };
  status: GraphNodeStatus;
}) {
  const terminal = node.id.startsWith("__");
  return (
    <span
      className={cn(
        "inline-flex flex-none items-center gap-1.5 whitespace-nowrap rounded-full border font-mono transition-colors duration-300",
        terminal
          ? "px-2 py-0.5 text-[9px] uppercase tracking-widest"
          : "px-2.5 py-1 text-[11px]",
        status === "idle" && "border-border/70 bg-card/40 text-muted-foreground/55",
        status === "active" &&
          "border-primary/60 bg-primary/10 text-primary shadow-[0_0_16px_-4px] shadow-primary/60",
        status === "done" && "border-border bg-card text-foreground/80",
      )}
    >
      {status === "done" ? (
        <Check className="size-3 flex-none text-primary" aria-hidden />
      ) : (
        <span
          aria-hidden
          className={cn(
            "size-1.5 flex-none rounded-full",
            status === "active" ? "node-pulse bg-primary" : "bg-muted-foreground/30",
          )}
        />
      )}
      {node.label}
      <span className="sr-only">
        {status === "active" ? ": running" : status === "done" ? ": finished" : ": pending"}
      </span>
    </span>
  );
}

// Edge between two adjacent nodes: two dashed line halves around a direction
// glyph. When "hot" (an endpoint is active) the dashes flow via .flow-line —
// already exempted under prefers-reduced-motion in globals.css.
function Edge({ bidirectional, hot }: { bidirectional: boolean; hot: boolean }) {
  const half = (
    <svg
      className="h-2 min-w-2 flex-1"
      preserveAspectRatio="none"
      viewBox="0 0 24 8"
      aria-hidden
    >
      <line
        x1="0"
        y1="4"
        x2="24"
        y2="4"
        stroke="currentColor"
        strokeWidth="1.5"
        className={hot ? "flow-line" : undefined}
        strokeDasharray={hot ? undefined : "3 5"}
      />
    </svg>
  );
  return (
    <span
      aria-hidden
      className={cn(
        "flex min-w-5 flex-1 items-center gap-0.5 transition-colors duration-300",
        hot ? "text-primary" : "text-muted-foreground/35",
      )}
    >
      {half}
      <span className="text-[10px] leading-none">{bidirectional ? "⇄" : "→"}</span>
      {half}
    </span>
  );
}
