export async function extractFileText(file: File): Promise<string> {
  const name = file.name.toLowerCase()
  if (name.endsWith(".txt") || file.type === "text/plain") {
    return file.text()
  }
  if (name.endsWith(".docx")) {
    const mammoth = await import("mammoth")
    const buffer = await file.arrayBuffer()
    const result = await mammoth.extractRawText({ arrayBuffer: buffer })
    return result.value.trim()
  }
  if (name.endsWith(".pdf") || file.type === "application/pdf") {
    return extractPdf(file)
  }
  throw new Error("Use a .txt, .docx, or .pdf file.")
}

async function extractPdf(file: File): Promise<string> {
  const pdfjs = await import("pdfjs-dist")
  const worker = await import("pdfjs-dist/build/pdf.worker.min.mjs?url")
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default
  const data = new Uint8Array(await file.arrayBuffer())
  const doc = await pdfjs.getDocument({ data }).promise
  const pages: string[] = []
  for (let pageNumber = 1; pageNumber <= doc.numPages; pageNumber += 1) {
    const page = await doc.getPage(pageNumber)
    const content = await page.getTextContent()
    const line = content.items
      .map((item) => ("str" in item ? item.str : ""))
      .join(" ")
    pages.push(line)
  }
  const text = pages.join("\n\n").replace(/[ \t]+/g, " ").trim()
  if (!text) {
    throw new Error("No text could be read from that PDF.")
  }
  return text
}

export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function exportDoc(filename: string, title: string, body: string): void {
  const escaped = escapeHtml(body).replace(/\n/g, "<br/>")
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title></head><body><h1>${escapeHtml(title)}</h1><p>${escaped}</p></body></html>`
  downloadBlob(
    filename,
    new Blob(["\ufeff", html], { type: "application/msword" }),
  )
}

export function printPdf(title: string, original: string, revised: string): void {
  const popup = window.open("", "_blank", "noopener,noreferrer,width=900,height=700")
  if (!popup) {
    throw new Error("Allow pop-ups to export a PDF.")
  }
  popup.document.write(`<!DOCTYPE html><html><head><title>${escapeHtml(title)}</title>
    <style>
      body { font-family: Segoe UI, Helvetica, Arial, sans-serif; margin: 32px; color: #1f2328; }
      h1 { font-size: 18px; }
      h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; color: #656d76; }
      pre { white-space: pre-wrap; font-family: inherit; font-size: 13px; line-height: 1.5; }
    </style></head><body>
    <h1>${escapeHtml(title)}</h1>
    <h2>Original</h2><pre>${escapeHtml(original)}</pre>
    <h2>Revised</h2><pre>${escapeHtml(revised)}</pre>
    </body></html>`)
  popup.document.close()
  popup.focus()
  popup.print()
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}
