import { diffWords } from "../lib/document"

export function DiffViewer({
  original,
  revised,
}: {
  original: string
  revised: string
}) {
  const unchanged = original === revised
  const tokens = diffWords(original, revised)

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded border border-line bg-surface">
        <h2 className="border-b border-line px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
          Original
        </h2>
        <pre className="whitespace-pre-wrap p-3 font-sans text-[13px] leading-6">
          {original}
        </pre>
      </section>
      <section className="rounded border border-line bg-surface">
        <h2 className="border-b border-line px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
          Revised
        </h2>
        <div className="whitespace-pre-wrap p-3 font-sans text-[13px] leading-6">
          {unchanged ? (
            <span className="text-muted">No accepted changes yet.</span>
          ) : (
            tokens.map((token, index) => {
              if (token.kind === "equal") {
                return <span key={`${token.value}-${index}`}>{token.value}</span>
              }
              if (token.kind === "del") {
                return (
                  <del key={`${token.value}-${index}`} className="diff-del">
                    {token.value}
                  </del>
                )
              }
              return (
                <ins key={`${token.value}-${index}`} className="diff-add no-underline">
                  {token.value}
                </ins>
              )
            })
          )}
        </div>
      </section>
    </div>
  )
}
