import {
  createContext,
  useCallback,
  useMemo,
  useReducer,
  type ReactNode,
} from "react"
import { analyzeDocument, generateRequirement } from "../api/client"
import { buildRevisedText } from "../lib/document"
import type {
  AnalysisIssue,
  AnalysisResult,
  AppView,
  GenerateResult,
  HistoryItem,
  InputMode,
  IssueFilter,
  IssueStatus,
  RequirementKind,
} from "../types"

interface AnalysisState {
  view: AppView
  inputMode: InputMode
  draftText: string
  fileName: string | null
  result: AnalysisResult | null
  selectedIssueId: string | null
  drawerIssueId: string | null
  editingIssueId: string | null
  filter: IssueFilter
  status: "idle" | "analyzing" | "generating" | "ready" | "error"
  error: string | null
  toast: string | null
  mobileIssuesOpen: boolean
  createIdea: string
  createType: RequirementKind | ""
  createDetails: string
  createResult: GenerateResult | null
  history: HistoryItem[]
  nextReq: number
}

type Action =
  | { type: "set-view"; view: AppView }
  | { type: "set-input-mode"; mode: InputMode }
  | { type: "set-draft"; text: string }
  | { type: "set-file"; name: string | null; text: string }
  | { type: "analyze-start" }
  | { type: "analyze-success"; result: AnalysisResult }
  | { type: "analyze-error"; error: string }
  | { type: "select-issue"; id: string | null }
  | { type: "open-drawer"; id: string | null }
  | { type: "set-filter"; filter: IssueFilter }
  | { type: "set-status"; id: string; status: IssueStatus; editedText?: string | null }
  | { type: "set-editing"; id: string | null }
  | { type: "accept-all" }
  | { type: "revert-all" }
  | { type: "set-toast"; message: string | null }
  | { type: "set-mobile-issues"; open: boolean }
  | { type: "set-create-idea"; text: string }
  | { type: "set-create-type"; value: RequirementKind | "" }
  | { type: "set-create-details"; text: string }
  | { type: "generate-start" }
  | { type: "generate-success"; result: GenerateResult }
  | { type: "generate-error"; error: string }
  | { type: "open-history"; id: string }
  | { type: "set-create-suggestion"; text: string }

const initialState: AnalysisState = {
  view: "dashboard",
  inputMode: "paste",
  draftText: "",
  fileName: null,
  result: null,
  selectedIssueId: null,
  drawerIssueId: null,
  editingIssueId: null,
  filter: "all",
  status: "idle",
  error: null,
  toast: null,
  mobileIssuesOpen: false,
  createIdea: "",
  createType: "",
  createDetails: "",
  createResult: null,
  history: [],
  nextReq: 1,
}

function nextId(n: number) {
  return `REQ-${String(n).padStart(3, "0")}`
}

function toHistory(result: AnalysisResult): HistoryItem {
  const user = result.userAssessment
  return {
    id: result.requirementId,
    requirement: result.displayText || result.originalText,
    score: user?.score ?? result.finalScore,
    requirementType: user?.requirement_type_label ?? null,
    ambiguityType: user?.type_label ?? result.ambiguityType,
    status: user?.title ?? (result.overallStatus === "clean" ? "Clear" : "Needs improvement"),
    date: new Date().toLocaleString(),
    snapshot: result,
  }
}

function applyDisplayText(
  result: AnalysisResult,
  issues: AnalysisIssue[],
  suggestion: string | null,
): AnalysisResult {
  const revised = buildRevisedText(result.originalText, issues, suggestion)
  return { ...result, issues, displayText: revised }
}

function reducer(state: AnalysisState, action: Action): AnalysisState {
  switch (action.type) {
    case "set-view":
      return { ...state, view: action.view, mobileIssuesOpen: false, error: null }
    case "set-input-mode":
      return { ...state, inputMode: action.mode }
    case "set-draft":
      return { ...state, draftText: action.text, error: null }
    case "set-file":
      return {
        ...state,
        fileName: action.name,
        draftText: action.text,
        inputMode: "upload",
        error: null,
      }
    case "analyze-start":
      return { ...state, status: "analyzing", error: null, toast: null }
    case "analyze-success": {
      const id = action.result.requirementId || nextId(state.nextReq)
      const result = {
        ...action.result,
        requirementId: id,
        displayText: action.result.displayText || action.result.originalText,
      }
      const item = toHistory(result)
      return {
        ...state,
        status: "ready",
        result,
        view: "analysis",
        selectedIssueId: result.issues[0]?.id ?? null,
        drawerIssueId: null,
        editingIssueId: null,
        nextReq: action.result.requirementId ? state.nextReq : state.nextReq + 1,
        history: [item, ...state.history.filter((row) => row.id !== id)].slice(0, 40),
      }
    }
    case "analyze-error":
      return { ...state, status: "error", error: action.error }
    case "select-issue":
      return { ...state, selectedIssueId: action.id, mobileIssuesOpen: true }
    case "open-drawer":
      return { ...state, drawerIssueId: action.id, selectedIssueId: action.id ?? state.selectedIssueId }
    case "set-filter":
      return { ...state, filter: action.filter }
    case "set-editing":
      return { ...state, editingIssueId: action.id }
    case "set-toast":
      return { ...state, toast: action.message }
    case "set-mobile-issues":
      return { ...state, mobileIssuesOpen: action.open }
    case "set-status": {
      if (!state.result) return state
      const suggestion =
        state.result.userAssessment?.suggested_requirement ??
        state.result.suggestedRequirement
      const issues = state.result.issues.map((issue) =>
        issue.id === action.id
          ? {
              ...issue,
              status: action.status,
              editedText:
                action.editedText !== undefined ? action.editedText : issue.editedText,
            }
          : issue,
      )
      const result = applyDisplayText({ ...state.result, issues }, issues, suggestion)
      const toast =
        action.status === "accepted"
          ? "Suggestion accepted."
          : action.status === "edited"
            ? "Edited requirement saved."
            : action.status === "dismissed"
              ? "Suggestion dismissed."
              : null
      return {
        ...state,
        editingIssueId: action.status === "edited" ? null : state.editingIssueId,
        result,
        toast,
        history: state.history.map((row) =>
          row.id === result.requirementId
            ? {
                ...row,
                requirement: result.displayText,
                snapshot: result,
                status: action.status === "dismissed" ? row.status : "Updated",
              }
            : row,
        ),
      }
    }
    case "accept-all": {
      if (!state.result) return state
      const suggestion =
        state.result.userAssessment?.suggested_requirement ??
        state.result.suggestedRequirement
      const issues: AnalysisIssue[] = state.result.issues.map((issue) => {
        if (issue.status === "dismissed") return issue
        const status: IssueStatus = issue.editedText ? "edited" : "accepted"
        return { ...issue, status }
      })
      return {
        ...state,
        result: applyDisplayText({ ...state.result, issues }, issues, suggestion),
        toast: "All remaining suggestions accepted.",
      }
    }
    case "set-create-idea":
      return { ...state, createIdea: action.text, error: null }
    case "set-create-type":
      return { ...state, createType: action.value }
    case "set-create-details":
      return { ...state, createDetails: action.text }
    case "generate-start":
      return { ...state, status: "generating", error: null, toast: null }
    case "generate-success":
      return {
        ...state,
        status: "ready",
        createResult: action.result,
      }
    case "generate-error":
      return { ...state, status: "error", error: action.error }
    case "set-create-suggestion":
      if (!state.createResult) return state
      return {
        ...state,
        createResult: {
          ...state.createResult,
          suggestedRequirement: action.text,
        },
      }
    case "revert-all": {
      if (!state.result) return state
      const issues = state.result.issues.map((issue) => ({
        ...issue,
        status: "open" as const,
        editedText: null,
      }))
      return {
        ...state,
        result: {
          ...state.result,
          issues,
          displayText: state.result.originalText,
        },
        toast: "All suggestions reverted.",
      }
    }
    case "open-history": {
      const item = state.history.find((row) => row.id === action.id)
      if (!item) return { ...state, view: "history" }
      return {
        ...state,
        result: item.snapshot,
        view: "analysis",
        selectedIssueId: item.snapshot.issues[0]?.id ?? null,
      }
    }
    default:
      return state
  }
}

export interface AnalysisContextValue extends AnalysisState {
  revisedText: string
  setView: (view: AppView) => void
  setInputMode: (mode: InputMode) => void
  setDraftText: (text: string) => void
  setFile: (name: string | null, text: string) => void
  analyze: () => Promise<void>
  selectIssue: (id: string | null) => void
  openDrawer: (id: string | null) => void
  setFilter: (filter: IssueFilter) => void
  setIssueStatus: (id: string, status: IssueStatus, editedText?: string | null) => void
  setEditing: (id: string | null) => void
  acceptAll: () => void
  revertAll: () => void
  setToast: (message: string | null) => void
  setMobileIssues: (open: boolean) => void
  setCreateIdea: (text: string) => void
  setCreateType: (value: RequirementKind | "") => void
  setCreateDetails: (text: string) => void
  setCreateSuggestion: (text: string) => void
  generateRequirementFromIdea: () => Promise<void>
  useGeneratedRequirement: () => void
  analyzeGeneratedRequirement: () => void
  openHistoryItem: (id: string) => void
}

export const AnalysisContext = createContext<AnalysisContextValue | null>(null)

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  const revisedText = useMemo(() => {
    if (!state.result) return state.draftText
    return state.result.displayText || state.result.originalText
  }, [state.result, state.draftText])

  const analyze = useCallback(async () => {
    const text = state.draftText.trim()
    if (!text) {
      dispatch({ type: "analyze-error", error: "Enter a requirement first." })
      return
    }
    dispatch({ type: "analyze-start" })
    try {
      const result = await analyzeDocument(text)
      dispatch({ type: "analyze-success", result })
    } catch {
      dispatch({
        type: "analyze-error",
        error: "The requirement could not be analyzed right now. Please try again.",
      })
    }
  }, [state.draftText])

  const generateRequirementFromIdea = useCallback(async () => {
    const idea = state.createIdea.trim()
    if (!idea) {
      dispatch({ type: "generate-error", error: "Describe what you want the system to do." })
      return
    }
    dispatch({ type: "generate-start" })
    try {
      const result = await generateRequirement(
        idea,
        state.createType,
        state.createDetails.trim(),
      )
      dispatch({ type: "generate-success", result })
    } catch {
      dispatch({
        type: "generate-error",
        error: "The requirement could not be generated right now. Try again.",
      })
    }
  }, [state.createIdea, state.createType, state.createDetails])

  const useGeneratedRequirement = useCallback(() => {
    if (!state.createResult) return
    const text = state.createResult.suggestedRequirement
    dispatch({ type: "set-draft", text })
    if (state.createResult.analysis) {
      dispatch({
        type: "analyze-success",
        result: {
          ...state.createResult.analysis,
          originalText: text,
          displayText: text,
        },
      })
      return
    }
    dispatch({ type: "set-view", view: "input" })
  }, [state.createResult])

  const analyzeGeneratedRequirement = useCallback(() => {
    if (!state.createResult) return
    dispatch({ type: "set-draft", text: state.createResult.suggestedRequirement })
    if (state.createResult.analysis) {
      dispatch({
        type: "analyze-success",
        result: {
          ...state.createResult.analysis,
          originalText: state.createResult.suggestedRequirement,
          displayText: state.createResult.suggestedRequirement,
        },
      })
      return
    }
    dispatch({ type: "set-view", view: "input" })
  }, [state.createResult])

  const value = useMemo<AnalysisContextValue>(
    () => ({
      ...state,
      revisedText,
      setView: (view) => dispatch({ type: "set-view", view }),
      setInputMode: (mode) => dispatch({ type: "set-input-mode", mode }),
      setDraftText: (text) => dispatch({ type: "set-draft", text }),
      setFile: (name, text) => dispatch({ type: "set-file", name, text }),
      analyze,
      generateRequirementFromIdea,
      useGeneratedRequirement,
      analyzeGeneratedRequirement,
      setCreateIdea: (text) => dispatch({ type: "set-create-idea", text }),
      setCreateType: (value) => dispatch({ type: "set-create-type", value }),
      setCreateDetails: (text) => dispatch({ type: "set-create-details", text }),
      setCreateSuggestion: (text) => dispatch({ type: "set-create-suggestion", text }),
      selectIssue: (id) => dispatch({ type: "select-issue", id }),
      openDrawer: (id) => dispatch({ type: "open-drawer", id }),
      setFilter: (filter) => dispatch({ type: "set-filter", filter }),
      setIssueStatus: (id, status, editedText) =>
        dispatch({ type: "set-status", id, status, editedText }),
      setEditing: (id) => dispatch({ type: "set-editing", id }),
      acceptAll: () => dispatch({ type: "accept-all" }),
      revertAll: () => dispatch({ type: "revert-all" }),
      setToast: (message) => dispatch({ type: "set-toast", message }),
      setMobileIssues: (open) => dispatch({ type: "set-mobile-issues", open }),
      openHistoryItem: (id) => dispatch({ type: "open-history", id }),
    }),
    [state, revisedText, analyze, generateRequirementFromIdea, useGeneratedRequirement, analyzeGeneratedRequirement],
  )

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
}
