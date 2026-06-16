import { API_URL, getHealth } from "@/lib/api";

// Server component: fetches the AI service health on each request so the
// Phase 0 Next.js -> FastAPI link is visible in the browser.
export default async function Home() {
  const [live, db] = await Promise.all([
    getHealth("/health"),
    getHealth("/db/health"),
  ]);

  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 p-8 font-sans dark:bg-black">
      <main className="w-full max-w-xl space-y-8">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            Agentic RAG Assistant
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Phase 0 — Next.js &rarr; FastAPI health check
          </p>
        </header>

        <section className="space-y-3">
          <HealthRow label="AI service (/health)" result={live} />
          <HealthRow label="Database (/db/health)" result={db} />
        </section>

        <footer className="text-xs text-zinc-500 dark:text-zinc-500">
          API: <code>{API_URL}</code>
        </footer>
      </main>
    </div>
  );
}

function HealthRow({
  label,
  result,
}: {
  label: string;
  result: Awaited<ReturnType<typeof getHealth>>;
}) {
  const ok = result.ok;
  return (
    <div className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
      <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
        {label}
      </span>
      <span
        className={`flex items-center gap-2 text-sm font-medium ${
          ok ? "text-green-600" : "text-red-600"
        }`}
      >
        <span
          className={`h-2 w-2 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`}
        />
        {ok ? "connected" : result.error}
      </span>
    </div>
  );
}
