export const SAMPLE_REQUIREMENTS = `4.1 Performance
The system should respond quickly to user requests.

4.2 Export
The application shall allow users to export data as needed.

4.3 Presentation
The dashboard must be user-friendly and display relevant information in real time.

4.4 Authentication
The system shall lock the account after 5 failed login attempts.

4.5 Ingestion
The module shall process files efficiently and notify the appropriate team if necessary.

4.6 Reporting
Users can view reports.

4.7 Availability
The service shall be highly available and recover soon after a failure.`

interface DetectionRule {
  pattern: RegExp
  category: "vague_term" | "missing_quantifier" | "undefined_actor" | "missing_edge_case" | "conflicting_statement"
  modelType: "lexical" | "syntactic" | "semantic" | "syntax" | "pragmatic"
  severity: "critical" | "medium" | "low"
  explanation: string
  rewrite: (sentence: string, phrase: string) => string
  confidence: number
}

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
        .replace(/\bquickly\b/i, "within 2 seconds"),
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
      sentence.replace(
        /\bas needed\b/i,
        "on demand, in CSV or JSON, within 10 seconds for up to 10,000 rows",
      ),
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
        "usable without training: primary actions reachable within 3 clicks",
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
      sentence.replace(
        /\brelevant information\b/i,
        "status, last-updated timestamp, and assigned owner for the signed-in role",
      ),
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
      sentence.replace(/\bin real[ -]?time\b/i, "within 1 second of the source update"),
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
      sentence.replace(/\befficiently\b/i, "within 30 seconds for files up to 10 MB"),
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
      sentence.replace(/\bthe appropriate team\b/i, "the on-call operations group"),
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
      sentence.replace(
        /\bif necessary\b/i,
        "when validation fails or processing exceeds 30 seconds",
      ),
    confidence: 0.83,
  },
  {
    pattern: /^users can\b/i,
    category: "undefined_actor",
    modelType: "syntactic",
    severity: "low",
    explanation:
      "“Users” is not a defined role, and the sentence is not written as a testable system requirement.",
    rewrite: () =>
      "The system shall allow authenticated users with the Reporter role to view reports they are assigned.",
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
      sentence.replace(/\bhighly available\b/i, "available 99.9% of each calendar month"),
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
      sentence.replace(/\bsoon after a failure\b/i, "within 15 minutes of a detected failure"),
    confidence: 0.85,
  },
  {
    pattern: /\bmust\b.+\band\b.+\bmust\b/i,
    category: "conflicting_statement",
    modelType: "syntactic",
    severity: "critical",
    explanation:
      "The sentence stacks obligations without priority, which can produce conflicting implementations.",
    rewrite: (sentence) => sentence,
    confidence: 0.66,
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

  return {
    originalText,
    issues,
    source: "mock" as const,
    classification: issues.length > 0 ? ("ambiguous" as const) : ("clean" as const),
    ambiguityType: null,
    ambiguityScore: 0,
    confidence: 0,
    explanation: "",
    suggestedRequirement: null,
    typeSource: null,
    overallStatus: issues.length > 0 ? ("ambiguous" as const) : ("clean" as const),
    linguisticSeverity: null,
    mlPrediction: null,
    finalAssessment: null,
    finalScore: null,
    llmAnalysis: null,
    userAssessment: null,
    missingInformation: [],
    displayText: originalText,
    requirementId: "REQ-000",
  }
}
