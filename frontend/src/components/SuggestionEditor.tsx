import { useState } from "react"
import { useAnalysis } from "../state/useAnalysis"
import type { AnalysisIssue } from "../types"

export function SuggestionEditor({
  issue,
  initialText,
}: {
  issue: AnalysisIssue
  initialText?: string
}) {
  const { setIssueStatus, setEditing } = useAnalysis()
  const [value, setValue] = useState(issue.editedText ?? initialText ?? issue.suggestion)

  return (
    <div className="mt-2">
      <label htmlFor={`edit-${issue.id}`} className="sr-only">
        Edit suggested requirement
      </label>
      <textarea
        id={`edit-${issue.id}`}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        rows={3}
        className="w-full rounded border border-line bg-canvas px-2 py-1.5 text-[12px] leading-5"
      />
      <div className="mt-1.5 flex gap-2">
        <button
          type="button"
          className="rounded bg-ink px-2 py-1 text-[12px] text-white"
          onClick={() => setIssueStatus(issue.id, "edited", value.trim())}
        >
          Save
        </button>
        <button
          type="button"
          className="rounded px-2 py-1 text-[12px] text-muted hover:text-ink"
          onClick={() => setEditing(null)}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
