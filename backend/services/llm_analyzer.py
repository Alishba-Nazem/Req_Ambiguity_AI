"""Optional LLM reasoning layer for requirement ambiguity.

The model is asked to reason independently about a software requirement.
It must not replace BERT Stage A/B or the linguistic detector. Structured
JSON is required; invalid or failed calls never raise to the API.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.config import Settings, get_settings
from backend.schemas import AmbiguityType, IssueSeverity
from backend.services.ambiguity_model import ModelPrediction
from backend.services.linguistic_detector import LinguisticIssue
from backend.services.llm_client import complete_chat

logger = logging.getLogger(__name__)

LLM_DISABLED = "Optional review skipped"
LLM_UNAVAILABLE = "Optional review unavailable"

_ALLOWED_TYPES = frozenset(
    {"lexical", "syntactic", "semantic", "syntax", "pragmatic"}
)
_TYPE_ALIASES = {
    "lex": "lexical",
    "lexical": "lexical",
    "syntactic": "syntactic",
    "syntax": "syntax",
    "semantic": "semantic",
    "pragmatic": "pragmatic",
}
_ALLOWED_SEVERITIES = frozenset({"high", "medium", "low"})

SYSTEM_PROMPT = """You analyze software requirements for ambiguity.

Look for issues such as vague or subjective wording, undefined quantities or
time limits, unclear actors or references, missing conditions, unclear scope,
ambiguous pronouns, inconsistent terminology, unclear logical relationships,
incomplete constraints, and context-dependent wording. Words such as quickly,
easily, user-friendly, appropriate, reasonable, sufficient, fast, regularly,
or soon are signals only. Do not mark a requirement ambiguous just because
one of those words appears. A requirement can be clear if the context already
makes the wording measurable or specific.

Do not blindly trust the BERT prediction, linguistic findings, or the
preliminary fused assessment. Reason about the requirement independently.

Use only these ambiguity types: lexical, syntactic, semantic, syntax,
pragmatic. Use "syntax" only for structurally incomplete or malformed
requirement wording. Use "pragmatic" for unstated assumptions, missing
acceptance criteria, or context-dependent expectations.

Identify the exact ambiguous phrase from the original requirement. Do not
quote the entire requirement when only one phrase is ambiguous.

Return a single JSON object with this shape:
{
  "is_ambiguous": true,
  "ambiguity_score": 8.5,
  "ambiguity_type": "pragmatic",
  "severity": "high",
  "ambiguous_phrases": [
    {
      "text": "quickly",
      "reason": "The word does not define a measurable response-time limit.",
      "suggestion": "The software shall respond within [X] seconds."
    }
  ],
  "explanation": "The requirement uses an undefined time constraint.",
  "confidence": 0.94
}

ambiguity_score is 0-10 for how ambiguous the requirement is, not a model
probability. confidence is 0-1 for how sure you are of this analysis.
If the requirement is clear, set is_ambiguous to false, use a low
ambiguity_score, and return an empty ambiguous_phrases list.
Return JSON only. No markdown fences or commentary.
"""


class LlmPhrasePayload(BaseModel):
    text: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    suggestion: str = ""

    @field_validator("text", "reason", "suggestion")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class LlmStructuredOutput(BaseModel):
    """Strict schema for the LLM JSON body."""

    is_ambiguous: bool
    ambiguity_score: float = Field(..., ge=0.0, le=10.0)
    ambiguity_type: str | None = None
    severity: str | None = None
    ambiguous_phrases: list[LlmPhrasePayload] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("ambiguity_type", "severity", "explanation")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


@dataclass(frozen=True)
class LlmPhrase:
    text: str
    reason: str
    suggestion: str
    start: int | None = None
    end: int | None = None
    source: str = "llm"


@dataclass(frozen=True)
class LlmReasoningResult:
    available: bool
    reason: str | None = None
    is_ambiguous: bool | None = None
    ambiguity_score: float | None = None
    ambiguity_type: AmbiguityType | None = None
    severity: IssueSeverity | None = None
    confidence: float | None = None
    explanation: str | None = None
    phrases: list[LlmPhrase] = field(default_factory=list)
    source: str = "llm"

    @classmethod
    def unavailable(cls, reason: str = LLM_UNAVAILABLE) -> LlmReasoningResult:
        safe = reason if reason in {LLM_DISABLED, LLM_UNAVAILABLE} else LLM_UNAVAILABLE
        return cls(available=False, reason=safe)


def locate_phrase_span(requirement: str, phrase: str) -> tuple[int, int] | None:
    """Return the first exact or case-insensitive span, or None.

    Never returns a span that covers an entire multi-word requirement.
    """
    needle = (phrase or "").strip()
    if not needle or not requirement:
        return None
    start = requirement.find(needle)
    if start < 0:
        start = requirement.lower().find(needle.lower())
        if start < 0:
            return None
        end = start + len(needle)
    else:
        end = start + len(needle)
    if _covers_whole_requirement(requirement, start, end):
        return None
    return start, end


def map_ambiguity_type(raw: str | None) -> AmbiguityType | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if key == "clean":
        return None
    mapped = _TYPE_ALIASES.get(key)
    if mapped in _ALLOWED_TYPES:
        return mapped  # type: ignore[return-value]
    return None


def map_severity(raw: str | None) -> IssueSeverity | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if key in _ALLOWED_SEVERITIES:
        return key  # type: ignore[return-value]
    return None


class LlmAnalyzer:
    """One controlled chat-completions call per requirement analysis."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def analyze(
        self,
        requirement: str,
        prediction: ModelPrediction | None,
        issues: list[LinguisticIssue],
        preliminary: Any | None = None,
    ) -> LlmReasoningResult:
        if not self._settings.llm_enabled:
            return LlmReasoningResult.unavailable(LLM_DISABLED)
        if not (self._settings.llm_api_key or "").strip():
            return LlmReasoningResult.unavailable(LLM_UNAVAILABLE)

        try:
            raw = complete_chat(
                self._settings,
                SYSTEM_PROMPT,
                _user_prompt(requirement, prediction, issues, preliminary),
                json_mode=True,
            )
            parsed = parse_llm_json(raw)
            return self._to_result(requirement, parsed)
        except Exception:
            logger.warning("LLM analysis failed; continuing without LLM.")
            return LlmReasoningResult.unavailable(LLM_UNAVAILABLE)

    def _to_result(
        self,
        requirement: str,
        parsed: LlmStructuredOutput,
    ) -> LlmReasoningResult:
        phrases: list[LlmPhrase] = []
        if parsed.is_ambiguous:
            for item in parsed.ambiguous_phrases:
                span = locate_phrase_span(requirement, item.text)
                start, end = (span if span else (None, None))
                phrases.append(
                    LlmPhrase(
                        text=requirement[start:end] if span else item.text,
                        reason=item.reason,
                        suggestion=item.suggestion,
                        start=start,
                        end=end,
                    )
                )
        ambiguity_type = map_ambiguity_type(parsed.ambiguity_type)
        if not parsed.is_ambiguous:
            ambiguity_type = None
        return LlmReasoningResult(
            available=True,
            is_ambiguous=parsed.is_ambiguous,
            ambiguity_score=round(float(parsed.ambiguity_score), 1),
            ambiguity_type=ambiguity_type,
            severity=map_severity(parsed.severity) if parsed.is_ambiguous else None,
            confidence=float(parsed.confidence),
            explanation=parsed.explanation,
            phrases=phrases,
        )


def parse_llm_json(raw: str) -> LlmStructuredOutput:
    """Parse and strictly validate LLM JSON. Raises on invalid payloads."""
    payload = json.loads(_extract_json_object(raw))
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON must be an object")
    return LlmStructuredOutput.model_validate(payload)


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    raise ValueError("LLM response is not JSON")


def _covers_whole_requirement(requirement: str, start: int, end: int) -> bool:
    span = requirement[start:end].strip()
    stripped = requirement.strip()
    if span != stripped:
        return False
    return len(stripped.split()) > 3


def _user_prompt(
    requirement: str,
    prediction: ModelPrediction | None,
    issues: list[LinguisticIssue],
    preliminary: Any | None,
) -> str:
    if prediction is None:
        stage_a = "unavailable"
        stage_a_conf = "unavailable"
        stage_b = "not available"
    else:
        stage_a = prediction.classification
        conf = (
            prediction.stage_a_confidence
            if prediction.stage_a_confidence is not None
            else prediction.confidence
        )
        stage_a_conf = f"{conf:.3f}"
        if prediction.ambiguity_type:
            stage_b_conf = (
                f"{prediction.stage_b_confidence:.3f}"
                if prediction.stage_b_confidence is not None
                else "unknown"
            )
            stage_b = f"{prediction.ambiguity_type} (confidence {stage_b_conf})"
        else:
            stage_b = "not run (Stage A was not Ambiguous or type unavailable)"

    if issues:
        ling_lines = "\n".join(
            f"- phrase={item.phrase!r} type={item.ambiguity_type} "
            f"severity={item.severity} reason={item.reason}"
            for item in issues
        )
    else:
        ling_lines = "- none"

    if preliminary is None:
        prelim_line = "unavailable"
    else:
        prelim_line = (
            f"status={getattr(preliminary, 'status', None)}, "
            f"score={getattr(preliminary, 'score', None)}/10, "
            f"type={getattr(preliminary, 'ambiguity_type', None)}"
        )

    return (
        "Analyze this software requirement independently.\n\n"
        f"Requirement:\n{requirement}\n\n"
        "Preliminary evidence from other layers. Do not blindly trust it.\n"
        f"- BERT Stage A: {stage_a} (confidence {stage_a_conf})\n"
        f"- BERT Stage B: {stage_b}\n"
        f"- Linguistic findings:\n{ling_lines}\n"
        f"- Preliminary fused assessment: {prelim_line}\n"
    )


# Re-export ValidationError for tests that inspect parse failures.
__all__ = [
    "LLM_DISABLED",
    "LLM_UNAVAILABLE",
    "LlmAnalyzer",
    "LlmPhrase",
    "LlmReasoningResult",
    "LlmStructuredOutput",
    "ValidationError",
    "locate_phrase_span",
    "map_ambiguity_type",
    "parse_llm_json",
]
