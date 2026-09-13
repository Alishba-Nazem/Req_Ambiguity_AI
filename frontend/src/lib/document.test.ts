import { describe, expect, it } from "vitest"
import { buildRevisedText } from "./document"
import type { AnalysisIssue } from "../types"

function issue(overrides: Partial<AnalysisIssue> = {}): AnalysisIssue {
  return {
    id: "issue-1",
    sentence: "The system shall respond quickly.",
    phrase: "quickly",
    start: 24,
    end: 31,
    sentenceStart: 0,
    sentenceEnd: 32,
    category: "vague_term",
    modelType: "pragmatic",
    severity: "critical",
    explanation: "Not measurable",
    suggestion: "The system shall respond within [X] seconds.",
    confidence: 0.9,
    status: "open",
    editedText: null,
    ...overrides,
  }
}

const original = "The system shall respond quickly."
const combined = "The system shall respond within [X] seconds."

describe("buildRevisedText", () => {
  it("accepts the suggested rewrite", () => {
    expect(buildRevisedText(original, [issue({ status: "accepted" })], combined)).toBe(combined)
  })

  it("saves an edited requirement", () => {
    const edited = "The system shall respond within 2 seconds."
    expect(
      buildRevisedText(original, [issue({ status: "edited", editedText: edited })], combined),
    ).toBe(edited)
  })

  it("keeps the original text when dismissed", () => {
    expect(buildRevisedText(original, [issue({ status: "dismissed" })], combined)).toBe(original)
  })
})
