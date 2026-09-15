/**
 * Hugging Face Gradio Space adapter for production (Vercel).
 * Local development continues to use FastAPI via Vite's /api proxy.
 */

import { Client } from "@gradio/client"

import type { AnalyzeApiResponse, GenerateApiResponse } from "../types"

export type GradioErrorBody = {
  error?: string
  code?: string
}

let cachedClient: Awaited<ReturnType<typeof Client.connect>> | null = null
let cachedSpaceId: string | null = null

export function getHfSpaceId(): string {
  return (import.meta.env.VITE_HF_SPACE ?? "").trim()
}

export function usesGradioSpace(): boolean {
  return getHfSpaceId().length > 0
}

/**
 * Prefer the live Space host URL so the Gradio client loads config with
 * api_prefix=/gradio_api. Calling /call/* without that prefix returns HTTP 404.
 */
export function resolveGradioSource(spaceRef: string): string {
  const trimmed = spaceRef.trim().replace(/\/$/, "")
  if (!trimmed) return trimmed
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  // "user/space-name" → "https://user-space-name.hf.space"
  if (trimmed.includes("/")) {
    return `https://${trimmed.replaceAll("/", "-")}.hf.space`
  }
  return trimmed
}

/** Test helper: drop the cached Gradio client. */
export function resetGradioClient(): void {
  cachedClient = null
  cachedSpaceId = null
}

async function getClient() {
  const spaceId = getHfSpaceId()
  if (!spaceId) {
    throw new Error("VITE_HF_SPACE is not configured.")
  }
  if (cachedClient && cachedSpaceId === spaceId) {
    return cachedClient
  }
  const source = resolveGradioSource(spaceId)
  const client = await Client.connect(source)
  const prefix = client.config?.api_prefix || "/gradio_api"
  // Ensure Gradio 5 call paths use /gradio_api/call/... (not /call/... → 404).
  ;(client as { api_prefix: string }).api_prefix = prefix
  cachedClient = client
  cachedSpaceId = spaceId
  return cachedClient
}

function firstData(result: { data?: unknown }): unknown {
  if (!result || !Array.isArray(result.data) || result.data.length === 0) {
    throw new Error("The analysis service returned an empty response.")
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
    throw new Error((payload as GradioErrorBody).error || fallback)
  }
  return payload as T
}

export async function analyzeViaGradio(
  requirement: string,
): Promise<AnalyzeApiResponse> {
  const client = await getClient()
  // Positional args match the Space API parameter order for /analyze.
  const result = await client.predict("/analyze", [requirement])
  const payload = firstData(result) as AnalyzeApiResponse & GradioErrorBody
  return assertGradioSuccess(
    payload,
    "The analysis service could not process this document.",
  )
}

export async function generateViaGradio(
  idea: string,
  requirementType?: string | "",
  details?: string,
): Promise<GenerateApiResponse> {
  const client = await getClient()
  const kind = requirementType?.trim() ? requirementType : "auto"
  const extra = details ?? ""
  // Positional: idea, requirement_type, details
  const result = await client.predict("/generate_requirement", [
    idea,
    kind,
    extra,
  ])
  const payload = firstData(result) as GenerateApiResponse & GradioErrorBody
  return assertGradioSuccess(payload, "The requirement could not be generated.")
}
