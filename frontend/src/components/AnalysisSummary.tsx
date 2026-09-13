import { severityCounts } from "../lib/document"
import type { AnalysisIssue } from "../types"

export function AnalysisSummary({ issues }: { issues: AnalysisIssue[] }) {
  const counts = severityCounts(issues)
  const remaining = counts.critical + counts.medium + counts.low
  return (
    <p className="text-[13px] text-ink">
      <span className="font-semibold">{remaining} issues found</span>
      <span className="text-muted">
        {" "}
        · {counts.critical} critical · {counts.medium} medium · {counts.low} low
      </span>
    </p>
  )
}
