import { HighlightedRequirement } from "./HighlightedRequirement"
import { useAnalysis } from "../state/useAnalysis"

export function RequirementViewer() {
  const { result, selectedIssueId, selectIssue } = useAnalysis()
  if (!result) return null
  const accepted = result.issues.some(
    (issue) => issue.status === "accepted" || issue.status === "edited",
  )
  const text = accepted
    ? result.displayText
    : result.generatedText || result.originalText
  const issues = accepted ? [] : result.issues

  return (
    <section>
      <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
        Flagged wording
      </h2>
      <div className="mt-2 border border-line bg-surface px-3 py-3">
        <HighlightedRequirement
          text={text}
          issues={issues}
          selectedIssueId={selectedIssueId}
          onSelect={selectIssue}
        />
      </div>
    </section>
  )
}
