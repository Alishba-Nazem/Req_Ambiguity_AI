import { MODEL_TYPE_LABELS } from "../types"
import { useAnalysis } from "../state/useAnalysis"

export function IssueSidebar() {
  const { result, selectedIssueId, selectIssue } = useAnalysis()
  if (!result) return null
  const visible = result.issues.filter((issue) => issue.status !== "dismissed")

  return (
    <aside className="bg-transparent">
      <h2 className="font-serif text-[36px] leading-none">
        {visible.length}{" "}
        <span className="text-[22px]">
          {visible.length === 1 ? "issue to resolve" : "issues to resolve"}
        </span>
      </h2>
      <p className="mt-3 text-[12px] uppercase tracking-[0.14em] text-muted">
        All {visible.length}
      </p>
      <div className="mt-5 space-y-3">
        {visible.length === 0 ? (
          <p className="text-[13px] text-muted">No issues found in this document.</p>
        ) : (
          visible.map((issue, index) => (
            <button
              key={issue.id}
              id={`issue-${issue.id}`}
              type="button"
              onClick={() => selectIssue(issue.id)}
              className={`w-full rounded-sm bg-surface px-4 py-4 text-left shadow-[0_0_0_1px_var(--color-line)] ${
                issue.id === selectedIssueId
                  ? "shadow-[0_0_0_1px_var(--color-ink)]"
                  : ""
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-[12px] text-muted">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="text-[11px] uppercase tracking-[0.12em] text-muted">
                  {issue.modelType ? MODEL_TYPE_LABELS[issue.modelType] : "Vague"}
                </span>
              </div>
              <p className="mt-2 font-serif text-[22px] leading-7">
                “{issue.phrase || issue.sentence}”
              </p>
              <p className="mt-2 text-[13px] leading-5 text-muted">
                {issue.explanation}
              </p>
            </button>
          ))
        )}
      </div>
    </aside>
  )
}
