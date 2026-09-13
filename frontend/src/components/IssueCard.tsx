import { CategoryLabel, SeverityBadge } from "./SeverityBadge"
import { SuggestionEditor } from "./SuggestionEditor"
import { replacementFor } from "../lib/document"
import { useAnalysis } from "../state/useAnalysis"
import type { AnalysisIssue } from "../types"

export function IssueCard({
  issue,
  selected,
}: {
  issue: AnalysisIssue
  selected: boolean
}) {
  const { selectIssue, openDrawer, setIssueStatus, setEditing, editingIssueId } =
    useAnalysis()
  const editing = editingIssueId === issue.id
  const dismissed = issue.status === "dismissed"
  const accepted = issue.status === "accepted" || issue.status === "edited"

  return (
    <article
      id={`issue-${issue.id}`}
      className={`border-b border-line px-3 py-3 ${
        selected ? "bg-low-bg" : "bg-surface"
      } ${dismissed ? "opacity-60" : ""}`}
    >
      <button
        type="button"
        className="w-full text-left"
        onClick={() => selectIssue(issue.id)}
        aria-current={selected ? "true" : undefined}
      >
        <div className="flex items-center justify-between gap-2">
          <CategoryLabel category={issue.category} />
          <SeverityBadge severity={issue.severity} />
        </div>
        <p className="mt-1.5 line-clamp-2 text-[12px] text-muted">
          {issue.sentence}
        </p>
      </button>
      <p className="mt-1.5 text-[13px] leading-5 text-ink">{issue.explanation}</p>
      {editing ? (
        <SuggestionEditor key={issue.id} issue={issue} />
      ) : (
        <p className="mt-1.5 text-[12px] leading-5">
          <span className="text-muted">Suggestion: </span>
          {replacementFor(issue)}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {accepted ? (
          <span className="text-[11px] font-medium text-accepted">
            {issue.status === "edited" ? "Edited" : "Accepted"}
          </span>
        ) : null}
        {dismissed ? (
          <span className="text-[11px] font-medium text-muted">Dismissed</span>
        ) : null}
        {!accepted && !dismissed && !editing ? (
          <>
            <button
              type="button"
              className="rounded bg-ink px-2 py-0.5 text-[12px] text-white"
              onClick={() => setIssueStatus(issue.id, "accepted")}
            >
              Accept
            </button>
            <button
              type="button"
              className="rounded border border-line px-2 py-0.5 text-[12px]"
              onClick={() => {
                selectIssue(issue.id)
                setEditing(issue.id)
              }}
            >
              Edit
            </button>
            <button
              type="button"
              className="rounded px-2 py-0.5 text-[12px] text-muted hover:text-ink"
              onClick={() => setIssueStatus(issue.id, "dismissed")}
            >
              Dismiss
            </button>
          </>
        ) : null}
        {(accepted || dismissed) && (
          <button
            type="button"
            className="text-[12px] text-muted hover:text-ink"
            onClick={() => setIssueStatus(issue.id, "open", null)}
          >
            Undo
          </button>
        )}
        <button
          type="button"
          className="ml-auto text-[12px] text-muted hover:text-ink"
          onClick={() => openDrawer(issue.id)}
        >
          Details
        </button>
        <span className="text-[11px] text-muted">
          Confidence {Math.round(issue.confidence * 100)}%
        </span>
      </div>
    </article>
  )
}
