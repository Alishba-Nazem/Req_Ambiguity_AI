import { useState } from "react"
import { exportDoc, printPdf } from "../lib/export"
import { useAnalysis } from "../state/useAnalysis"

export function ExportActions() {
  const { result, revisedText, setToast } = useAnalysis()
  const [approvalOpen, setApprovalOpen] = useState(false)
  if (!result) return null

  async function copy() {
    await navigator.clipboard.writeText(revisedText)
    setToast("Revised requirements copied.")
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        className="rounded border border-line bg-surface px-2.5 py-1 text-[13px]"
        onClick={() => printPdf("Requirement review", result.originalText, revisedText)}
      >
        Export PDF
      </button>
      <button
        type="button"
        className="rounded border border-line bg-surface px-2.5 py-1 text-[13px]"
        onClick={() =>
          exportDoc("requirements.doc", "Revised requirements", revisedText)
        }
      >
        Export DOCX
      </button>
      <button
        type="button"
        className="rounded border border-line bg-surface px-2.5 py-1 text-[13px]"
        onClick={() => void copy()}
      >
        Copy to clipboard
      </button>
      <button
        type="button"
        className="rounded px-2.5 py-1 text-[13px] text-muted hover:text-ink"
        onClick={() => setApprovalOpen(true)}
      >
        Send for approval
      </button>
      {approvalOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30 p-4">
          <div
            role="dialog"
            aria-labelledby="approval-title"
            className="w-full max-w-sm rounded border border-line bg-surface p-4"
          >
            <h2 id="approval-title" className="text-[14px] font-semibold">
              Send for approval
            </h2>
            <p className="mt-2 text-[13px] leading-6 text-muted">
              This workspace has no reviewers configured. Connect an approval
              channel later; nothing was sent.
            </p>
            <button
              type="button"
              className="mt-4 rounded bg-ink px-3 py-1.5 text-[13px] text-white"
              onClick={() => setApprovalOpen(false)}
            >
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
