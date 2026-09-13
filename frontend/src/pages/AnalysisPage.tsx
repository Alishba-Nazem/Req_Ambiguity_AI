import { ModelResultPanel } from "../components/ModelResultPanel"
import { useAnalysis } from "../state/useAnalysis"

export function AnalysisPage() {
  const { result, setView, status, error, analyze } = useAnalysis()

  if (status === "analyzing") {
    return (
      <div className="mx-auto max-w-[800px] px-4 py-10" role="status" aria-live="polite">
        <p className="text-[14px] text-muted">Analyzing requirement…</p>
        <p className="mt-1 text-[13px] text-muted">
          Checking for ambiguity and identifying unclear phrases.
        </p>
        <div className="mt-4 h-1 w-full overflow-hidden bg-line">
          <div className="h-full w-1/3 animate-pulse bg-primary" />
        </div>
      </div>
    )
  }

  if (status === "error" && !result) {
    return (
      <div className="mx-auto max-w-[800px] px-4 py-10 text-[14px]" role="alert">
        <p className="text-danger">{error ?? "The requirement could not be analyzed."}</p>
        <button type="button" className="mt-3 text-primary hover:underline" onClick={() => void analyze()}>
          Retry
        </button>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="mx-auto max-w-[800px] px-4 py-10 text-[14px] text-muted">
        <p>No analysis is open.</p>
        <button
          type="button"
          className="mt-3 text-primary hover:underline"
          onClick={() => setView("input")}
        >
          Analyze a requirement
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[800px] px-4 py-6">
      <p className="text-[12px] text-muted">
        Workspace / Analysis / {result.requirementId}
      </p>
      {error ? (
        <div className="mt-3 text-[13px] text-danger" role="alert">
          <p>{error}</p>
          <button type="button" className="mt-2 text-primary hover:underline" onClick={() => void analyze()}>
            Retry
          </button>
        </div>
      ) : null}
      <div className="mt-4">
        <ModelResultPanel />
      </div>
    </div>
  )
}
