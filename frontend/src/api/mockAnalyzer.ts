export const SAMPLE_REQUIREMENTS = `The system should respond quickly to user requests.`

interface DetectionRule {
  pattern: RegExp
  category:
    | "vague_term"
    | "missing_quantifier"
    | "undefined_actor"
    | "missing_edge_case"
    | "conflicting_statement"
  modelType: "lexical" | "syntactic" | "semantic" | "syntax" | "pragmatic"
  severity: "critical" | "medium" | "low"
  explanation: string
  rewrite: (sentence: string, phrase: string) => string
  confidence: number
}

const TYPE_LABELS = {
  lexical: "Lexical",
  syntactic: "Syntactic",
  semantic: "Semantic",
  syntax: "Syntax",
  pragmatic: "Pragmatic",
} as const

const RULES: DetectionRule[] = [
  {
    pattern: /\bquickly\b/gi,
    category: "vague_term",
    modelType: "pragmatic",
    severity: "critical",
    explanation:
      "“Quickly” does not define a measurable response time, so implementers can ship different behavior.",
    rewrite: (sentence) =>
      sentence
        .replace(/\bshould\b/i, "shall")
        .replace(/\bquickly\b/i, "within [maximum response time]"),
    confidence: 0.86,
  },
  {
    pattern: /\bas needed\b/gi,
    category: "missing_quantifier",
    modelType: "pragmatic",
    severity: "medium",
    explanation:
      "“As needed” leaves frequency and trigger undefined. The export behavior cannot be tested as written.",
    rewrite: (sentence) =>
      sentence.replace(/\bas needed\b/i, "on demand, in [format], within [time limit]"),
    confidence: 0.81,
  },
  {
    pattern: /\buser-friendly\b/gi,
    category: "vague_term",
    modelType: "lexical",
    severity: "medium",
    explanation:
      "“User-friendly” is subjective. It does not name a concrete interaction, layout, or acceptance check.",
    rewrite: (sentence) =>
      sentence.replace(
        /\buser-friendly\b/i,
        "usable without training: primary actions reachable within [N] clicks",
      ),
    confidence: 0.78,
  },
  {
    pattern: /\brelevant information\b/gi,
    category: "undefined_actor",
    modelType: "semantic",
    severity: "medium",
    explanation:
      "“Relevant information” does not say which fields, for which role, or who decides relevance.",
    rewrite: (sentence) =>
      sentence.replace(/\brelevant information\b/i, "[specific fields for the signed-in role]"),
    confidence: 0.74,
  },
  {
    pattern: /\breal[ -]?time\b/gi,
    category: "missing_quantifier",
    modelType: "syntax",
    severity: "medium",
    explanation:
      "“Real time” is not a latency bound. State the maximum delay after the source changes.",
    rewrite: (sentence) =>
      sentence.replace(
        /\bin real[ -]?time\b/i,
        "within [maximum delay] of the source update",
      ),
    confidence: 0.8,
  },
  {
    pattern: /\befficiently\b/gi,
    category: "vague_term",
    modelType: "lexical",
    severity: "critical",
    explanation:
      "“Efficiently” is not testable. Throughput, file size, or a time limit is missing.",
    rewrite: (sentence) =>
      sentence.replace(/\befficiently\b/i, "within [time limit] for files up to [size]"),
    confidence: 0.88,
  },
  {
    pattern: /\bappropriate team\b/gi,
    category: "undefined_actor",
    modelType: "semantic",
    severity: "medium",
    explanation:
      "The actor is unnamed. “Appropriate team” does not identify a role, queue, or channel.",
    rewrite: (sentence) =>
      sentence.replace(/\bthe appropriate team\b/i, "[named role or team]"),
    confidence: 0.77,
  },
  {
    pattern: /\bif necessary\b/gi,
    category: "missing_edge_case",
    modelType: "pragmatic",
    severity: "critical",
    explanation:
      "The condition is unstated. Say which failure, threshold, or event triggers the notification.",
    rewrite: (sentence) =>
      sentence.replace(/\bif necessary\b/i, "when [specific failure condition occurs]"),
    confidence: 0.83,
  },
  {
    pattern: /^users can\b/i,
    category: "undefined_actor",
    modelType: "syntactic",
    severity: "low",
    explanation:
      "“Users” is not a defined role, and the sentence is not written as a testable system requirement.",
    rewrite: () => "The system shall allow [named role] to [specific action].",
    confidence: 0.7,
  },
  {
    pattern: /\bhighly available\b/gi,
    category: "missing_quantifier",
    modelType: "pragmatic",
    severity: "critical",
    explanation:
      "Availability is not quantified. State an uptime target and the window it is measured over.",
    rewrite: (sentence) =>
      sentence.replace(
        /\bhighly available\b/i,
        "available [uptime target] of each calendar month",
      ),
    confidence: 0.9,
  },
  {
    pattern: /\bsoon\b/gi,
    category: "vague_term",
    modelType: "lexical",
    severity: "medium",
    explanation:
      "“Soon” is not a recovery time objective. Name the maximum downtime after a detected failure.",
    rewrite: (sentence) =>
      sentence.replace(
        /\bsoon after a failure\b/i,
        "within [recovery time] of a detected failure",
      ),
    confidence: 0.85,
  },
]

function splitSentences(text: string): { text: string; start: number; end: number }[] {
  const parts: { text: string; start: number; end: number }[] = []
  const regex = /[^\n.!?]+[.!?]?/g
  let match: RegExpExecArray | null
  while ((match = regex.exec(text)) !== null) {
    const raw = match[0]
    const leading = raw.match(/^\s*/)?.[0].length ?? 0
    const trailing = raw.match(/\s*$/)?.[0].length ?? 0
    const start = match.index + leading
    const end = match.index + raw.length - trailing
    const slice = text.slice(start, end)
    if (slice.trim().length > 0) {
      parts.push({ text: slice, start, end })
    }
  }
  return parts
}

function scoreFromSeverity(severity: "critical" | "medium" | "low"): number {
  if (severity === "critical") return 8.2
  if (severity === "medium") return 5.5
  return 3.2
}

export function mockAnalyze(originalText: string) {
  const issues = []
  const used = new Set<string>()
  let index = 0

  for (const sentence of splitSentences(originalText)) {
    for (const rule of RULES) {
      rule.pattern.lastIndex = 0
      const hit = rule.pattern.exec(sentence.text)
      if (!hit || hit.index == null) continue
      const phrase = hit[0]
      const start = sentence.start + hit.index
      const end = start + phrase.length
      const key = `${start}:${end}`
      if (used.has(key)) continue
      used.add(key)
      index += 1
      issues.push({
        id: `issue-${index}`,
        sentence: sentence.text,
        phrase,
        start,
        end,
        sentenceStart: sentence.start,
        sentenceEnd: sentence.end,
        category: rule.category,
        modelType: rule.modelType,
        severity: rule.severity,
        explanation: rule.explanation,
        suggestion: rule.rewrite(sentence.text, phrase).replace(/\s+/g, " ").trim(),
        confidence: rule.confidence,
        status: "open" as const,
        editedText: null,
      })
    }
  }

  const primary = issues[0] ?? null
  const ambiguous = issues.length > 0
  const ambiguityOutOfTen = primary ? scoreFromSeverity(primary.severity) : 1.2
  const clarity = Math.round((10 - ambiguityOutOfTen) * 10) / 10
  const suggested = primary?.suggestion ?? null

  return {
    originalText,
    generatedText: null,
    issues,
    source: "mock" as const,
    classification: ambiguous ? ("ambiguous" as const) : ("clean" as const),
    ambiguityType: primary?.modelType ?? null,
    ambiguityScore: ambiguous ? Math.round(ambiguityOutOfTen * 10) : 8,
    confidence: primary?.confidence ?? 0.9,
    explanation:
      primary?.explanation ?? "The requirement looks specific and measurable as written.",
    suggestedRequirement: suggested,
    typeSource: primary ? ("linguistic" as const) : null,
    overallStatus: ambiguous ? ("ambiguous" as const) : ("clean" as const),
    linguisticSeverity:
      primary?.severity === "critical"
        ? ("high" as const)
        : primary?.severity === "low"
          ? ("low" as const)
          : primary
            ? ("medium" as const)
            : null,
    mlPrediction: null,
    finalAssessment: {
      status: ambiguous ? ("ambiguous" as const) : ("clean" as const),
      ambiguity_score: ambiguityOutOfTen,
      clarity_score: clarity,
      score: clarity,
      severity:
        primary?.severity === "critical"
          ? ("high" as const)
          : primary?.severity === "low"
            ? ("low" as const)
            : primary
              ? ("medium" as const)
              : null,
      ambiguity_type: primary?.modelType ?? null,
      type: primary?.modelType ?? null,
      source: "linguistic" as const,
    },
    finalScore: clarity,
    clarityScore: clarity,
    fusedAmbiguityScore: ambiguityOutOfTen,
    llmAnalysis: null,
    userAssessment: {
      status: ambiguous ? ("needs_improvement" as const) : ("clear" as const),
      title: ambiguous ? "Needs improvement" : "Clear",
      ambiguity_type: primary?.modelType ?? null,
      type_label: primary ? TYPE_LABELS[primary.modelType] : null,
      why: primary?.explanation ?? "The wording looks testable as written.",
      suggested_requirement: suggested,
      missing_information: suggested?.includes("[")
        ? ["Replace bracketed placeholders with measurable values."]
        : [],
      phrases: issues.map((issue) => ({
        text: issue.phrase,
        start: issue.start,
        end: issue.end,
        ambiguity_type: issue.modelType,
        type_label: TYPE_LABELS[issue.modelType],
        severity:
          issue.severity === "critical"
            ? ("high" as const)
            : issue.severity === "low"
              ? ("low" as const)
              : ("medium" as const),
        why: issue.explanation,
        suggestion: issue.suggestion,
        specify: issue.suggestion.includes("[")
          ? "Replace the placeholder with a concrete, measurable value."
          : null,
      })),
      requirement_type: "functional" as const,
      requirement_type_label: "Functional",
      score: clarity,
      clarity_score: clarity,
      ambiguity_score: ambiguityOutOfTen,
      score_label:
        clarity >= 8
          ? "Very clear"
          : clarity >= 6
            ? "Mostly clear"
            : clarity >= 4
              ? "Needs improvement"
              : "Highly ambiguous",
    },
    missingInformation: suggested?.includes("[")
      ? ["Replace bracketed placeholders with measurable values."]
      : [],
    displayText: originalText,
    requirementId: "REQ-000",
  }
}

function mockBuildRequirement(idea: string, details?: string): string {
  let text = idea.replace(/\s+/g, " ").trim().replace(/[.!?]+$/, "")
  text = text.replace(/^\s*(i want(?: you to)?|i need|please)\s+/i, "").trim()

  const systemShall = text.match(
    /^(?:the\s+)?(?:system|application|software)\s+(?:shall|must|should|will)\s+(.+)$/i,
  )
  if (systemShall?.[1]) {
    text = systemShall[1]
  } else {
    const able = text.match(
      /^(?:(?:the\s+)?(?:users?|use)\s+)?(?:shall|must|should|will|can)\s+be\s+able\s+to\s+(.+)$/i,
    )
    if (able?.[1]) {
      text = `allow the user to ${able[1]}`
    } else {
      const letUsers = text.match(
        /^(.+?)\s+(?:should|shall|must|will|can)\s+(?:let|allow|enable)\s+(?:the\s+)?users?\s+(?:to\s+)?(.+)$/i,
      )
      if (letUsers?.[2]) {
        const context = letUsers[1].trim()
        text = `allow users to ${letUsers[2]}`
        if (
          context &&
          context.split(/\s+/).length <= 4 &&
          !/\b(system|application|software|users?)\b/i.test(context)
        ) {
          text = `${text} during ${context.toLowerCase()}`
        }
      } else {
        text = text.replace(
          /^(?:(?:the\s+)?(?:users?|use))\s+(?:should|shall|must|will|can|to)\s+(?:be\s+able\s+to\s+)?/i,
          "",
        )
        if (
          /^(navigate|reset|open|view|export|upload|download|search|filter|edit|create|delete|login)\b/i.test(
            text,
          )
        ) {
          text = `allow users to ${text}`
        }
      }
    }
  }

  text = text
    .replace(/^(?:shall|must|should|will|can)\s+(?:be\s+able\s+to\s+)?/i, "")
    .trim()
  if (!text) text = "perform [specify the intended action]"
  text = text.charAt(0).toLowerCase() + text.slice(1)
  if (details?.trim() && !text.toLowerCase().includes(details.trim().toLowerCase())) {
    text = `${text} ${details.trim().replace(/\.$/, "")}`
  }
  let suggested = `The system shall ${text}.`
  suggested = suggested.replace(/\bshall\s+(?:shall|must|should|will|can)\b/gi, "shall")
  suggested = suggested.replace(/\bshall\s+be\s+able\s+to\b/gi, "shall allow the user to")
  if (/\bquickly\b/i.test(suggested)) {
    suggested = suggested.replace(/\bquickly\b/i, "within [maximum response time]")
  }
  return suggested.replace(/\s+/g, " ").trim()
}

export function mockGenerate(
  idea: string,
  requirementType?: string | "",
  details?: string,
) {
  const kind =
    (requirementType as
      | "functional"
      | "performance"
      | "security"
      | "usability"
      | "availability"
      | "compatibility"
      | "other"
      | undefined) ||
    (/\brespond|latency|fast|quick/i.test(idea)
      ? "performance"
      : /\bnavigate|interface|usable/i.test(idea)
        ? "usability"
        : /\bpassword|login|credential|secur/i.test(idea)
          ? "security"
          : "functional")
  const suggested = mockBuildRequirement(idea, details)
  const analysis = {
    ...mockAnalyze(suggested),
    originalText: idea,
    generatedText: suggested,
    displayText: suggested,
  }
  return {
    idea,
    requirementType: kind,
    suggestedRequirement: suggested,
    explanation:
      "Rewrote the idea as a single shall-statement and flagged any remaining vague wording.",
    missingInformation: analysis.missingInformation,
    questions: suggested.includes("[")
      ? ["What measurable limit should replace the placeholder?"]
      : [],
    readyToUse: !suggested.includes("["),
    qualityChecks: [
      {
        id: "actor",
        label: "Names the system as the actor",
        passed: true,
        detail: null,
      },
      {
        id: "shall",
        label: "Uses shall wording",
        passed: true,
        detail: null,
      },
      {
        id: "measurable",
        label: "Avoids vague wording",
        passed: !suggested.includes("["),
        detail: suggested.includes("[")
          ? "A measurable placeholder still needs a concrete value."
          : null,
      },
    ],
    analysis,
  }
}
