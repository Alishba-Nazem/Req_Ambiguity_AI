import { FileUpload } from "../components/FileUpload"
import { RequirementInput } from "../components/RequirementInput"
import { countWords } from "../lib/document"
import { useAnalysis } from "../state/useAnalysis"

export function InputPage() {
  const { analyze, status, error, draftText, setInputMode, inputMode } = useAnalysis()
  const analyzing = status === "analyzing"
  const canAnalyze = draftText.trim().length > 0 && !analyzing
  const words = countWords(draftText)

  return (
    <div className="mx-auto max-w-[720px] px-4 py-8">
      <p className="text-[12px] text-muted">Workspace / Analyze requirement</p>
      <h1 className="mt-1 text-[22px] font-semibold">Analyze requirement</h1>
      <p className="mt-2 text-[14px] text-muted">
        Paste one requirement. The result shows the score, the unclear phrase,
        and a rewrite you can accept or edit.
      </p>

      <div className="mt-5 flex gap-3 text-[13px]">
        <button
          type="button"
          className={inputMode === "paste" ? "font-semibold text-primary" : "text-muted"}
          onClick={() => setInputMode("paste")}
        >
          Paste
        </button>
        <button
          type="button"
          className={inputMode === "upload" ? "font-semibold text-primary" : "text-muted"}
          onClick={() => setInputMode("upload")}
        >
          Upload
        </button>
      </div>

      <div className="mt-3 border border-line bg-surface p-3">
        {inputMode === "paste" ? <RequirementInput /> : <FileUpload />}
        <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
          <p className="text-[12px] text-muted">
            {words} {words === 1 ? "word" : "words"}
          </p>
          <button
            type="button"
            disabled={!canAnalyze}
            onClick={() => void analyze()}
            className="bg-primary px-3 py-1.5 text-[13px] font-medium text-white hover:bg-primary-hover disabled:cursor-not-allowed disabled:bg-line-strong"
          >
            {analyzing ? "Analyzing requirement…" : "Analyze"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-4 text-[13px] text-danger" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="mt-2 text-primary hover:underline"
            onClick={() => void analyze()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {analyzing ? (
        <p className="mt-4 text-[13px] text-muted" role="status">
          Checking for ambiguity and identifying unclear phrases…
        </p>
      ) : null}
    </div>
  )
}
