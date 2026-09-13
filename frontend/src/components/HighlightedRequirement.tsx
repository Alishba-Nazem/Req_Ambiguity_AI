import type { KeyboardEvent } from "react"
import type { AnalysisIssue } from "../types"

interface Props {
  text: string
  issues: AnalysisIssue[]
  selectedIssueId: string | null
  onSelect: (id: string) => void
  onOpenDetails?: (id: string) => void
}

export function HighlightedRequirement({
  text,
  issues,
  selectedIssueId,
  onSelect,
  onOpenDetails,
}: Props) {
  const visible = issues
    .filter((issue) => issue.status !== "dismissed")
    .sort((a, b) => a.start - b.start)

  const parts: { key: string; text: string; issue?: AnalysisIssue }[] = []
  let cursor = 0
  visible.forEach((issue, index) => {
    if (issue.start < cursor) return
    if (issue.start > cursor) {
      parts.push({ key: `t-${cursor}`, text: text.slice(cursor, issue.start) })
    }
    parts.push({
      key: issue.id,
      text: text.slice(issue.start, issue.end),
      issue,
    })
    cursor = issue.end
    if (index === visible.length - 1 && cursor < text.length) {
      parts.push({ key: `t-end`, text: text.slice(cursor) })
    }
  })
  if (visible.length === 0) {
    parts.push({ key: "all", text })
  } else if (cursor < text.length && parts[parts.length - 1]?.key !== "t-end") {
    parts.push({ key: `t-${cursor}`, text: text.slice(cursor) })
  }

  function onKey(event: KeyboardEvent<HTMLElement>, id: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      onSelect(id)
    }
  }

  const numberFor = new Map(visible.map((issue, index) => [issue.id, index + 1]))

  return (
    <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">
      {parts.map((part) => {
        if (!part.issue) {
          return <span key={part.key}>{part.text}</span>
        }
        const issue = part.issue
        const selected = issue.id === selectedIssueId
        const number = numberFor.get(issue.id)
        return (
          <mark
            key={part.key}
            role="button"
            tabIndex={0}
            data-selected={selected}
            aria-pressed={selected}
            aria-label={`${issue.phrase}, ${issue.category.replaceAll("_", " ")}`}
            className={`hl hl-${issue.category}`}
            onClick={() => onSelect(issue.id)}
            onDoubleClick={() => onOpenDetails?.(issue.id)}
            onKeyDown={(event) => onKey(event, issue.id)}
          >
            {part.text}
            {number ? (
              <sup className="ml-0.5 font-sans text-[10px] text-muted">{number}</sup>
            ) : null}
          </mark>
        )
      })}
    </p>
  )
}
