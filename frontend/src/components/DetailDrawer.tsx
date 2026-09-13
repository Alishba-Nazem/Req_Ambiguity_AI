import { useState, type FormEvent } from "react"
import { CategoryLabel, SeverityBadge } from "./SeverityBadge"
import { replacementFor } from "../lib/document"
import { useAnalysis } from "../state/useAnalysis"

const WHY: Record<string, string> = {
  vague_term:
    "The highlighted wording has no measurable meaning. Two engineers can implement it differently and both still match the text.",
  missing_quantifier:
    "A quantity, limit, or frequency is missing, so the requirement cannot be tested as written.",
  undefined_actor:
    "The person, role, or system responsible is unnamed or too broad.",
  missing_edge_case:
    "The trigger or failure path is left to assumption. Edge cases will be implemented inconsistently.",
  conflicting_statement:
    "The sentence can be read more than one way, or stacks obligations without a priority.",
}

export function DetailDrawer() {
  const { result, drawerIssueId, openDrawer, setIssueStatus } = useAnalysis()
  const [question, setQuestion] = useState("")
  const [thread, setThread] = useState<{ role: "user" | "assistant"; text: string }[]>([])

  const issue = result?.issues.find((item) => item.id === drawerIssueId) ?? null
  if (!issue) return null

  function onAsk(event: FormEvent) {
    event.preventDefault()
    const text = question.trim()
    if (!text || !issue) return
    const reply = localReply(text, issue.category)
    setThread((current) => [
      ...current,
      { role: "user", text },
      { role: "assistant", text: reply },
    ])
    setQuestion("")
  }

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <button
        type="button"
        aria-label="Close details"
        className="h-full flex-1 bg-ink/20"
        onClick={() => openDrawer(null)}
      />
      <aside
        role="dialog"
        aria-labelledby="drawer-title"
        className="flex h-full w-full max-w-md flex-col border-l border-line bg-surface shadow-[0_0_0_1px_rgba(0,0,0,0.04)]"
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 id="drawer-title" className="text-[13px] font-semibold">
            Issue detail
          </h2>
          <button
            type="button"
            className="text-[13px] text-muted hover:text-ink"
            onClick={() => openDrawer(null)}
          >
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <div className="flex items-center gap-2">
            <CategoryLabel category={issue.category} />
            <SeverityBadge severity={issue.severity} />
          </div>
          <h3 className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">
            Original
          </h3>
          <p className="mt-1 text-[13px] leading-6">{issue.sentence}</p>
          <h3 className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">
            Why it is ambiguous
          </h3>
          <p className="mt-1 text-[13px] leading-6">{issue.explanation}</p>
          <h3 className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">
            Suggestion
          </h3>
          <p className="mt-1 text-[13px] leading-6">{replacementFor(issue)}</p>
          <p className="mt-3 text-[12px] text-muted">
            Confidence {Math.round(issue.confidence * 100)}%
            {issue.modelType ? ` · model type ${issue.modelType}` : null}
          </p>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              className="rounded bg-ink px-2.5 py-1 text-[12px] text-white"
              onClick={() => setIssueStatus(issue.id, "accepted")}
            >
              Accept
            </button>
            <button
              type="button"
              className="rounded border border-line px-2.5 py-1 text-[12px]"
              onClick={() => setIssueStatus(issue.id, "dismissed")}
            >
              Dismiss
            </button>
          </div>
          <section className="mt-6 border-t border-line pt-4">
            <h3 className="text-[13px] font-semibold">Ask about this issue</h3>
            <p className="mt-1 text-[12px] text-muted">
              Answers stay on this requirement. This is a local explanation, not a chat product.
            </p>
            <div className="mt-3 space-y-2">
              {thread.length === 0 ? (
                <p className="text-[13px] leading-6 text-ink">
                  <span className="font-medium">Why is this ambiguous? </span>
                  {WHY[issue.category]}
                </p>
              ) : null}
              {thread.map((entry, index) => (
                <p key={`${entry.role}-${index}`} className="text-[13px] leading-6">
                  <span className="font-medium">
                    {entry.role === "user" ? "You: " : "Note: "}
                  </span>
                  {entry.text}
                </p>
              ))}
            </div>
            <form className="mt-3 flex gap-2" onSubmit={onAsk}>
              <label htmlFor="issue-question" className="sr-only">
                Question about this issue
              </label>
              <input
                id="issue-question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask a follow-up"
                className="min-w-0 flex-1 rounded border border-line px-2 py-1 text-[13px]"
              />
              <button
                type="submit"
                className="rounded border border-line px-2 py-1 text-[12px]"
              >
                Ask
              </button>
            </form>
          </section>
        </div>
      </aside>
    </div>
  )
}

function localReply(question: string, category: string): string {
  const q = question.toLowerCase()
  if (q.includes("rewrite") || q.includes("suggest")) {
    return "Use a shall-statement with a named actor, a measurable limit, and an explicit condition. Avoid words like quickly, soon, or as needed."
  }
  if (q.includes("test") || q.includes("accept")) {
    return "A tester should be able to pass or fail the statement without asking the author what they meant."
  }
  return WHY[category] ?? "The wording leaves room for more than one valid implementation."
}
