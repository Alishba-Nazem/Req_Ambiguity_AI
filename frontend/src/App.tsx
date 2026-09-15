import { useEffect } from "react"
import { AppHeader } from "./components/AppHeader"
import { AnalysisPage } from "./pages/AnalysisPage"
import { CreatePage } from "./pages/CreatePage"
import { DashboardPage } from "./pages/DashboardPage"
import { HistoryPage } from "./pages/HistoryPage"
import { InputPage } from "./pages/InputPage"
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
        {view === "dashboard" ? <DashboardPage /> : null}
        {view === "input" ? <InputPage /> : null}
        {view === "create" ? <CreatePage /> : null}
        {view === "analysis" ? <AnalysisPage /> : null}
        {view === "history" ? <HistoryPage /> : null}
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
    </div>
  )
}
