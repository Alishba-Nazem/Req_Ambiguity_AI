import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const predict = vi.fn()
const connect = vi.fn(async () => ({
  predict,
  config: { api_prefix: "/gradio_api", root: "https://lishyyyy-710-req-ambiguity-ai.hf.space" },
  api_prefix: "/gradio_api",
}))

vi.mock("@gradio/client", () => ({
  Client: { connect },
}))

describe("Gradio Space adapter", () => {
  beforeEach(() => {
    predict.mockReset()
    connect.mockClear()
    vi.resetModules()
    vi.stubEnv("VITE_USE_MOCK", "false")
    vi.stubEnv("VITE_HF_SPACE", "lishyyyy-710/req-ambiguity-ai")
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it("connects to the Space host URL and calls /analyze positionally", async () => {
    predict.mockResolvedValueOnce({
      data: [
        {
          requirement: "The system should respond quickly.",
          classification: "ambiguous",
          ambiguity_type: "pragmatic",
          ambiguity_score: 78,
          confidence: 0.81,
          explanation: "The phrase is vague.",
          suggested_requirement: "The system shall respond within [X] seconds.",
          overall_status: "ambiguous",
          final_assessment: {
            status: "ambiguous",
            score: 8.2,
            severity: "high",
            ambiguity_type: "pragmatic",
            type: "pragmatic",
            source: "hybrid",
          },
          user_assessment: {
            status: "needs_improvement",
            title: "Needs improvement",
            type_label: "Pragmatic",
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
            score: 8.2,
            score_label: "High ambiguity",
            requirement_type_label: "Performance",
          },
        },
      ],
    })

    const { analyzeDocument, resolveBackendMode } = await import("./client")
    const { resolveGradioSource } = await import("./gradioSpace")
    expect(resolveBackendMode()).toBe("gradio")
    expect(resolveGradioSource("lishyyyy-710/req-ambiguity-ai")).toBe(
      "https://lishyyyy-710-req-ambiguity-ai.hf.space",
    )

    const result = await analyzeDocument("The system should respond quickly.")
    expect(connect).toHaveBeenCalledWith(
      "https://lishyyyy-710-req-ambiguity-ai.hf.space",
    )
    expect(predict).toHaveBeenCalledWith("/analyze", [
      "The system should respond quickly.",
    ])
    expect(result.overallStatus).toBe("ambiguous")
    expect(result.finalScore).toBe(8.2)
    expect(result.userAssessment?.type_label).toBe("Pragmatic")
    expect(result.issues[0]?.phrase).toBe("quickly")
  })

  it("calls /generate_requirement positionally and preserves the response shape", async () => {
    predict.mockResolvedValueOnce({
      data: [
        {
          idea: "I want users to navigate the dashboard",
          requirement_type: "usability",
          suggested_requirement: "The system shall allow users to navigate the dashboard.",
          explanation: "Rewrote as a shall-statement.",
          missing_information: [],
          questions: [],
          ready_to_use: true,
          quality_checks: [
            { id: "actor", label: "Names the system as the actor", passed: true },
          ],
          analysis: {
            requirement: "The system shall allow users to navigate the dashboard.",
            classification: "clean",
            ambiguity_type: null,
            ambiguity_score: 10,
            confidence: 0.9,
            explanation: "Clear.",
            suggested_requirement: null,
            overall_status: "clean",
            final_assessment: {
              status: "clean",
              score: 1.5,
              severity: null,
              ambiguity_type: null,
              type: null,
              source: "bert",
            },
            user_assessment: {
              status: "clear",
              title: "Clear",
              why: "Looks testable.",
              phrases: [],
              score: 1.5,
              score_label: "Low ambiguity",
            },
          },
        },
      ],
    })

    const { generateRequirement } = await import("./client")
    const result = await generateRequirement(
      "I want users to navigate the dashboard",
      "usability",
      "",
    )

    expect(predict).toHaveBeenCalledWith("/generate_requirement", [
      "I want users to navigate the dashboard",
      "usability",
      "",
    ])
    expect(result.requirementType).toBe("usability")
    expect(result.readyToUse).toBe(true)
    expect(result.analysis?.overallStatus).toBe("clean")
  })

  it("throws when Gradio returns { error, code }", async () => {
    predict.mockResolvedValueOnce({
      data: [
        {
          error: "requirement must not be empty or whitespace-only",
          code: "validation_error",
        },
      ],
    })

    const { analyzeDocument } = await import("./client")
    await expect(analyzeDocument("   ")).rejects.toThrow(
      /requirement must not be empty/i,
    )
  })

  it("defaults requirement_type to auto when omitted", async () => {
    predict.mockResolvedValueOnce({
      data: [
        {
          idea: "reset password",
          requirement_type: "security",
          suggested_requirement: "The system shall allow users to reset their password.",
          explanation: "ok",
          missing_information: [],
          questions: [],
          ready_to_use: false,
          quality_checks: [],
          analysis: null,
        },
      ],
    })

    const { generateRequirement } = await import("./client")
    await generateRequirement("reset password")
    expect(predict).toHaveBeenCalledWith("/generate_requirement", [
      "reset password",
      "auto",
      "",
    ])
  })
})

describe("backend mode selection", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it("uses mock when VITE_USE_MOCK is not false", async () => {
    vi.stubEnv("VITE_USE_MOCK", "true")
    vi.stubEnv("VITE_HF_SPACE", "lishyyyy-710/req-ambiguity-ai")
    const { resolveBackendMode } = await import("./client")
    expect(resolveBackendMode()).toBe("mock")
  })

  it("uses fastapi when mock is off and VITE_HF_SPACE is empty", async () => {
    vi.stubEnv("VITE_USE_MOCK", "false")
    vi.stubEnv("VITE_HF_SPACE", "")
    const { resolveBackendMode } = await import("./client")
    expect(resolveBackendMode()).toBe("fastapi")
  })

  it("uses gradio when mock is off and VITE_HF_SPACE is set", async () => {
    vi.stubEnv("VITE_USE_MOCK", "false")
    vi.stubEnv("VITE_HF_SPACE", "lishyyyy-710/req-ambiguity-ai")
    const { resolveBackendMode } = await import("./client")
    expect(resolveBackendMode()).toBe("gradio")
  })
})

describe("resolveGradioSource", () => {
  it("maps space id to the hf.space host", async () => {
    const { resolveGradioSource } = await import("./gradioSpace")
    expect(resolveGradioSource("lishyyyy-710/req-ambiguity-ai")).toBe(
      "https://lishyyyy-710-req-ambiguity-ai.hf.space",
    )
  })
})
