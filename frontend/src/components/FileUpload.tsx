import { useState, type DragEvent, type ChangeEvent } from "react"
import { extractFileText } from "../lib/export"
import { countWords } from "../lib/document"
import { useAnalysis } from "../state/useAnalysis"

export function FileUpload() {
  const { fileName, draftText, setFile, status } = useAnalysis()
  const [dragOver, setDragOver] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const analyzing = status === "analyzing"

  async function loadFile(file: File) {
    setLocalError(null)
    try {
      const text = await extractFileText(file)
      if (!text.trim()) {
        setLocalError("That file did not contain readable text.")
        return
      }
      setFile(file.name, text)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not read that file."
      setLocalError(message)
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragOver(false)
    const file = event.dataTransfer.files[0]
    if (file) void loadFile(file)
  }

  function onChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) void loadFile(file)
    event.target.value = ""
  }

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`rounded border border-dashed px-4 py-10 text-center ${
          dragOver ? "border-ink bg-low-bg" : "border-line bg-surface"
        }`}
      >
        <p className="text-[13px] font-medium">Drop a requirements file</p>
        <p className="mt-1 text-[12px] text-muted">.txt, .docx, or .pdf</p>
        <label className="mt-4 inline-flex cursor-pointer rounded border border-line bg-surface px-3 py-1.5 text-[13px] hover:bg-low-bg">
          Browse
          <input
            type="file"
            accept=".txt,.docx,.pdf,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="sr-only"
            disabled={analyzing}
            onChange={onChange}
          />
        </label>
      </div>
      {fileName ? (
        <div className="mt-3 rounded border border-line bg-surface px-3 py-2 text-[13px]">
          <p className="font-medium">{fileName}</p>
          <p className="text-[12px] text-muted">
            {countWords(draftText)} words extracted
          </p>
        </div>
      ) : null}
      {localError ? (
        <p className="mt-2 text-[13px] text-critical" role="alert">
          {localError}
        </p>
      ) : null}
    </div>
  )
}
