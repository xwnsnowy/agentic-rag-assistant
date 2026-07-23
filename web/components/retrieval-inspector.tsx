"use client";

import type { Citation, PoolEntry, RetrievalTrace } from "@/lib/api";
import { cn } from "@/lib/utils";

// "Show work" panel: per rag_search call, the fused candidate pool in hybrid
// (RRF) order next to the post-rerank final order, with rank movement and
// every score the pipeline computed. Dense numeric output on purpose —
// tabular numerals and restrained colour, not badges everywhere.
//
// Honesty rules baked in:
//  - rerank_score null on every entry => the reranker didn't actually score
//    this call (dead key / non-rerank config). Say so plainly instead of
//    rendering a second column that implies a rerank happened. When the key
//    works again the same UI lights up with real movement, no code changes.
//  - timings_ms.rerank null means the rerank step never ran (vs ran in N ms).
//  - `pool` is the PRE-truncation fused list; only its head went to the
//    reranker. The reranked window is derived from which entries carry a
//    score, and the tail below it is visually separated.

export function RetrievalInspector({
  traces,
  citations,
  className,
}: {
  traces: RetrievalTrace[];
  citations: Citation[];
  className?: string;
}) {
  // Pool rows and answer citations both carry chunk_id — join on it.
  const citedBy = new Map<number, number>();
  for (const c of citations) if (!citedBy.has(c.chunk_id)) citedBy.set(c.chunk_id, c.n);

  return (
    <div className={cn("flex flex-col gap-5", className)}>
      {traces.map((trace, i) => (
        <TraceView
          key={i}
          trace={trace}
          citedBy={citedBy}
          title={traces.length > 1 ? `rag_search · call ${i + 1}` : "rag_search"}
        />
      ))}
    </div>
  );
}

function TraceView({
  trace,
  citedBy,
  title,
}: {
  trace: RetrievalTrace;
  citedBy: Map<number, number>;
  title: string;
}) {
  const { pool, final_ids, timings_ms } = trace;
  // Reranked = the reranker actually returned scores. The scored entries are
  // the contiguous head of the fused order (the pipeline sends pool[:window]).
  const rerankedWindow = pool.filter((e) => e.rerank_score != null).length;
  const reranked = rerankedWindow > 0;
  const rerankAttempted = timings_ms.rerank != null;
  const finalEntries = final_ids
    .map((id) => {
      const idx = pool.findIndex((e) => e.chunk_id === id);
      return idx === -1 ? null : { entry: pool[idx], from: idx + 1 };
    })
    .filter((x): x is { entry: PoolEntry; from: number } => x !== null);
  const finalIdSet = new Set(final_ids);

  return (
    <section aria-label={`Retrieval trace for ${title}`}>
      {/* header: what was searched + how long each stage took */}
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <span className="font-mono text-[11px] font-semibold text-primary">{title}</span>
        <span className="min-w-0 truncate font-mono text-[11.5px] text-foreground/85">
          &ldquo;{trace.tool_call_query}&rdquo;
        </span>
      </div>
      {trace.rewritten_query != null && trace.rewritten_query !== trace.tool_call_query && (
        <p className="mt-1 truncate font-mono text-[10.5px] text-muted-foreground">
          rewritten → &ldquo;{trace.rewritten_query}&rdquo;
        </p>
      )}
      <p className="mt-1.5 font-mono text-[10.5px] tabular-nums text-muted-foreground">
        retrieve {Math.round(timings_ms.retrieve)} ms
        {rerankAttempted && <> · rerank {Math.round(timings_ms.rerank!)} ms</>}
        {!rerankAttempted && <> · rerank not run</>}
        {" · "}
        {pool.length} candidates → {final_ids.length} passed to the agent
      </p>

      {/* min-w-0 on both columns: grid items default to min-content width, so
          without it the truncating rows force horizontal overflow on mobile. */}
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        {/* left: fused pool in hybrid order */}
        <div className="min-w-0">
          <h4 className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
            hybrid order <span className="font-normal normal-case">(RRF-fused)</span>
          </h4>
          <ol className="max-h-72 overflow-y-auto pr-1" role="list">
            {pool.map((e, idx) => (
              <PoolRow
                key={`${e.chunk_id}-${idx}`}
                entry={e}
                rank={idx + 1}
                citedN={citedBy.get(e.chunk_id)}
                inFinal={finalIdSet.has(e.chunk_id)}
                showRerankScore={reranked}
                belowWindow={reranked && idx === rerankedWindow}
              />
            ))}
          </ol>
        </div>

        {/* right: order after rerank — or an honest "not reranked" state */}
        <div className="min-w-0">
          <h4 className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
            {reranked ? (
              <>after rerank <span className="font-normal normal-case">(Cohere)</span></>
            ) : (
              <>final order <span className="font-normal normal-case">(not reranked)</span></>
            )}
          </h4>
          {!reranked && (
            <p className="mb-2 rounded-lg border border-dashed bg-muted/40 px-2.5 py-2 text-[11px] leading-snug text-muted-foreground">
              {rerankAttempted
                ? "The reranker returned no scores for this call (service unavailable), so the pipeline fell back to the fused order — these are simply the top candidates from the left column, unchanged."
                : "Reranking was not part of this configuration — these are the top candidates of the fused order."}
            </p>
          )}
          <ol role="list">
            {finalEntries.map(({ entry, from }, j) => (
              <FinalRow
                key={`${entry.chunk_id}-${j}`}
                entry={entry}
                from={from}
                to={j + 1}
                citedN={citedBy.get(entry.chunk_id)}
                reranked={reranked}
              />
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function PoolRow({
  entry,
  rank,
  citedN,
  inFinal,
  showRerankScore,
  belowWindow,
}: {
  entry: PoolEntry;
  rank: number;
  citedN: number | undefined;
  inFinal: boolean;
  showRerankScore: boolean;
  belowWindow: boolean; // first row past the reranked window — draw the cut line
}) {
  return (
    <li>
      {belowWindow && (
        <div className="my-1.5 flex items-center gap-2" aria-hidden>
          <span className="h-px flex-1 border-t border-dashed" />
          <span className="text-[9px] uppercase tracking-wider text-muted-foreground/70">
            below: never sent to the reranker
          </span>
          <span className="h-px flex-1 border-t border-dashed" />
        </div>
      )}
      <div
        className={cn(
          "flex items-start gap-2 rounded-md px-1 py-1",
          inFinal && "bg-primary/5",
        )}
      >
        <span className="w-7 flex-none text-right font-mono text-[10.5px] tabular-nums leading-4 text-muted-foreground">
          {rank}
        </span>
        <div className="min-w-0 flex-1">
          <RowTitle entry={entry} citedN={citedN} />
          <Scores entry={entry} showRerank={showRerankScore} />
        </div>
      </div>
    </li>
  );
}

function FinalRow({
  entry,
  from,
  to,
  citedN,
  reranked,
}: {
  entry: PoolEntry;
  from: number; // 1-based rank in the fused pool
  to: number; // 1-based rank after rerank
  citedN: number | undefined;
  reranked: boolean;
}) {
  const delta = from - to; // positive = promoted by the reranker
  return (
    <li className="flex items-start gap-2 rounded-md px-1 py-1.5">
      <span className="w-7 flex-none text-right font-mono text-[10.5px] tabular-nums leading-4 text-muted-foreground">
        {to}
      </span>
      <div className="min-w-0 flex-1">
        <RowTitle entry={entry} citedN={citedN} />
        <p className="mt-0.5 font-mono text-[10px] tabular-nums text-muted-foreground">
          {reranked ? (
            <>
              #{from} → #{to}{" "}
              {delta > 0 ? (
                <span className="text-emerald-600 dark:text-emerald-400">▲{delta}</span>
              ) : delta < 0 ? (
                <span className="text-rose-600 dark:text-rose-400">▼{-delta}</span>
              ) : (
                <span className="text-muted-foreground/70">＝</span>
              )}
              {entry.rerank_score != null && (
                <>
                  <Sep /> cohere {fmt(entry.rerank_score)}
                </>
              )}
            </>
          ) : (
            <>fused #{from}</>
          )}
        </p>
      </div>
    </li>
  );
}

// Compact score chips: cos (vector cosine) · ts (Postgres ts_rank) · rrf
// (fusion) · cohere (cross-encoder). "—" = that ranker didn't surface/score
// the chunk.
function Scores({ entry, showRerank }: { entry: PoolEntry; showRerank: boolean }) {
  return (
    <p className="mt-0.5 truncate font-mono text-[10px] tabular-nums text-muted-foreground">
      <L>cos</L> {fmt(entry.vector_score)}
      <Sep /> <L>ts</L> {fmt(entry.keyword_score)}
      <Sep /> <L>rrf</L> {fmt(entry.rrf_score, 4)}
      {showRerank && (
        <>
          <Sep /> <L>cohere</L> {fmt(entry.rerank_score)}
        </>
      )}
    </p>
  );
}

// Title line: the text truncates, the badges never do — a truncating
// paragraph would silently swallow them on long page titles.
function RowTitle({ entry, citedN }: { entry: PoolEntry; citedN: number | undefined }) {
  return (
    <p className="flex items-center gap-1.5 text-[11.5px] leading-4 text-foreground/85">
      <span className="min-w-0 truncate">
        {entry.page_title ?? "?"}
        {entry.heading ? <span className="text-muted-foreground"> — {entry.heading}</span> : null}
      </span>
      {/* Which corpus the chunk came from — load-bearing since S2.5, when two
          docs versions coexist in the index: the workbench's flag path
          retrieves from v0.2 BY DESIGN, and without the tag those rows would
          read as wrong-corpus retrieval bugs. Older payloads omit the field. */}
      {entry.docs_version ? <VersionBadge v={entry.docs_version} /> : null}
      {citedN !== undefined && <CitedBadge n={citedN} />}
    </p>
  );
}

function VersionBadge({ v }: { v: string }) {
  return (
    <span className="flex-none whitespace-nowrap rounded border bg-card px-1 py-px font-mono text-[9px] leading-none text-muted-foreground">
      v{v}
    </span>
  );
}

function CitedBadge({ n }: { n: number }) {
  return (
    <span className="flex-none whitespace-nowrap rounded border border-primary/30 bg-primary/10 px-1 py-px font-mono text-[9px] font-semibold leading-none text-primary">
      cited [{n}]
    </span>
  );
}

function L({ children }: { children: React.ReactNode }) {
  return <span className="text-muted-foreground/60">{children}</span>;
}

function Sep() {
  return <span className="text-muted-foreground/40"> · </span>;
}

function fmt(x: number | null, digits = 3): string {
  return x == null ? "—" : x.toFixed(digits);
}
