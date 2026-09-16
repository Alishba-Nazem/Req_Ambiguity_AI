import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

describe("backend mode selection", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it("uses mock when VITE_USE_MOCK is not false", async () => {
    vi.stubEnv("VITE_USE_MOCK", "true")
    const { resolveBackendMode } = await import("./client")
    expect(resolveBackendMode()).toBe("mock")
  })

  it("uses api when mock is off", async () => {
    vi.stubEnv("VITE_USE_MOCK", "false")
    const { resolveBackendMode } = await import("./client")
    expect(resolveBackendMode()).toBe("api")
  })

  it("treats VITE_USE_MOCK=0 as non-mock api mode", async () => {
    vi.stubEnv("VITE_USE_MOCK", "0")
    const { resolveBackendMode } = await import("./client")
    expect(resolveBackendMode()).toBe("api")
  })
})

describe("same-origin /api client", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubEnv("VITE_USE_MOCK", "false")
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it("POSTs /api/analyze and maps the response", async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          requirement: "The system should respond quickly.",
          classification: "ambiguous",
          ambiguity_type: "pragmatic",
          ambiguity_score: 78,
          confidence: 0.81,
          explanation: "The phrase is vague.",
          suggested_requirement: "The system shall respond within [X] seconds.",
          overall_status: "ambiguous",
          flagged_phrase: "quickly",
          flagged_start: 25,
          flagged_end: 32,
          final_assessment: {
            status: "ambiguous",
            ambiguity_score: 7.8,
            clarity_score: 2.2,
            score: 2.2,
            severity: "high",
            ambiguity_type: "lexical",
            type: "lexical",
            source: "hybrid",
          },
          fused_ambiguity_score: 7.8,
          clarity_score: 2.2,
          final_score: 2.2,
          user_assessment: {
            status: "needs_improvement",
            title: "Needs improvement",
            type_label: "Lexical / wording",
            ambiguity_type: "lexical",
            why: "Quickly is not measurable.",
            suggested_requirement: "The system shall respond within [X] seconds.",
            phrases: [
              {
                text: "quickly",
                start: 25,
                end: 32,
                ambiguity_type: "pragmatic",
                type_label: "Pragmatic",
                severity: "high",
                why: "Quickly is not measurable.",
                suggestion: "The system shall respond within [X] seconds.",
              },
            ],
            score: 2.2,
            clarity_score: 2.2,
            ambiguity_score: 7.8,
            score_label: "Highly ambiguous",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )

    const { analyzeDocument } = await import("./client")
    const result = await analyzeDocument("The system should respond quickly.")

    expect(fetchMock).toHaveBeenCalledWith("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        requirement: "The system should respond quickly.",
      }),
    })
    expect(result.overallStatus).toBe("ambiguous")
    expect(result.finalScore).toBe(2.2)
    expect(result.clarityScore).toBe(2.2)
    expect(result.fusedAmbiguityScore).toBe(7.8)
    expect(result.issues[0]?.phrase).toBe("quickly")
  })

  it("POSTs /api/generate-requirement", async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          idea: "reset password",
          requirement_type: "security",
          suggested_requirement:
            "The system shall allow users to reset their password.",
          explanation: "ok",
          missing_information: [],
          questions: [],
          ready_to_use: true,
          quality_checks: [],
          analysis: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )

    const { generateRequirement } = await import("./client")
    const result = await generateRequirement("reset password", "security", "")

    expect(fetchMock).toHaveBeenCalledWith("/api/generate-requirement", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        idea: "reset password",
        requirement_type: "security",
      }),
    })
    expect(result.requirementType).toBe("security")
    expect(result.readyToUse).toBe(true)
  })

  it("POSTs /api/generate-requirement and preserves idea as originalText", async () => {
    const fetchMock = vi.mocked(fetch)
    const idea = "Use shall be able to create a password and fill other credentials while logging into the system"
    const suggested =
      "The system shall allow the user to create a password and fill other credentials while logging into the system."
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          idea,
          requirement_type: "security",
          suggested_requirement: suggested,
          explanation: "ok",
          missing_information: [],
          questions: [],
          ready_to_use: true,
          quality_checks: [],
          analysis: {
            requirement: suggested,
            classification: "clean",
            ambiguity_type: null,
            ambiguity_score: 9,
            confidence: 0.9,
            explanation: "Clear.",
            suggested_requirement: null,
            overall_status: "clean",
            final_assessment: {
              status: "clean",
              ambiguity_score: 0.9,
              clarity_score: 9.1,
              score: 9.1,
              severity: null,
              ambiguity_type: null,
              type: null,
              source: "bert",
            },
            clarity_score: 9.1,
            fused_ambiguity_score: 0.9,
            final_score: 9.1,
            user_assessment: {
              status: "clear",
              title: "Clear",
              why: "Looks testable.",
              phrases: [],
              score: 9.1,
              clarity_score: 9.1,
              ambiguity_score: 0.9,
              score_label: "Very clear",
            },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )

    const { generateRequirement } = await import("./client")
    const result = await generateRequirement(idea, "security", "")

    expect(result.idea).toBe(idea)
    expect(result.suggestedRequirement).toBe(suggested)
    expect(result.analysis?.originalText).toBe(idea)
    expect(result.analysis?.generatedText).toBe(suggested)
    expect(result.analysis?.originalText).not.toBe(result.analysis?.generatedText)
    expect(result.analysis?.clarityScore).toBe(9.1)
    expect(result.analysis?.fusedAmbiguityScore).toBe(0.9)
  })

  it("throws on non-OK analyze responses using the public error field", async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: "The analysis service is temporarily unavailable. Please try again.",
          code: "model_unavailable",
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    )

    const { analyzeDocument } = await import("./client")
    await expect(analyzeDocument("x")).rejects.toThrow(
      /temporarily unavailable/i,
    )
  })
})
