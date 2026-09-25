import { useEffect, useState } from "react"
import { AppHeader } from "./components/AppHeader"
import { AnalysisPage } from "./pages/AnalysisPage"
import { CreatePage } from "./pages/CreatePage"
import { DashboardPage } from "./pages/DashboardPage"
import { HistoryPage } from "./pages/HistoryPage"
import { InputPage } from "./pages/InputPage"
import { PublicPage } from "./pages/PublicPage"
import { AnalysisProvider } from "./state/AnalysisContext"
import { useAnalysis } from "./state/useAnalysis"

export default function App() {
  return (
    <AnalysisProvider>
      <Shell />
    </AnalysisProvider>
  )
}

function Shell() {
  const { view, toast, setToast } = useAnalysis()
  const [path, setPath] = useState(() => window.location.pathname)

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname)
    window.addEventListener("popstate", onPopState)
    return () => window.removeEventListener("popstate", onPopState)
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 2800)
    return () => window.clearTimeout(timer)
  }, [toast, setToast])

  return (
    <div className="min-h-screen bg-background text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:bg-surface focus:px-2 focus:py-1"
      >
        Skip to content
      </a>
      <AppHeader />
      <main id="main">
        {path === "/analyze" && view !== "analysis" ? <InputPage /> : null}
        {path === "/analyze" && view === "analysis" ? <AnalysisPage /> : null}
        {path.startsWith("/learn/") || ["/about", "/privacy", "/terms"].includes(path) ? (
          <PublicPage path={path} />
        ) : null}
        {!path.startsWith("/learn/") && !["/about", "/privacy", "/terms", "/analyze"].includes(path) ? (
          <>
            {view === "dashboard" ? <DashboardPage /> : null}
            {view === "input" ? <InputPage /> : null}
            {view === "create" ? <CreatePage /> : null}
            {view === "analysis" ? <AnalysisPage /> : null}
            {view === "history" ? <HistoryPage /> : null}
          </>
        ) : null}
      </main>
      {toast ? (
        <div
          role="status"
          className="no-print fixed bottom-4 left-4 right-4 border border-line bg-surface px-3 py-2 text-[13px] shadow-sm sm:left-auto sm:right-4 sm:max-w-sm"
          style={{ bottom: "max(1rem, env(safe-area-inset-bottom))" }}
        >
          {toast}
        </div>
      ) : null}
      <footer className="border-t border-line bg-surface px-4 py-5 text-[12px] text-muted">
        <div className="mx-auto flex max-w-[1100px] flex-wrap items-center justify-between gap-3">
          <span>Requirement Ambiguity AI · Created by Alishba Nazem</span>
          <nav aria-label="Site information" className="flex flex-wrap gap-3">
            <a href="/learn/what-is-requirement-ambiguity" className="hover:text-ink">Learn</a>
            <a href="/privacy" className="hover:text-ink">Privacy</a>
            <a href="/terms" className="hover:text-ink">Terms</a>
          </nav>
        </div>
      </footer>
    </div>
  )
}
