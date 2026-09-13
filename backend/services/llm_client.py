"""Shared LLM HTTP client. Supports OpenAI-compatible APIs and Gemini.

Never logs API keys. Callers must treat any exception as a soft failure.
"""

from __future__ import annotations

import logging

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)

GEMINI_PROVIDERS = frozenset({"gemini", "google", "google-gemini"})
_PLACEHOLDER_MODELS = frozenset({"", "your-model", "your_model"})


def is_gemini(settings: Settings) -> bool:
    return (settings.llm_provider or "").strip().lower() in GEMINI_PROVIDERS


def resolved_model(settings: Settings) -> str:
    model = (settings.llm_model or "").strip()
    if is_gemini(settings):
        if model in _PLACEHOLDER_MODELS or model.startswith("gpt-"):
            return "gemini-2.0-flash"
        return model
    return model or "gpt-4o-mini"


def complete_chat(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = True,
) -> str:
    """Return the assistant text. Raises on transport or empty-content failures."""
    if is_gemini(settings):
        return _complete_gemini(settings, system_prompt, user_prompt, json_mode)
    return _complete_openai(settings, system_prompt, user_prompt, json_mode)


def _complete_openai(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool,
) -> str:
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": resolved_model(settings),
        "temperature": 0.2,
        "max_tokens": int(settings.llm_max_output_tokens),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key.strip()}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty LLM content")
    return content


def _complete_gemini(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool,
) -> str:
    model = resolved_model(settings)
    base = "https://generativelanguage.googleapis.com/v1beta"
    if "generativelanguage.googleapis.com" in (settings.llm_base_url or ""):
        base = settings.llm_base_url.rstrip("/")
        if base.endswith("/openai") or base.endswith("/v1"):
            base = "https://generativelanguage.googleapis.com/v1beta"
    url = f"{base}/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": int(settings.llm_max_output_tokens),
        },
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    headers = {
        "x-goog-api-key": settings.llm_api_key.strip(),
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
    parts = body["candidates"][0]["content"]["parts"]
    text = "".join(str(part.get("text") or "") for part in parts)
    if not text.strip():
        raise ValueError("empty LLM content")
    return text
