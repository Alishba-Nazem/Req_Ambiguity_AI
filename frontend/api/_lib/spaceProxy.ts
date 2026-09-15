/**
 * Server-only Gradio Space proxy helpers for Vercel serverless functions.
 * Uses HF_TOKEN from the runtime environment — never import this from browser code.
 */

import { Client } from "@gradio/client"

export type GradioErrorBody = {
  error?: string
  code?: string
}

export type ProxyError = {
  status: number
  body: { error: string; code: string }
}

const DEFAULT_SPACE = "lishyyyy-710/req-ambiguity-ai"

const SENSITIVE =
  /zerogpu|quota|hf_token|huggingface\.co\/settings|authenticate with a hugging face token|token for more quota/i

export function getHfSpaceId(): string {
  return (
    (process.env.HF_SPACE ?? process.env.HF_SPACE_ID ?? DEFAULT_SPACE).trim() ||
    DEFAULT_SPACE
  )
}

export function getHfToken(): string {
  return (process.env.HF_TOKEN ?? "").trim()
}

/** "user/space" → https://user-space.hf.space */
export function resolveGradioSource(spaceRef: string): string {
  const trimmed = spaceRef.trim().replace(/\/$/, "")
  if (!trimmed) return trimmed
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (trimmed.includes("/")) {
    return `https://${trimmed.replaceAll("/", "-")}.hf.space`
  }
  return trimmed
}

function firstData(result: { data?: unknown }): unknown {
  if (!result || !Array.isArray(result.data) || result.data.length === 0) {
    throw Object.assign(new Error("empty_response"), { code: "empty_response" })
  }
  return result.data[0]
}

export function assertGradioSuccess<T extends object>(
  payload: T | GradioErrorBody,
  fallback: string,
): T {
  if (
    payload &&
    typeof payload === "object" &&
    "error" in payload &&
    typeof (payload as GradioErrorBody).error === "string" &&
    (payload as GradioErrorBody).error
  ) {
    const code = (payload as GradioErrorBody).code || "upstream_error"
    const message = (payload as GradioErrorBody).error || fallback
    throw Object.assign(new Error(message), { code })
  }
  return payload as T
}

let cachedClient: Awaited<ReturnType<typeof Client.connect>> | null = null
let cachedKey: string | null = null

export async function getSpaceClient() {
  const token = getHfToken()
  if (!token) {
    throw Object.assign(new Error("The analysis service is not configured."), {
      code: "misconfigured",
      status: 503,
    })
  }
  const spaceId = getHfSpaceId()
  const cacheKey = `${spaceId}::${token.slice(0, 8)}`
  if (cachedClient && cachedKey === cacheKey) {
    return cachedClient
  }
  const source = resolveGradioSource(spaceId)
  const client = await Client.connect(source, {
    token: token as `hf_${string}`,
  })
  const prefix = client.config?.api_prefix || "/gradio_api"
  ;(client as { api_prefix: string }).api_prefix = prefix
  cachedClient = client
  cachedKey = cacheKey
  return cachedClient
}

/** Test helper */
export function resetSpaceClient(): void {
  cachedClient = null
  cachedKey = null
}

export async function analyzeOnSpace(requirement: string): Promise<object> {
  const client = await getSpaceClient()
  const result = await client.predict("/analyze", [requirement])
  const payload = firstData(result) as object & GradioErrorBody
  return assertGradioSuccess(
    payload,
    "The analysis service could not process this document.",
  )
}

export async function generateOnSpace(
  idea: string,
  requirementType?: string | null,
  details?: string | null,
): Promise<object> {
  const client = await getSpaceClient()
  const kind = requirementType?.trim() ? requirementType.trim() : "auto"
  const extra = details ?? ""
  const result = await client.predict("/generate_requirement", [
    idea,
    kind,
    extra,
  ])
  const payload = firstData(result) as object & GradioErrorBody
  return assertGradioSuccess(payload, "The requirement could not be generated.")
}

export function toProxyError(error: unknown, fallback: string): ProxyError {
  const err = error as Error & { code?: string; status?: number; title?: string }
  const rawMessage = typeof err?.message === "string" ? err.message : ""
  const code = typeof err?.code === "string" ? err.code : ""

  if (code === "misconfigured" || err?.status === 503) {
    return {
      status: 503,
      body: {
        error: "The analysis service is temporarily unavailable. Please try again.",
        code: "model_unavailable",
      },
    }
  }

  if (code === "validation_error") {
    return {
      status: 422,
      body: {
        error: sanitizePublicMessage(rawMessage, fallback),
        code: "validation_error",
      },
    }
  }

  if (code === "model_unavailable") {
    return {
      status: 503,
      body: {
        error: sanitizePublicMessage(rawMessage, fallback),
        code: "model_unavailable",
      },
    }
  }

  if (code === "empty_response") {
    return {
      status: 502,
      body: {
        error: "The analysis service returned an empty response.",
        code: "upstream_error",
      },
    }
  }

  // Gradio/ZeroGPU auth and quota failures must not leak internals.
  if (SENSITIVE.test(rawMessage) || SENSITIVE.test(String(err?.title ?? ""))) {
    return {
      status: 503,
      body: {
        error: "The analysis service is temporarily unavailable. Please try again.",
        code: "model_unavailable",
      },
    }
  }

  if (rawMessage && !SENSITIVE.test(rawMessage)) {
    const status = code === "validation_error" ? 422 : 503
    return {
      status,
      body: {
        error: sanitizePublicMessage(rawMessage, fallback),
        code: code || "upstream_error",
      },
    }
  }

  return {
    status: 503,
    body: {
      error: fallback,
      code: "upstream_error",
    },
  }
}

function sanitizePublicMessage(message: string, fallback: string): string {
  const trimmed = message.trim()
  if (!trimmed || SENSITIVE.test(trimmed)) return fallback
  // Avoid dumping stack-like or URL-heavy messages to clients.
  if (trimmed.length > 300 || /https?:\/\//i.test(trimmed)) return fallback
  return trimmed
}
