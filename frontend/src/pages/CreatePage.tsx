import { useState } from "react"
import { REQUIREMENT_KIND_LABELS, type RequirementKind } from "../types"
import { useAnalysis } from "../state/useAnalysis"

const KINDS = Object.keys(REQUIREMENT_KIND_LABELS) as RequirementKind[]

export function CreatePage() {
  const {
    createIdea,
    createType,
    createDetails,
    createResult,
    status,
    error,
    setCreateIdea,
    setCreateType,
    setCreateDetails,
    generateRequirementFromIdea,
    useGeneratedRequirement,
    analyzeGeneratedRequirement,
    setCreateSuggestion,
  } = useAnalysis()
  const [editingGenerated, setEditingGenerated] = useState(false)
  const generating = status === "generating"
  const canGenerate = createIdea.trim().length > 0 && !generating
  const checks = createResult?.qualityChecks ?? []
  const failed = checks.filter((item) => !item.passed)
  const passed = checks.filter((item) => item.passed).slice(0, 3)

  return (
    <div className="mx-auto max-w-[720px] px-4 py-8">
      <p className="text-[12px] text-muted">Workspace / Create requirement</p>
      <h1 className="mt-1 text-[22px] font-semibold">Create requirement</h1>
      <p className="mt-2 text-[14px] text-muted">
        Describe the intended behavior in everyday language. We rewrite it as a
        single testable shall-statement.
      </p>

      <label htmlFor="idea" className="mt-6 block text-[12px] font-semibold text-muted">
        What do you want the system to do?
      </label>
      <textarea
        id="idea"
        value={createIdea}
        onChange={(event) => setCreateIdea(event.target.value)}
        rows={5}
        className="mt-1 w-full border border-line bg-surface px-3 py-2 text-[14px] leading-6"
        placeholder='Users should be able to reset their password using their email.'
      />

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="kind" className="block text-[12px] font-semibold text-muted">
            Requirement type
          </label>
          <select
            id="kind"
            value={createType}
            onChange={(event) =>
              setCreateType(event.target.value as RequirementKind | "")
            }
            className="mt-1 w-full border border-line bg-surface px-3 py-2 text-[14px]"
          >
            <option value="">Let the assistant choose</option>
            {KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {REQUIREMENT_KIND_LABELS[kind]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="details" className="block text-[12px] font-semibold text-muted">
            Optional details
          </label>
          <input
            id="details"
            value={createDetails}
            onChange={(event) => setCreateDetails(event.target.value)}
            className="mt-1 w-full border border-line bg-surface px-3 py-2 text-[14px]"
            placeholder="Actors, limits, conditions"
          />
        </div>
      </div>

      <button
        type="button"
        disabled={!canGenerate}
        onClick={() => void generateRequirementFromIdea()}
        className="mt-5 bg-primary px-3 py-2 text-[13px] font-medium text-white hover:bg-primary-hover disabled:cursor-not-allowed disabled:bg-line-strong"
      >
        {generating ? "Generating requirement…" : "Generate requirement"}
      </button>

      {error ? (
        <p className="mt-3 text-[13px] text-danger" role="alert">
          {error}
        </p>
      ) : null}

      {createResult ? (
        <section className="mt-8 border-t border-line pt-6">
          <h2 className="text-[12px] font-semibold uppercase tracking-wide text-muted">
            Generated requirement
          </h2>
          {editingGenerated ? (
            <textarea
              aria-label="Edit generated requirement"
              value={createResult.suggestedRequirement}
              onChange={(event) => setCreateSuggestion(event.target.value)}
              rows={4}
              className="mt-2 w-full border border-line bg-surface px-3 py-2 text-[15px] leading-7"
            />
          ) : (
            <p className="mt-2 text-[16px] leading-7">{createResult.suggestedRequirement}</p>
          )}
          <p className="mt-2 text-[13px] text-muted">
            Requirement type: {REQUIREMENT_KIND_LABELS[createResult.requirementType]}
          </p>
          <p className="mt-3 text-[14px] leading-6">{createResult.explanation}</p>

          {passed.length + failed.length > 0 ? (
            <ul className="mt-4 space-y-1 text-[13px]">
              {passed.map((item) => (
                <li key={item.id} className="text-success">
                  ✓ {item.label}
                </li>
              ))}
              {failed.map((item) => (
                <li key={item.id} className="text-warning">
                  ⚠ {item.detail ?? item.label}
                </li>
              ))}
            </ul>
          ) : null}

          {createResult.missingInformation.length > 0 ? (
            <div className="mt-4">
              <h3 className="text-[12px] font-semibold text-muted">Missing information</h3>
              <ul className="mt-1 list-disc pl-5 text-[13px] leading-6">
                {createResult.missingInformation.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-2">
            <button
              type="button"
              className="bg-primary px-3 py-1.5 text-[13px] text-white hover:bg-primary-hover"
              onClick={() => useGeneratedRequirement()}
            >
              Use requirement
            </button>
            <button
              type="button"
              className="border border-line px-3 py-1.5 text-[13px] hover:bg-background"
              onClick={() => setEditingGenerated((value) => !value)}
            >
              {editingGenerated ? "Done editing" : "Edit"}
            </button>
            <button
              type="button"
              className="px-3 py-1.5 text-[13px] text-muted hover:text-ink"
              onClick={() => analyzeGeneratedRequirement()}
            >
              Analyze
            </button>
          </div>
        </section>
      ) : null}
    </div>
  )
}
