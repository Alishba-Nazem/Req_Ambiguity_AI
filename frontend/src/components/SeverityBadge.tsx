import { CATEGORY_LABELS, type IssueCategory, type Severity } from "../types"

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  medium: "Medium",
  low: "Low",
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const tone =
    severity === "critical"
      ? "bg-critical-bg text-critical"
      : severity === "medium"
        ? "bg-medium-bg text-medium"
        : "bg-low-bg text-low"
  const mark =
    severity === "critical" ? "■" : severity === "medium" ? "▲" : "●"
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${tone}`}
    >
      <span aria-hidden="true">{mark}</span>
      {SEVERITY_LABEL[severity]}
    </span>
  )
}

export function CategoryLabel({ category }: { category: IssueCategory }) {
  return (
    <span className="text-[11px] font-medium uppercase tracking-wide text-muted">
      {CATEGORY_LABELS[category]}
    </span>
  )
}
