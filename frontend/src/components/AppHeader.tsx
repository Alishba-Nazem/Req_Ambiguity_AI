import { useAnalysis } from "../state/useAnalysis"
import type { AppView } from "../types"

const LINKS: { view: AppView; label: string }[] = [
  { view: "dashboard", label: "Dashboard" },
  { view: "create", label: "Create" },
  { view: "input", label: "Analyze" },
  { view: "history", label: "History" },
]

export function AppHeader() {
  const { view, setView, result } = useAnalysis()

  return (
    <header className="no-print sticky top-0 z-20 border-b border-line bg-surface">
      <div className="mx-auto flex min-h-12 max-w-[1100px] flex-wrap items-center justify-between gap-2 px-4 py-2">
        <button
          type="button"
          className="text-[14px] font-semibold text-ink"
          onClick={() => setView("dashboard")}
        >
          Requirement Ambiguity AI
        </button>
        <nav
          aria-label="Workspace"
          className="flex max-w-full flex-wrap items-center gap-1 text-[13px]"
        >
          {LINKS.map((link) => (
            <button
              key={link.view}
              type="button"
              aria-current={view === link.view ? "page" : undefined}
              onClick={() => setView(link.view)}
              className={`px-2.5 py-1 ${
                view === link.view
                  ? "bg-primary/10 font-medium text-primary"
                  : "text-muted hover:bg-background hover:text-ink"
              }`}
            >
              {link.label}
            </button>
          ))}
          {result ? (
            <button
              type="button"
              aria-current={view === "analysis" ? "page" : undefined}
              onClick={() => setView("analysis")}
              className={`px-2.5 py-1 ${
                view === "analysis"
                  ? "bg-primary/10 font-medium text-primary"
                  : "text-muted hover:text-ink"
              }`}
            >
              {result.requirementId}
            </button>
          ) : null}
          <a className="px-2.5 py-1 text-muted hover:text-ink" href="/learn/what-is-requirement-ambiguity">
            Learn
          </a>
          <a className="px-2.5 py-1 text-muted hover:text-ink" href="/about">
            About
          </a>
        </nav>
      </div>
    </header>
  )
}
