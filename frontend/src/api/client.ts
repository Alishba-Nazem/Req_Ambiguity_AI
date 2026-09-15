import { mockAnalyze, mockGenerate } from "./mockAnalyzer"
import {
  analyzeViaGradio,
  generateViaGradio,
  usesGradioSpace,
} from "./gradioSpace"
import type {
  AnalysisIssue,
  AnalysisResult,
  AnalyzeApiResponse,
  ApiIssueView,
  DetectedIssue,
  GenerateApiResponse,
  GenerateResult,
  LinguisticSeverity,
  RequirementKind,
  Severity,
  UserPhrase,
} from "../types"

export type BackendMode = "mock" | "gradio" | "fastapi"

export function isMockMode(): boolean {
  const value = String(import.meta.env.VITE_USE_MOCK ?? "true")
    .trim()
    .toLowerCase()
  return value !== "false" && value !== "0" && value !== "no"
}

/** Resolve which backend the UI should call. Mock wins for local UI demos. */
export function resolveBackendMode(): BackendMode {
  if (isMockMode()) return "mock"
  if (usesGradioSpace()) return "gradio"
  return "fastapi"
}

export async function analyzeDocument(text: string): Promise<AnalysisResult> {
  const mode = resolveBackendMode()
  if (mode === "mock") {
    await wait(850)
    return mockAnalyze(text)
  }
  if (mode === "gradio") {
    return fromApiResponse(await analyzeViaGradio(text))
  }
  return fromApiResponse(await analyzeViaFastapi(text))
}

async function analyzeViaFastapi(text: string): Promise<AnalyzeApiResponse> {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement: text }),
  })
  const payload = (await response.json()) as AnalyzeApiResponse & {
    error?: string
  }
  if (!response.ok) {
    throw new Error(payload.error ?? "The analysis service could not process this document.")
  }
  return payload
}

function mapSeverity(severity: LinguisticSeverity | undefined | null): Severity {
  if (severity === "high") return "critical"
  if (severity === "low") return "low"
  return "medium"
}

function issueFromDetected(
  payload: AnalyzeApiResponse,
  item: DetectedIssue | ApiIssueView,
  index: number,
): AnalysisIssue | null {
  const phrase = item.phrase?.trim() ?? ""
  if (!phrase || item.end <= item.start) return null
  return {
    id: `issue-${index + 1}`,
    sentence: payload.requirement,
    phrase,
    start: item.start,
    end: item.end,
    sentenceStart: item.start,
    sentenceEnd: item.end,
    category: "vague_term",
    modelType: item.type ?? item.ambiguity_type,
    severity: mapSeverity(item.severity),
    explanation: item.reason,
    suggestion: item.suggestion,
    confidence: item.confidence ?? payload.confidence,
    status: "open",
    editedText: null,
  }
}

function issueFromUserPhrase(
  requirement: string,
  phrase: UserPhrase,
  index: number,
  fallbackSuggestion: string | null,
): AnalysisIssue | null {
  const text = phrase.text?.trim() ?? ""
  const start = phrase.start ?? -1
  const end = phrase.end ?? -1
  if (!text || start < 0 || end <= start) return null
  return {
    id: `issue-${index + 1}`,
    sentence: requirement,
    phrase: text,
    start,
    end,
    sentenceStart: start,
    sentenceEnd: end,
    category: "vague_term",
    modelType: phrase.ambiguity_type ?? null,
    severity: mapSeverity(phrase.severity),
    explanation: phrase.why,
    suggestion: phrase.suggestion || fallbackSuggestion || requirement,
    confidence: 0.9,
    status: "open",
    editedText: null,
  }
}

export function fromApiResponse(payload: AnalyzeApiResponse): AnalysisResult {
  const classification =
    payload.ml_prediction?.stage_a?.label ??
    payload.ml_prediction?.classification ??
    payload.classification
  const overallStatus =
    payload.final_assessment?.status ?? payload.overall_status ?? classification
  const ambiguityType =
    payload.final_assessment?.type ??
    payload.final_assessment?.ambiguity_type ??
    payload.ambiguity_type
  const suggestion =
    payload.user_assessment?.suggested_requirement ?? payload.suggested_requirement
  const detected =
    payload.linguistic_findings ?? payload.detected_issues ?? []
  const phrase = payload.flagged_phrase?.trim() ?? ""
  const start = payload.flagged_start ?? 0
  const end = payload.flagged_end ?? (phrase ? start + phrase.length : 0)
  const mlConfidence =
    payload.ml_prediction?.stage_a?.confidence ??
    payload.ml_prediction?.confidence ??
    payload.confidence

  let issues: AnalysisIssue[] = []
  const userPhrases = payload.user_assessment?.phrases ?? []
  if (userPhrases.length > 0) {
    issues = userPhrases
      .map((item, index) =>
        issueFromUserPhrase(payload.requirement, item, index, suggestion ?? null),
      )
      .filter((item): item is AnalysisIssue => item !== null)
  }
  if (issues.length === 0 && payload.issues && payload.issues.length > 0) {
    issues = payload.issues
      .map((item, index) => issueFromDetected(payload, item, index))
      .filter((item): item is AnalysisIssue => item !== null)
  } else if (issues.length === 0 && detected.length > 0) {
    issues = detected
      .map((item, index) => issueFromDetected(payload, item, index))
      .filter((item): item is AnalysisIssue => item !== null)
  } else if (
    issues.length === 0 &&
    (Boolean(suggestion && suggestion.trim()) ||
      (classification === "ambiguous" && ambiguityType) ||
      Boolean(phrase))
  ) {
    if (phrase && end > start) {
      issues = [
        {
          id: "issue-1",
          sentence: payload.requirement,
          phrase,
          start,
          end,
          sentenceStart: start,
          sentenceEnd: end,
          category: "vague_term",
          modelType: ambiguityType,
          severity: mapSeverity(payload.linguistic_severity ?? undefined),
          explanation: payload.user_assessment?.why ?? payload.explanation,
          suggestion: suggestion ?? payload.requirement,
          confidence: payload.confidence,
          status: "open",
          editedText: null,
        },
      ]
    }
  }

  return {
    originalText: payload.requirement,
    issues,
    source: "api",
    classification,
    overallStatus,
    ambiguityType,
    ambiguityScore: payload.ambiguity_score,
    confidence: mlConfidence,
    explanation: payload.explanation,
    suggestedRequirement: suggestion ?? null,
    typeSource: payload.type_source ?? null,
    linguisticSeverity: payload.linguistic_severity ?? null,
    mlPrediction: payload.ml_prediction ?? {
      classification,
      confidence: payload.confidence,
      ambiguity_score: payload.ambiguity_score,
    },
    finalAssessment: payload.final_assessment ?? null,
    finalScore:
      payload.user_assessment?.score ??
      payload.final_score ??
      payload.final_assessment?.score ??
      null,
    llmAnalysis: payload.llm_analysis ?? null,
    userAssessment: payload.user_assessment ?? null,
    missingInformation:
      payload.missing_information ??
      payload.user_assessment?.missing_information ??
      [],
    displayText: payload.requirement,
    requirementId: "",
  }
}

export function fromGenerateApiResponse(payload: GenerateApiResponse): GenerateResult {
  return {
    idea: payload.idea,
    requirementType: payload.requirement_type,
    suggestedRequirement: payload.suggested_requirement,
    explanation: payload.explanation,
    missingInformation: payload.missing_information ?? [],
    questions: payload.questions ?? [],
    readyToUse: payload.ready_to_use,
    qualityChecks: payload.quality_checks ?? [],
    analysis: payload.analysis ? fromApiResponse(payload.analysis) : null,
  }
}

export async function generateRequirement(
  idea: string,
  requirementType?: RequirementKind | "",
  details?: string,
): Promise<GenerateResult> {
  const mode = resolveBackendMode()
  if (mode === "mock") {
    await wait(700)
    return mockGenerate(idea, requirementType, details)
  }
  if (mode === "gradio") {
    return fromGenerateApiResponse(
      await generateViaGradio(idea, requirementType, details),
    )
  }
  return fromGenerateApiResponse(
    await generateViaFastapi(idea, requirementType, details),
  )
}

async function generateViaFastapi(
  idea: string,
  requirementType?: RequirementKind | "",
  details?: string,
): Promise<GenerateApiResponse> {
  const response = await fetch("/api/generate-requirement", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      idea,
      requirement_type: requirementType || undefined,
      details: details || undefined,
    }),
  })
  const payload = (await response.json()) as GenerateApiResponse & { error?: string }
  if (!response.ok) {
    throw new Error(payload.error ?? "The requirement could not be generated.")
  }
  return payload
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}
