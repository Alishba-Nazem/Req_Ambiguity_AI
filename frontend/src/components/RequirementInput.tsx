import { SAMPLE_REQUIREMENTS } from "../api/mockAnalyzer"
import { countWords } from "../lib/document"
import { useAnalysis } from "../state/useAnalysis"

export function RequirementInput() {
  const { draftText, setDraftText, status } = useAnalysis()
  const words = countWords(draftText)
  const chars = draftText.length
  const analyzing = status === "analyzing"

  return (
    <div>
      <label htmlFor="requirement-editor" className="sr-only">
        Requirement text
      </label>
      <textarea
        id="requirement-editor"
        value={draftText}
        onChange={(event) => setDraftText(event.target.value)}
        disabled={analyzing}
        spellCheck={false}
        placeholder="Paste software requirements here. One statement per line works well, for example: The system shall respond to user requests within 2 seconds."
        className="min-h-[220px] w-full resize-y border-0 bg-transparent p-0 font-sans text-[16px] leading-7 text-ink outline-none placeholder:text-muted"
      />
      <div className="sr-only">
        {words} words · {chars} characters
      </div>
      <button
        type="button"
        className="mt-2 text-[13px] text-muted hover:text-ink"
        onClick={() => setDraftText(SAMPLE_REQUIREMENTS)}
      >
        Try a sample requirement
      </button>
    </div>
  )
}
