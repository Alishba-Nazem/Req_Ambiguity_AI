import type { VercelRequest, VercelResponse } from "@vercel/node"

import { analyzeOnSpace, toProxyError } from "./_lib/spaceProxy"

export const config = {
  maxDuration: 60,
}

export default async function handler(
  req: VercelRequest,
  res: VercelResponse,
): Promise<void> {
  if (req.method === "OPTIONS") {
    res.status(204).end()
    return
  }
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed.", code: "method_not_allowed" })
    return
  }

  try {
    let body: unknown = req.body
    if (typeof body === "string") {
      try {
        body = JSON.parse(body)
      } catch {
        res.status(422).json({
          error: "Request body must be valid JSON.",
          code: "validation_error",
        })
        return
      }
    }
    const record = (body ?? {}) as Record<string, unknown>
    const requirement =
      typeof record.requirement === "string" ? record.requirement : ""
    if (!requirement.trim()) {
      res.status(422).json({
        error: "requirement must not be empty or whitespace-only",
        code: "validation_error",
      })
      return
    }

    const payload = await analyzeOnSpace(requirement)
    res.status(200).json(payload)
  } catch (error) {
    const mapped = toProxyError(
      error,
      "The analysis service could not process this document.",
    )
    res.status(mapped.status).json(mapped.body)
  }
}
