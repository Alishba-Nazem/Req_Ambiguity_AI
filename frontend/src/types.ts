export const SEVERITIES = ["critical", "medium", "low"] as const
export type Severity = (typeof SEVERITIES)[number]

export const ISSUE_CATEGORIES = [
  "vague_term",
  "missing_quantifier",
  "undefined_actor",
  "missing_edge_case",
  "conflicting_statement",
] as const
export type IssueCategory = (typeof ISSUE_CATEGORIES)[number]

export const CATEGORY_LABELS: Record<IssueCategory, string> = {
  vague_term: "Vague term",
  missing_quantifier: "Missing quantifier",
  undefined_actor: "Undefined actor",
  missing_edge_case: "Missing edge case",
  conflicting_statement: "Conflicting statement",
}

export const MODEL_TYPES = [
  "lexical",
  "syntactic",
  "semantic",
  "syntax",
  "pragmatic",
] as const
export type ModelAmbiguityType = (typeof MODEL_TYPES)[number]

export const MODEL_TYPE_LABELS: Record<ModelAmbiguityType, string> = {
  lexical: "Lexical",
  syntactic: "Syntactic",
  semantic: "Semantic",
  syntax: "Syntax",
  pragmatic: "Pragmatic",
}

export type TypeSource =
  | "stage_b"
  | "heuristic"
  | "linguistic"
  | "linguistic_override"
  | "hybrid"
  | "bert"
  | "llm"
export type LinguisticSeverity = "high" | "medium" | "low"
export type EvidenceSource = "bert" | "linguistic" | "hybrid" | "llm"
export type FindingSource = "linguistic" | "llm"

export type IssueStatus = "open" | "accepted" | "edited" | "dismissed"

export type AppView = "dashboard" | "input" | "create" | "analysis" | "history"

export type RequirementKind =
  | "functional"
  | "performance"
  | "security"
  | "usability"
  | "availability"
  | "compatibility"
  | "other"

export const REQUIREMENT_KIND_LABELS: Record<RequirementKind, string> = {
  functional: "Functional",
  performance: "Performance",
  security: "Security",
  usability: "Usability",
  availability: "Availability",
  compatibility: "Compatibility",
  other: "Other",
}
export type InputMode = "paste" | "upload"
export type IssueFilter = "all" | Severity

export interface AnalysisIssue {
  id: string
  sentence: string
  phrase: string
  start: number
  end: number
  sentenceStart: number
  sentenceEnd: number
  category: IssueCategory
  modelType: ModelAmbiguityType | null
  severity: Severity
  explanation: string
  suggestion: string
  confidence: number
  status: IssueStatus
  editedText: string | null
}

export type Classification = "clean" | "ambiguous"

export interface DetectedIssue {
  phrase: string
  start: number
  end: number
  ambiguity_type: ModelAmbiguityType
  type?: ModelAmbiguityType
  category: string
  reason: string
  suggestion: string
  severity: LinguisticSeverity
  confidence?: number
  source: FindingSource
}

export interface StageAPrediction {
  label: Classification
  confidence: number
  source?: "bert"
  stage?: "stage_a"
}

export interface StageBPrediction {
  label: ModelAmbiguityType
  confidence?: number | null
  source?: "bert"
  stage?: "stage_b"
}

export interface MlPrediction {
  classification: Classification
  confidence: number
  ambiguity_score: number
  source?: "bert"
  stage?: "stage_a"
  stage_b_type?: ModelAmbiguityType | null
  stage_a?: StageAPrediction | null
  stage_b?: StageBPrediction | null
}

export interface FinalAssessment {
  status: Classification
  /** Fused ambiguity 0–10 (higher = more ambiguous). */
  ambiguity_score?: number | null
  /** Requirement quality / clarity 0–10 (higher = clearer). */
  clarity_score?: number | null
  /** Alias of clarity_score for user-facing displays. */
  score: number
  severity: LinguisticSeverity | null
  ambiguity_type: ModelAmbiguityType | null
  type?: ModelAmbiguityType | null
  source: EvidenceSource
}

export interface ApiIssueView {
  id: string
  phrase: string
  start: number
  end: number
  type: ModelAmbiguityType
  ambiguity_type: ModelAmbiguityType
  severity: LinguisticSeverity
  confidence: number
  source: FindingSource
  reason: string
  suggestion: string
  category: string
}

export interface LlmPhraseView {
  text: string
  phrase?: string
  reason: string
  suggestion?: string
  start?: number | null
  end?: number | null
  source?: "llm"
}

export interface LlmAnalysis {
  available: boolean
  reason?: string | null
  is_ambiguous?: boolean | null
  score?: number | null
  type?: ModelAmbiguityType | null
  ambiguity_type?: ModelAmbiguityType | null
  severity?: LinguisticSeverity | null
  confidence?: number | null
  explanation?: string | null
  ambiguous_phrases?: LlmPhraseView[]
  source?: "llm"
}

export interface AnalysisResult {
  /** Exact text the user entered (idea or pasted requirement). Never overwritten by rewrites. */
  originalText: string
  /**
   * Clean generated shall-statement when the user came from Create.
   * Null for paste/upload analyze flows. Phrase spans refer to this text when set.
   */
  generatedText: string | null
  issues: AnalysisIssue[]
  source: "mock" | "api"
  classification: Classification
  overallStatus: Classification
  ambiguityType: ModelAmbiguityType | null
  /** Stage A P(ambiguous) as 0–100 from the API. */
  ambiguityScore: number
  confidence: number
  explanation: string
  suggestedRequirement: string | null
  typeSource: TypeSource | null
  linguisticSeverity: LinguisticSeverity | null
  mlPrediction: MlPrediction | null
  finalAssessment: FinalAssessment | null
  /** User-facing clarity / requirement quality (higher = clearer). */
  finalScore: number | null
  clarityScore: number | null
  /** Fused ambiguity 0–10 (higher = more ambiguous). */
  fusedAmbiguityScore: number | null
  llmAnalysis: LlmAnalysis | null
  userAssessment: UserAssessment | null
  missingInformation: string[]
  displayText: string
  requirementId: string
}

export interface UserPhrase {
  text: string
  start?: number | null
  end?: number | null
  ambiguity_type?: ModelAmbiguityType | null
  type_label?: string | null
  severity?: LinguisticSeverity | null
  why: string
  suggestion?: string
  specify?: string | null
}

export interface UserAssessment {
  status: "needs_improvement" | "clear"
  title: string
  ambiguity_type?: ModelAmbiguityType | null
  type_label?: string | null
  why: string
  suggested_requirement?: string | null
  missing_information?: string[]
  phrases?: UserPhrase[]
  requirement_type?: RequirementKind | null
  requirement_type_label?: string | null
  /** User-facing clarity / requirement quality (higher = clearer). */
  score?: number | null
  score_label?: string | null
  ambiguity_score?: number | null
  clarity_score?: number | null
}

export interface QualityCheck {
  id: string
  label: string
  passed: boolean
  detail?: string | null
}

export interface HistoryItem {
  id: string
  requirement: string
  score: number | null
  requirementType: string | null
  ambiguityType: string | null
  status: string
  date: string
  snapshot: AnalysisResult
}

export interface GenerateApiResponse {
  idea: string
  requirement_type: RequirementKind
  suggested_requirement: string
  explanation: string
  missing_information: string[]
  questions: string[]
  ready_to_use: boolean
  quality_checks?: QualityCheck[]
  analysis: AnalyzeApiResponse | null
}

export interface GenerateResult {
  idea: string
  requirementType: RequirementKind
  suggestedRequirement: string
  explanation: string
  missingInformation: string[]
  questions: string[]
  readyToUse: boolean
  qualityChecks: QualityCheck[]
  analysis: AnalysisResult | null
}

export interface AnalyzeApiResponse {
  requirement: string
  classification: "clean" | "ambiguous"
  ambiguity_type: ModelAmbiguityType | null
  ambiguity_score: number
  confidence: number
  explanation: string
  suggested_requirement: string | null
  type_source?: TypeSource | null
  flagged_phrase?: string | null
  flagged_start?: number | null
  flagged_end?: number | null
  overall_status?: Classification
  ml_prediction?: MlPrediction | null
  detected_issues?: DetectedIssue[]
  linguistic_findings?: DetectedIssue[]
  issues?: ApiIssueView[]
  linguistic_severity?: LinguisticSeverity | null
  final_assessment?: FinalAssessment | null
  final_score?: number | null
  fused_ambiguity_score?: number | null
  clarity_score?: number | null
  llm_analysis?: LlmAnalysis | null
  user_assessment?: UserAssessment | null
  missing_information?: string[]
}
