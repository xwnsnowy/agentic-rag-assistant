"use client";

import { ArrowUpRight, CheckCircle2, TriangleAlert } from "lucide-react";
import type { Change, Citation, MigrationResult } from "@/lib/api";
import { parseUnifiedDiff, type DiffLine } from "@/lib/diff";
import { cn } from "@/lib/utils";

// The migration result panel: change list (every change carrying clickable
// [n] citations), the server-side unified diff, and caveats. Three states,
// each rendered honestly:
//  - modernize: a red/green diff + cited changes;
//  - flag: NO diff — the caveats naming the untouched symbols ARE the
//    product on that path, so they render prominently, not as a footnote;
//  - clean: an explicit "already idiomatic v1.0" state — a migration tool
//    that always finds something to fix is useless.
// No syntax highlighting on purpose (S2.5 scope): the reading task is
// "what changed", which colour-by-line answers; a highlighter answers a
// different question at a real dependency cost.

export function DiffView({
  result,
  citations,
  className,
}: {
  result: MigrationResult;
  citations: Citation[];
  className?: string;
}) {
  const lines = parseUnifiedDiff(result.diff);
  const byN = new Map<number, Citation>();
  for (const c of citations) byN.set(c.n, c);
  const clean =
    lines.length === 0 && result.caveats.length === 0 && result.changes.length === 0;

  return (
    <div className={cn("flex flex-col gap-3.5", className)}>
      {clean && (
        <div className="flex items-start gap-3 rounded-xl border border-emerald-500/35 bg-emerald-500/[0.07] px-4 py-3.5">
          <CheckCircle2 className="mt-0.5 size-4.5 flex-none text-emerald-600 dark:text-emerald-400" aria-hidden />
          <div className="text-sm leading-relaxed">
            <p className="font-semibold text-emerald-700 dark:text-emerald-300">
              Already idiomatic v1.0 — no changes
            </p>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">
              No deprecated or unevidenced LangGraph APIs were detected, so the
              code is returned byte-identical. It never touched an LLM.
            </p>
          </div>
        </div>
      )}

      {/* Caveats before the diff: on the flag path they are the whole answer. */}
      {result.caveats.length > 0 && (
        <section
          aria-label="Caveats"
          className="rounded-xl border border-amber-500/40 bg-amber-500/[0.08] px-4 py-3.5"
        >
          <h3 className="flex items-center gap-2 text-[13px] font-semibold text-amber-700 dark:text-amber-300">
            <TriangleAlert className="size-4 flex-none" aria-hidden />
            Kept unchanged — review needed
          </h3>
          <ul className="mt-2 flex flex-col gap-2">
            {result.caveats.map((cv, i) => (
              <li key={i} className="text-[13px] leading-relaxed text-foreground/85">
                <CaveatText text={cv} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.changes.length > 0 && (
        <section aria-label="Changes">
          <h3 className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
            changes <span className="font-normal normal-case">(each grounded in the pinned v1.0 docs)</span>
          </h3>
          <ol className="mt-1.5 flex flex-col gap-1.5">
            {result.changes.map((c, i) => (
              <ChangeRow key={i} change={c} byN={byN} />
            ))}
          </ol>
        </section>
      )}

      {lines.length > 0 && <DiffTable lines={lines} />}
    </div>
  );
}

function ChangeRow({ change, byN }: { change: Change; byN: Map<number, Citation> }) {
  return (
    <li className="flex items-start gap-2 text-[13px] leading-relaxed">
      <span className="mt-[5px] size-1.5 flex-none rounded-full bg-primary/60" aria-hidden />
      <span className="min-w-0">
        {change.description}{" "}
        {change.citations.map((n) => {
          const c = byN.get(n);
          return c ? (
            <a
              key={n}
              href={c.source_url}
              target="_blank"
              rel="noopener noreferrer"
              title={`${c.page_title} — ${c.heading}`}
              className="ml-0.5 align-super font-mono text-[10px] font-semibold text-primary underline-offset-2 hover:underline"
            >
              [{n}]
            </a>
          ) : (
            // Number without a delivered source: render it inert, never a dead link.
            <span key={n} className="ml-0.5 align-super font-mono text-[10px] text-muted-foreground">
              [{n}]
            </span>
          );
        })}
      </span>
    </li>
  );
}

// Red/green unified diff as a table: two tabular-nums gutters (old/new line
// numbers) + marker + code. Gutters and markers are select-none so a
// copy/paste grabs clean code. Horizontal overflow stays inside this panel
// (overflow-x-auto + w-max rows) — the page never scrolls sideways.
function DiffTable({ lines }: { lines: DiffLine[] }) {
  return (
    <div className="overflow-hidden rounded-xl border bg-card/60">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[12px] leading-[1.45]">
          <tbody>
            {lines.map((l, i) => (
              <Row key={i} line={l} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Row({ line }: { line: DiffLine }) {
  if (line.kind === "file") {
    return (
      <tr className="bg-muted/50 text-muted-foreground">
        <td colSpan={3} aria-hidden className="select-none" />
        <td className="whitespace-pre px-3 py-0.5 text-[11px]">{line.text}</td>
      </tr>
    );
  }
  if (line.kind === "hunk") {
    return (
      <tr className="bg-primary/[0.06] text-primary/80">
        <td colSpan={3} aria-hidden className="select-none" />
        <td className="whitespace-pre px-3 py-0.5 text-[11px]">{line.text}</td>
      </tr>
    );
  }
  const add = line.kind === "add";
  const del = line.kind === "del";
  return (
    <tr
      className={cn(
        add && "bg-emerald-500/[0.13] dark:bg-emerald-500/[0.16]",
        del && "bg-rose-500/[0.11] dark:bg-rose-500/[0.14]",
      )}
    >
      <Gutter no={line.kind === "add" ? null : line.oldNo} />
      <Gutter no={line.kind === "del" ? null : line.newNo} />
      <td
        aria-hidden
        className={cn(
          "w-5 select-none pl-2 text-center align-top",
          add && "text-emerald-600 dark:text-emerald-400",
          del && "text-rose-600 dark:text-rose-400",
          !add && !del && "text-transparent",
        )}
      >
        {add ? "+" : del ? "−" : " "}
      </td>
      <td className="w-full whitespace-pre px-3 align-top text-foreground/90">
        {/* sr-only added/removed so the diff reads correctly without colour */}
        {(add || del) && <span className="sr-only">{add ? "added: " : "removed: "}</span>}
        {line.text || " "}
      </td>
    </tr>
  );
}

function Gutter({ no }: { no: number | null }) {
  return (
    <td
      aria-hidden
      className="w-9 min-w-9 select-none pr-1.5 text-right align-top text-[10.5px] tabular-nums text-muted-foreground/55"
    >
      {no ?? ""}
    </td>
  );
}

// Caveats are backend-built sentences with `backticked` symbols and a
// trailing [slug] marker. A full Markdown pass is overkill for one inline
// pattern — split on backticks and style the odd segments as code.
function CaveatText({ text }: { text: string }) {
  const parts = text.split("`");
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <code
            key={i}
            className="rounded-md border bg-muted px-1.5 py-0.5 font-mono text-[11.5px] text-primary"
          >
            {p}
          </code>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}
