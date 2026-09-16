import { ExportActions } from "../components/ExportActions"
import { countWords } from "../lib/document"
import { useAnalysis } from "../state/useAnalysis"

export function ReviewPage() {
  const { result, setView } = useAnalysis()

  if (!result) {
    return (
      <div className="px-4 py-16 text-center text-[13px] text-muted">
        Analyze a document from Input first.
      </div>
    )
  }

  const issues = result.issues.filter((issue) => issue.status !== "dismissed")
  const vague = issues.filter(
    (issue) => issue.category === "vague_term" || issue.modelType === "pragmatic",
  ).length
  const other = Math.max(0, issues.length - vague)
  const finalScore = result.clarityScore ?? result.finalScore ?? 0
  const clarity = Math.max(0, Math.min(100, Math.round(finalScore * 10)))
  const words = countWords(result.originalText)
  const nextSteps = issues.slice(0, 3).map((issue, index) => ({
    n: String(index + 1).padStart(2, "0"),
    text: issue.explanation,
  }))

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[12px] uppercase tracking-[0.16em] text-muted">
          Report / Analysis {String(issues.length).padStart(3, "0")}
        </p>
        <ExportActions />
      </div>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <h1 className="font-serif max-w-[16ch] text-[56px] leading-[0.95] tracking-tight">
          Requirements analysis
        </h1>
        <p className="text-[13px] text-muted">
          Ready for review · {words} words · {issues.length} findings
        </p>
      </div>
      <p className="mt-4 max-w-[52ch] text-[16px] leading-7 text-muted">
        A plain-language review of ambiguity, vagueness, and internal conflict.
      </p>

      <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat value={String(issues.length).padStart(3, "0")} label="Issues found" />
        <Stat value={String(vague).padStart(3, "0")} label="Vague language" />
        <Stat value={String(other).padStart(3, "0")} label="Other findings" />
        <Stat value={`${clarity}%`} label="Clarity score" />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section>
          <h2 className="font-serif text-[32px] leading-none">Findings by category</h2>
          <div className="mt-6 space-y-4">
            <Bar label="Vague language" count={vague} total={Math.max(issues.length, 1)} />
            <Bar label="Other findings" count={other} total={Math.max(issues.length, 1)} />
          </div>
          <h2 className="font-serif mt-10 text-[32px] leading-none">
            Recommended next pass
          </h2>
          <ol className="mt-5 space-y-3">
            {nextSteps.length === 0 ? (
              <li className="text-[14px] text-muted">No follow-up actions.</li>
            ) : (
              nextSteps.map((step) => (
                <li key={step.n} className="flex gap-3 text-[15px] leading-6">
                  <span className="text-muted">{step.n}</span>
                  <span>{step.text}</span>
                </li>
              ))
            )}
          </ol>
        </section>
        <aside className="space-y-4">
          <div className="rounded-sm bg-surface px-6 py-8 text-center shadow-[0_0_0_1px_var(--color-line)]">
            <p className="font-serif text-[28px]">At a glance</p>
            <div className="mx-auto mt-6 flex h-36 w-36 items-center justify-center rounded-full border-[10px] border-ink/15 border-t-ink">
              <span className="font-serif text-[36px]">{clarity}%</span>
            </div>
            <p className="mt-4 text-[15px] text-muted">
              {clarity >= 70 ? "Low" : clarity >= 45 ? "Moderate" : "High"} ambiguity
            </p>
            <p className="mt-4 text-[13px] leading-6 text-muted">
              {issues.length === 0
                ? "The wording looks testable as written."
                : `The document has ${issues.length} flagged phrase${issues.length === 1 ? "" : "s"} that leave implementation decisions open.`}
            </p>
          </div>
          <div className="rounded-sm bg-[#fff4d6] px-5 py-5">
            <p className="text-[11px] uppercase tracking-[0.14em] text-muted">
              Next step
            </p>
            <p className="mt-2 text-[16px] leading-6">
              Resolve the flagged phrases before estimation.
            </p>
            <button
              type="button"
              className="mt-4 text-[13px] underline-offset-2 hover:underline"
              onClick={() => setView("analysis")}
            >
              Back to document
            </button>
          </div>
        </aside>
      </div>
    </div>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-sm bg-surface px-5 py-6 shadow-[0_0_0_1px_var(--color-line)]">
      <p className="font-serif text-[48px] leading-none">{value}</p>
      <p className="mt-2 text-[13px] text-muted">{label}</p>
    </div>
  )
}

function Bar({
  label,
  count,
  total,
}: {
  label: string
  count: number
  total: number
}) {
  const width = Math.max(4, Math.round((count / total) * 100))
  return (
    <div>
      <div className="flex justify-between text-[14px]">
        <span>{label}</span>
        <span>{count}</span>
      </div>
      <div className="mt-2 h-[3px] bg-line">
        <div className="h-full bg-accent" style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}
