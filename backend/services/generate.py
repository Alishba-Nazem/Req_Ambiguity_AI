"""Turn a natural-language idea into a software requirement, then analyze it."""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel, Field, ValidationError

from backend.config import Settings, get_settings
from backend.schemas import GenerateResponse, QualityCheck, RequirementKind
from backend.services.analyze import AnalyzeService
from backend.services.llm_client import complete_chat
from backend.services.requirement_text import (
    apply_measurable_placeholders,
    build_requirement,
    infer_requirement_kind,
    is_broken_requirement,
    quality_checks,
    sanitize_requirement,
)
from backend.services.rewrite import is_valid_suggestion

logger = logging.getLogger(__name__)

GENERATE_SYSTEM_PROMPT = """You turn a rough idea into ONE standalone software requirement.

Hard rules:
- Output a single grammatically correct sentence.
- Start with "The system shall".
- Do not copy phrases such as "I want", "I need", or "please".
- Do not write "The system shall I want...".
- Do not invent numbers, SLAs, or technologies the user did not provide.
- If a measurable limit is missing, use a placeholder like [X] or [maximum response time].
- Describe one behavior only.
- Choose one type: functional, performance, security, usability, availability, compatibility, other.
- Do not treat words such as quickly, easily, or fast as automatically meaning performance.
  Use performance only when the idea is about response time, load time, latency, or throughput.
  Navigation and interface wording is usually usability.

Return JSON only:
{
  "requirement_type": "functional",
  "suggested_requirement": "The system shall ...",
  "explanation": "Why this wording is clearer.",
  "missing_information": ["..."],
  "questions": ["..."],
  "ready_to_use": false
}
"""

_PASSWORD_RESET = re.compile(
    r"\breset(?:ting)?\s+(?:their\s+|the\s+|a\s+)?password",
    re.IGNORECASE,
)
_SECURE = re.compile(r"\bsecur(?:e|ity)\b", re.IGNORECASE)
_FAST_IDEA = re.compile(
    r"\b(?:fast|quickly|quick|slow|performance|latency|load time)\b",
    re.IGNORECASE,
)
_AVAILABLE = re.compile(r"\bavailab", re.IGNORECASE)
_SECURITY_DETAIL = re.compile(
    r"\b(?:encrypt|password|authenticate|authorize|tls|oauth|mfa)\b",
    re.IGNORECASE,
)


class _GeneratedDraft(BaseModel):
    requirement_type: RequirementKind = "functional"
    suggested_requirement: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    missing_information: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    ready_to_use: bool = False


class GenerateService:
    def __init__(
        self,
        analyze_service: AnalyzeService,
        settings: Settings | None = None,
    ) -> None:
        self._analyze = analyze_service
        self._settings = settings or get_settings()

    def generate(
        self,
        idea: str,
        requirement_type: RequirementKind | None = None,
        details: str | None = None,
    ) -> GenerateResponse:
        draft = self._draft(idea, requirement_type, details)
        suggested = sanitize_requirement(draft.suggested_requirement, idea, details)
        if is_broken_requirement(suggested):
            suggested = build_requirement(idea, details)
        suggested = apply_measurable_placeholders(suggested, draft.requirement_type)
        analysis = self._analyze.analyze(suggested)
        if (
            analysis.overall_status == "ambiguous"
            and analysis.user_assessment
            and analysis.user_assessment.phrases
            and analysis.suggested_requirement
            and not is_broken_requirement(analysis.suggested_requirement)
            and is_valid_suggestion(analysis.suggested_requirement, suggested)
        ):
            suggested = apply_measurable_placeholders(
                sanitize_requirement(analysis.suggested_requirement, idea, details),
                draft.requirement_type,
            )
        missing = list(draft.missing_information)
        for item in analysis.missing_information:
            if item not in missing:
                missing.append(item)
        checks = [QualityCheck.model_validate(item) for item in quality_checks(suggested, idea)]
        ready = draft.ready_to_use and analysis.overall_status == "clean" and all(
            item.passed for item in checks if item.id in {"actor", "shall", "copied"}
        )
        return GenerateResponse(
            idea=idea,
            requirement_type=draft.requirement_type,
            suggested_requirement=suggested,
            explanation=draft.explanation,
            missing_information=missing,
            questions=draft.questions,
            ready_to_use=ready,
            quality_checks=checks,
            analysis=analysis,
        )

    def _draft(
        self,
        idea: str,
        requirement_type: RequirementKind | None,
        details: str | None,
    ) -> _GeneratedDraft:
        llm_draft = self._draft_with_llm(idea, requirement_type, details)
        if llm_draft is not None and not is_broken_requirement(llm_draft.suggested_requirement):
            return llm_draft
        return fallback_generate(idea, requirement_type, details)

    def _draft_with_llm(
        self,
        idea: str,
        requirement_type: RequirementKind | None,
        details: str | None,
    ) -> _GeneratedDraft | None:
        if not self._settings.llm_enabled or not (self._settings.llm_api_key or "").strip():
            return None
        type_line = (
            f"Preferred requirement type: {requirement_type}.\n"
            if requirement_type
            else "Infer the most appropriate requirement type.\n"
        )
        extra = f"Optional details from the user:\n{details}\n" if details else ""
        try:
            raw = complete_chat(
                self._settings,
                GENERATE_SYSTEM_PROMPT,
                f"{type_line}{extra}User idea:\n{idea}",
                json_mode=True,
            )
            payload = json.loads(_extract_object(raw))
            if requirement_type:
                payload["requirement_type"] = requirement_type
            draft = _GeneratedDraft.model_validate(payload)
            draft.suggested_requirement = sanitize_requirement(
                draft.suggested_requirement, idea, details
            )
            return draft
        except (Exception, ValidationError):
            logger.warning("LLM requirement generation failed; using fallback.")
            return None


def fallback_generate(
    idea: str,
    requirement_type: RequirementKind | None = None,
    details: str | None = None,
) -> _GeneratedDraft:
    kind = requirement_type or infer_requirement_kind(f"{idea} {details or ''}")
    if _PASSWORD_RESET.search(idea):
        return _GeneratedDraft(
            requirement_type=kind if requirement_type else "functional",
            suggested_requirement=(
                "The system shall allow registered users to reset their password "
                "using their registered email address."
            ),
            explanation=(
                "The idea names a concrete user action. The requirement states "
                "who can do it and how the reset is initiated, so it can be tested."
            ),
            missing_information=[],
            questions=[],
            ready_to_use=True,
        )
    if _SECURE.search(idea) and not _SECURITY_DETAIL.search(idea):
        return _GeneratedDraft(
            requirement_type=kind if requirement_type else "security",
            suggested_requirement=(
                "The system shall protect [asset] using [specify security control]."
            ),
            explanation=(
                "'Secure' is too broad to test. Choose the control you need, "
                "such as authentication, authorization, encryption, or session policy."
            ),
            missing_information=[
                "What must be protected (accounts, data, sessions).",
                "Authentication and password policy.",
                "Authorization / access control.",
                "Encryption in transit and at rest.",
                "Session timeout and account lockout.",
            ],
            questions=[
                "Which asset or action must be protected?",
                "Do you need login, roles, encryption, or all of these?",
            ],
            ready_to_use=False,
        )
    if _AVAILABLE.search(idea) and "navigate" not in idea.lower():
        return _GeneratedDraft(
            requirement_type=kind if requirement_type else "availability",
            suggested_requirement=(
                "The system shall maintain [X]% availability during each calendar month."
            ),
            explanation="Availability needs a measurable target and a measurement window.",
            missing_information=[
                "Target availability percentage.",
                "The period used to measure it.",
            ],
            questions=["What availability percentage is required?"],
            ready_to_use=False,
        )
    if (
        _FAST_IDEA.search(idea)
        and kind == "performance"
        and not re.search(r"\bnavigate|dashboard|interface\b", idea, re.I)
    ):
        return _GeneratedDraft(
            requirement_type="performance",
            suggested_requirement=(
                "The system shall complete [action] within [maximum response time] under [specified conditions]."
            ),
            explanation=(
                "Speed is not measurable until the action, time limit, and conditions are defined."
            ),
            missing_information=[
                "Maximum acceptable time.",
                "Which page or operation.",
                "Target device or network conditions.",
            ],
            questions=["How fast should the operation complete?"],
            ready_to_use=False,
        )
    suggested = apply_measurable_placeholders(build_requirement(idea, details), kind)
    missing: list[str] = []
    questions: list[str] = []
    if _FAST_IDEA.search(idea) or re.search(r"\[[^\]]+\]", suggested):
        missing.append("Maximum acceptable time or completion limit.")
        questions.append("What time limit should replace the subjective wording?")
    return _GeneratedDraft(
        requirement_type=kind,
        suggested_requirement=suggested,
        explanation=(
            "The informal request was rewritten as a single shall-statement "
            "without copying the original wording."
        ),
        missing_information=missing,
        questions=questions,
        ready_to_use=not missing,
    )


def _extract_object(raw: str) -> str:
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    raise ValueError("not JSON")
