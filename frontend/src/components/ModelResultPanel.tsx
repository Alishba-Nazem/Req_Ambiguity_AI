import { useState } from "react"
import { HighlightedRequirement } from "./HighlightedRequirement"
import { SuggestionEditor } from "./SuggestionEditor"
import { useAnalysis } from "../state/useAnalysis"
import { MODEL_TYPE_LABELS } from "../types"

function scoreTone(score: number | null | undefined) {
  // Clarity score: higher is better.
  if (score == null) return "text-muted"
  if (score >= 8) return "text-success"
  if (score >= 6) return "text-warning"
  return "text-danger"
}

function renderWithPlaceholders(text: string) {
  const parts = text.split(/(\[[^\]]+\])/g)
  return parts.map((part, index) =>
    part.startsWith("[") && part.endsWith("]") ? (
      <mark
        key={`${part}-${index}`}
        className="bg-warning-bg px-0.5 font-medium text-ink"
      >
        {part}
      </mark>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    ),
  )
}

export function ModelResultPanel() {
  const {
    result,
    revisedText,
    selectedIssueId,
    selectIssue,
    setIssueStatus,
    setEditing,
    editingIssueId,
    revertAll,
  } = useAnalysis()
  const [showDetails, setShowDetails] = useState(false)
  if (!result) return null

  const user = result.userAssessment
  const needsWork =
    user?.status === "needs_improvement" ||
    (user?.status !== "clear" && result.overallStatus === "ambiguous")
  const phrases = user?.phrases ?? []
  const openIssues = result.issues.filter((issue) => issue.status === "open")
  const selectedOpen =
    openIssues.find((issue) => issue.id === selectedIssueId) ?? null
  const primary = selectedOpen ?? openIssues[0] ?? result.issues[0] ?? null
  const editing = primary !== null && editingIssueId === primary.id
  const acceptedOrEdited = result.issues.some(
    (issue) => issue.status === "accepted" || issue.status === "edited",
  )
  const allResolved =
    result.issues.length > 0 &&
    result.issues.every((issue) => issue.status !== "open")
  const allDismissed =
    result.issues.length > 0 &&
    result.issues.every((issue) => issue.status === "dismissed")
  const suggestion =
    user?.suggested_requirement ?? result.suggestedRequirement ?? primary?.suggestion ?? null
  const score =
    user?.clarity_score ?? user?.score ?? result.clarityScore ?? result.finalScore
  const reqType = user?.requirement_type_label ?? "—"
  const ambType =
    user?.type_label ??
    (result.ambiguityType ? MODEL_TYPE_LABELS[result.ambiguityType] : "—")
  const missing = user?.missing_information ?? result.missingInformation ?? []
  const why = phrases[0]?.why ?? user?.why ?? null
  const specify = phrases[0]?.specify ?? missing[0] ?? null
  const showIssueCopy = needsWork && !allResolved
  const highlightIssues = allResolved ? [] : openIssues
  const barWidth =
    score == null ? 0 : Math.min(100, Math.max(0, score * 10))
  const barColor =
    score == null
      ? "bg-line"
      : score >= 8
        ? "bg-success"
        : score >= 6
          ? "bg-warning"
          : "bg-danger"

  return (
    <article>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-semibold">Requirement analysis</h1>
          <p className="mt-1 text-[13px] text-muted">{result.requirementId}</p>
        </div>
        <p
          className={`text-[13px] font-semibold ${
            needsWork && !allResolved ? "text-warning" : "text-success"
          }`}
        >
          {acceptedOrEdited && allResolved
            ? "Updated"
            : allDismissed
              ? "Suggestion dismissed"
              : user?.title ?? (needsWork ? "Needs improvement" : "Clear")}
        </p>
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-x-4 gap-y-3 text-[13px] sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Requirement quality
          </dt>
          <dd className={`mt-1 text-[22px] font-semibold ${scoreTone(score)}`}>
            {score != null ? `${score.toFixed(1)} / 10` : "—"}
          </dd>
          <dd className="text-[12px] text-muted">{user?.score_label ?? ""}</dd>
          {score != null ? (
            <div
              className="mt-2 h-1.5 w-full bg-line"
              role="meter"
              aria-label="Requirement quality score"
              aria-valuemin={0}
              aria-valuemax={10}
              aria-valuenow={Number(score.toFixed(1))}
            >
              <div
                className={`h-full ${barColor}`}
                style={{ width: `${barWidth}%` }}
              />
            </div>
          ) : null}
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Requirement type
          </dt>
          <dd className="mt-1 font-medium">{reqType}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Ambiguity type
          </dt>
          <dd className="mt-1 font-medium">
            {needsWork && !allResolved ? ambType : "None"}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Status
          </dt>
          <dd className="mt-1 font-medium">
            {acceptedOrEdited && allResolved
              ? "Accepted"
              : allDismissed
                ? "Dismissed"
                : needsWork
                  ? "Needs improvement"
                  : "Clear"}
          </dd>
        </div>
      </dl>

      {result.generatedText &&
      result.generatedText.trim() !== result.originalText.trim() ? (
        <>
          <section className="mt-6">
            <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              Original requirement
            </h2>
            <p className="mt-1 text-[15px] leading-7">{result.originalText}</p>
          </section>
          <section className="mt-5">
            <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              Generated requirement
            </h2>
            <div className="mt-1">
              <HighlightedRequirement
                text={result.generatedText}
                issues={highlightIssues}
                selectedIssueId={selectedIssueId}
                onSelect={selectIssue}
              />
            </div>
          </section>
        </>
      ) : (
        <section className="mt-6">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Original requirement
          </h2>
          <div className="mt-1">
            <HighlightedRequirement
              text={result.originalText}
              issues={highlightIssues}
              selectedIssueId={selectedIssueId}
              onSelect={selectIssue}
            />
          </div>
        </section>
      )}

      {showIssueCopy && phrases.length > 0 ? (
        <section className="mt-5">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            {phrases.length === 1 ? "Issue" : "Issues"}
          </h2>
          <ul className="mt-1 space-y-2 text-[14px] leading-6">
            {phrases.map((phrase) => (
              <li key={`${phrase.text}-${phrase.start}`}>
                <p>
                  “{phrase.text}”
                  {phrase.type_label ? (
                    <span className="ml-2 text-[12px] text-muted">· {phrase.type_label}</span>
                  ) : null}
                </p>
                {phrases.length > 1 ? (
                  <p className="mt-0.5 text-[13px] text-muted">{phrase.why}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {showIssueCopy && why && phrases.length <= 1 ? (
        <section className="mt-5">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Why it is ambiguous
          </h2>
          <p className="mt-1 text-[14px] leading-6">{why}</p>
        </section>
      ) : null}

      {showIssueCopy && specify ? (
        <section className="mt-5">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            What to specify
          </h2>
          <p className="mt-1 text-[14px] leading-6">{specify}</p>
        </section>
      ) : null}

      {suggestion && needsWork && !allResolved ? (
        <section className="mt-5">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Suggested rewrite
          </h2>
          {editing && primary ? (
            <SuggestionEditor
              key={primary.id}
              issue={primary}
              initialText={primary.editedText ?? suggestion}
            />
          ) : (
            <p className="mt-1 text-[15px] leading-7">
              {renderWithPlaceholders(primary?.editedText ?? suggestion)}
            </p>
          )}
          {primary && !editing ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {primary.status === "open" ? (
                <>
                  <button
                    type="button"
                    className="bg-primary px-2.5 py-1.5 text-[13px] text-white hover:bg-primary-hover"
                    onClick={() => setIssueStatus(primary.id, "accepted")}
                  >
                    Accept suggestion
                  </button>
                  <button
                    type="button"
                    className="border border-line bg-surface px-2.5 py-1.5 text-[13px]"
                    onClick={() => setEditing(primary.id)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="px-2.5 py-1.5 text-[13px] text-muted hover:text-ink"
                    onClick={() => setIssueStatus(primary.id, "dismissed")}
                  >
                    Dismiss
                  </button>
                </>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {acceptedOrEdited && revisedText !== result.originalText ? (
        <section className="mt-5 border-t border-line pt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              Current requirement
            </h2>
            {allResolved ? (
              <button
                type="button"
                className="text-[13px] text-primary hover:underline"
                onClick={() => revertAll()}
              >
                Undo
              </button>
            ) : null}
          </div>
          <p className="mt-1 text-[15px] leading-7">{revisedText}</p>
        </section>
      ) : null}

      <button
        type="button"
        className="mt-6 text-[12px] text-muted hover:text-ink hover:underline"
        aria-expanded={showDetails}
        onClick={() => setShowDetails((value) => !value)}
      >
        {showDetails ? "Hide technical details" : "Technical details"}
      </button>
      {showDetails ? (
        <div className="mt-2 border border-line bg-background px-3 py-2 text-[12px] leading-5 text-muted">
          <p>Overall result: {result.overallStatus}</p>
          <p>Requirement quality: {result.clarityScore ?? result.finalScore ?? "—"} / 10</p>
          <p>
            Fused ambiguity: {result.fusedAmbiguityScore ?? "—"} / 10
          </p>
          <p>
            Flagged phrases:{" "}
            {result.issues.map((issue) => issue.phrase).filter(Boolean).join(", ") ||
              "none"}
          </p>
        </div>
      ) : null}
    </article>
  )
}
