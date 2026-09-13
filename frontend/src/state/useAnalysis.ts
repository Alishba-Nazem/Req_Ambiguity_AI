import { useContext } from "react"
import { AnalysisContext, type AnalysisContextValue } from "./AnalysisContext"

export type { AnalysisContextValue }

export function useAnalysis(): AnalysisContextValue {
  const value = useContext(AnalysisContext)
  if (!value) {
    throw new Error("useAnalysis must be used within AnalysisProvider")
  }
  return value
}
