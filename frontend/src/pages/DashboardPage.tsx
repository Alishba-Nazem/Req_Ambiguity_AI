import { useAnalysis } from "../state/useAnalysis"

export function DashboardPage() {
  const { history, setView, openHistoryItem, status } = useAnalysis()
  const recent = history.slice(0, 5)

  return (
    <div className="mx-auto max-w-[880px] px-4 py-8">
      <p className="text-[12px] text-muted">Workspace / Dashboard</p>
      <h1 className="mt-1 text-[22px] font-semibold">Requirement workspace</h1>
      <p className="mt-2 max-w-[60ch] text-[14px] text-muted">
        Write a requirement from an idea, or analyze an existing statement for
        vague wording and missing measures.
      </p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => setView("create")}
          className="border border-line bg-surface px-4 py-4 text-left hover:border-primary"
        >
          <p className="text-[15px] font-semibold">Create requirement</p>
          <p className="mt-1 text-[13px] text-muted">
            Describe what you want. Get a shall-statement you can test.
          </p>
        </button>
        <button
          type="button"
          onClick={() => setView("input")}
          className="border border-line bg-surface px-4 py-4 text-left hover:border-primary"
        >
          <p className="text-[15px] font-semibold">Analyze requirement</p>
          <p className="mt-1 text-[13px] text-muted">
            Paste a requirement and see the unclear phrase, score, and rewrite.
          </p>
        </button>
      </div>

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">Recent analysis</h2>
          <button
            type="button"
            className="text-[13px] text-primary hover:underline"
            onClick={() => setView("history")}
          >
            View all
          </button>
        </div>
        {recent.length === 0 ? (
          <p className="mt-3 border border-dashed border-line bg-surface px-4 py-6 text-[13px] text-muted">
            {status === "analyzing"
              ? "Analyzing requirement…"
              : "Create your first requirement to start analyzing ambiguity."}
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-line border border-line bg-surface">
            {recent.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="flex w-full items-start justify-between gap-3 px-3 py-2.5 text-left hover:bg-background"
                  onClick={() => openHistoryItem(item.id)}
                >
                  <span className="min-w-0">
                    <span className="font-mono text-[12px] text-muted">{item.id}</span>
                    <span className="mt-0.5 block truncate text-[13px]">
                      {item.requirement}
                    </span>
                  </span>
                  <span className="shrink-0 text-[12px] text-muted">
                    {item.score != null ? `${item.score.toFixed(1)}/10` : "—"} · {item.status}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
