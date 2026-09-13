import { mockAnalyze } from "./mockAnalyzer"
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
} from "../types"

function isMockMode(): boolean {
  return import.meta.env.VITE_USE_MOCK !== "false"
}

export async function analyzeDocument(text: string): Promise<AnalysisResult> {
  if (isMockMode()) {
    await wait(850)
    return mockAnalyze(text)
  }
  return analyzeViaApi(text)
}

async function analyzeViaApi(text: string): Promise<AnalysisResult> {
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
  return fromApiResponse(payload)
}

function mapSeverity(severity: LinguisticSeverity | undefined): Severity {
  if (severity === "high") return "critical"
  if (severity === "low") return "low"
  return "medium"
}

function issueFromDetected(
  payload: AnalyzeApiResponse,
  item: DetectedIssue | ApiIssueView,
  index: number,
): AnalysisIssue {
  return {
    id: `issue-${index + 1}`,
    sentence: payload.requirement,
    phrase: item.phrase,
    start: item.start,
    end: item.end,
    sentenceStart: index === 0 ? 0 : item.start,
    sentenceEnd: index === 0 ? payload.requirement.length : item.end,
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
  const suggestion = payload.suggested_requirement
  const detected =
    payload.linguistic_findings ?? payload.detected_issues ?? []
  const phrase = payload.flagged_phrase?.trim() ?? ""
  const start = payload.flagged_start ?? 0
  const end = payload.flagged_end ?? (phrase ? start + phrase.length : 0)
  const mlConfidence =
    payload.ml_prediction?.stage_a?.confidence ??
    payload.ml_prediction?.confidence ??
    payload.confidence

  let issues: AnalysisIssue[]
  if (payload.issues && payload.issues.length > 0) {
    issues = payload.issues.map((item, index) =>
      issueFromDetected(payload, item, index),
    )
  } else if (detected.length > 0) {
    issues = detected.map((item, index) => issueFromDetected(payload, item, index))
  } else if (
    Boolean(suggestion && suggestion.trim()) ||
    (classification === "ambiguous" && ambiguityType) ||
    Boolean(phrase)
  ) {
    issues = [
      {
        id: "issue-1",
        sentence: payload.requirement,
        phrase,
        start,
        end,
        sentenceStart: 0,
        sentenceEnd: payload.requirement.length,
        category: "vague_term",
        modelType: ambiguityType,
        severity: mapSeverity(payload.linguistic_severity ?? undefined),
        explanation: payload.explanation,
        suggestion: suggestion ?? payload.requirement,
        confidence: payload.confidence,
        status: "open",
        editedText: null,
      },
    ]
  } else {
    issues = []
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
    suggestedRequirement: suggestion,
    typeSource: payload.type_source ?? null,
    linguisticSeverity: payload.linguistic_severity ?? null,
    mlPrediction: payload.ml_prediction ?? {
      classification,
      confidence: payload.confidence,
      ambiguity_score: payload.ambiguity_score,
    },
    finalAssessment: payload.final_assessment ?? null,
    finalScore: payload.final_score ?? payload.final_assessment?.score ?? null,
    llmAnalysis: payload.llm_analysis ?? null,
    userAssessment: payload.user_assessment ?? null,
    missingInformation: payload.missing_information ?? payload.user_assessment?.missing_information ?? [],
    displayText: payload.requirement,
    requirementId: "",
  }
}

export async function generateRequirement(
  idea: string,
  requirementType?: RequirementKind | "",
  details?: string,
): Promise<GenerateResult> {
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

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}
