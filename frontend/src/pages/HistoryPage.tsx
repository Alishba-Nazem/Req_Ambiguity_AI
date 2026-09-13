import { useAnalysis } from "../state/useAnalysis"

export function HistoryPage() {
  const { history, openHistoryItem, setView } = useAnalysis()

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <p className="text-[12px] text-muted">Workspace / History</p>
      <h1 className="mt-1 text-[22px] font-semibold">Analysis history</h1>
      {history.length === 0 ? (
        <div className="mt-6 border border-dashed border-line bg-surface px-4 py-8 text-[13px] text-muted">
          <p>No analyses yet.</p>
          <button
            type="button"
            className="mt-3 text-primary hover:underline"
            onClick={() => setView("input")}
          >
            Analyze a requirement
          </button>
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto border border-line bg-surface">
          <table className="min-w-full text-left text-[13px]">
            <thead className="border-b border-line bg-background text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">ID</th>
                <th className="px-3 py-2 font-medium">Requirement</th>
                <th className="px-3 py-2 font-medium">Score</th>
                <th className="px-3 py-2 font-medium">Req. type</th>
                <th className="px-3 py-2 font-medium">Ambiguity</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr
                  key={item.id}
                  className="cursor-pointer border-b border-line last:border-0 hover:bg-background"
                  tabIndex={0}
                  onClick={() => openHistoryItem(item.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      openHistoryItem(item.id)
                    }
                  }}
                >
                  <td className="px-3 py-2 font-mono text-[12px] text-primary">
                    {item.id}
                  </td>
                  <td className="max-w-[320px] truncate px-3 py-2">{item.requirement}</td>
                  <td className="px-3 py-2">
                    {item.score != null ? `${item.score.toFixed(1)} / 10` : "—"}
                  </td>
                  <td className="px-3 py-2">{item.requirementType ?? "—"}</td>
                  <td className="px-3 py-2">{item.ambiguityType ?? "—"}</td>
                  <td className="px-3 py-2">{item.status}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-muted">{item.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
