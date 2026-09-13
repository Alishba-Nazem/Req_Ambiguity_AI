import type { AnalysisIssue } from "../types"

export function scoreOutOfTen(score100: number): string {
  const clamped = Math.max(0, Math.min(100, score100))
  return (clamped / 10).toFixed(1)
}

export function countWords(text: string): number {
  const parts = text.trim().split(/\s+/).filter(Boolean)
  return parts.length
}

export function replacementFor(issue: AnalysisIssue): string {
  return issue.editedText ?? issue.suggestion
}

export function buildRevisedText(
  original: string,
  issues: AnalysisIssue[],
  combinedSuggestion?: string | null,
): string {
  const remaining = issues.filter((issue) => issue.status !== "dismissed")
  if (remaining.length === 0) return original
  const edited = remaining.find((issue) => issue.status === "edited" && issue.editedText)
  if (edited?.editedText) return edited.editedText
  const applied = remaining.filter(
    (issue) => issue.status === "accepted" || issue.status === "edited",
  )
  if (applied.length === 0) return original
  if (applied.length === remaining.length && combinedSuggestion) {
    return combinedSuggestion
  }

  let next = original
  const used = new Set<number>()
  const sorted = [...applied].sort((a, b) => b.sentenceStart - a.sentenceStart)
  for (const issue of sorted) {
    if (used.has(issue.sentenceStart)) continue
    used.add(issue.sentenceStart)
    next =
      next.slice(0, issue.sentenceStart) +
      replacementFor(issue) +
      next.slice(issue.sentenceEnd)
  }
  return next
}

export interface DiffToken {
  value: string
  kind: "equal" | "add" | "del"
}

export function diffWords(original: string, revised: string): DiffToken[] {
  const a = tokenize(original)
  const b = tokenize(revised)
  const m = a.length
  const n = b.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array.from({ length: n + 1 }, () => 0))
  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const tokens: DiffToken[] = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      tokens.push({ value: a[i], kind: "equal" })
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      tokens.push({ value: a[i], kind: "del" })
      i += 1
    } else {
      tokens.push({ value: b[j], kind: "add" })
      j += 1
    }
  }
  while (i < m) {
    tokens.push({ value: a[i], kind: "del" })
    i += 1
  }
  while (j < n) {
    tokens.push({ value: b[j], kind: "add" })
    j += 1
  }
  return tokens
}

function tokenize(text: string): string[] {
  return text.split(/(\s+)/).filter((part) => part.length > 0)
}

export function severityCounts(issues: AnalysisIssue[]) {
  return {
    critical: issues.filter((issue) => issue.severity === "critical" && issue.status !== "dismissed").length,
    medium: issues.filter((issue) => issue.severity === "medium" && issue.status !== "dismissed").length,
    low: issues.filter((issue) => issue.severity === "low" && issue.status !== "dismissed").length,
    open: issues.filter((issue) => issue.status === "open").length,
    total: issues.length,
  }
}
