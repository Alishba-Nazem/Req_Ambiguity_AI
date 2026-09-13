"""Build the user-facing assessment from fused evidence.

Technical pipeline details stay in ml_prediction / llm_analysis.
"""

from __future__ import annotations

from backend.schemas import UserAssessment, UserPhrase
from backend.services.fusion import FusionResult
from backend.services.linguistic_detector import LinguisticIssue
from backend.services.llm_analyzer import LlmReasoningResult
from backend.services.requirement_text import (
    infer_requirement_kind,
    requirement_kind_label,
    score_band,
)

_MISSING = {
    "unmeasurable_time": "Maximum acceptable response or completion time.",
    "unclear_quantity": "The expected number, capacity, or volume.",
    "subjective_quality": "A testable acceptance criterion for the quality.",
    "vague_degree": "A measurable threshold for this quality.",
    "open_ended": "The complete set of cases, items, or conditions.",
    "vague_frequency": "How often the action must occur.",
    "unmeasurable_availability": "Target availability percentage and the measurement period.",
    "unmeasurable_quality": "The specific control or criterion to test.",
    "contextual": "The missing actor, reference, or condition.",
}

_TYPE_LABELS = {
    "lexical": "Lexical / wording",
    "syntactic": "Syntactic",
    "semantic": "Semantic",
    "syntax": "Structural",
    "pragmatic": "Pragmatic / vague",
}


def build_user_assessment(
    fused: FusionResult,
    issues: list[LinguisticIssue],
    llm: LlmReasoningResult | None,
    suggested: str | None,
    requirement: str = "",
) -> UserAssessment:
    phrases = _user_phrases(issues, llm)
    missing = _missing_information(issues, llm)
    needs_work = fused.status == "ambiguous" or bool(phrases)
    why = _why(needs_work, phrases, issues, llm)
    kind = infer_requirement_kind(requirement or suggested or "")
    return UserAssessment(
        status="needs_improvement" if needs_work else "clear",
        title="Needs improvement" if needs_work else "Clear",
        ambiguity_type=fused.ambiguity_type if needs_work else None,
        type_label=(
            _TYPE_LABELS.get(fused.ambiguity_type or "", fused.ambiguity_type)
            if needs_work and fused.ambiguity_type
            else None
        ),
        why=why,
        suggested_requirement=suggested if needs_work else suggested,
        missing_information=missing,
        phrases=phrases,
        requirement_type=kind,
        requirement_type_label=requirement_kind_label(kind),
        score=fused.score,
        score_label=score_band(fused.score),
    )


def _user_phrases(
    issues: list[LinguisticIssue],
    llm: LlmReasoningResult | None,
) -> list[UserPhrase]:
    seen: set[tuple[int, int, str]] = set()
    phrases: list[UserPhrase] = []
    for item in issues:
        key = (item.start, item.end, item.phrase.lower())
        if key in seen:
            continue
        seen.add(key)
        phrases.append(
            UserPhrase(
                text=item.phrase,
                start=item.start,
                end=item.end,
                ambiguity_type=item.ambiguity_type,
                type_label=_TYPE_LABELS.get(item.ambiguity_type, item.ambiguity_type),
                severity=item.severity,
                why=item.reason,
                suggestion=item.suggestion,
                specify=_MISSING.get(item.category),
            )
        )
    if llm and llm.available and llm.is_ambiguous:
        for item in llm.phrases:
            if item.start is None or item.end is None:
                continue
            key = (item.start, item.end, item.text.lower())
            if any(
                not (item.end <= existing.start or item.start >= existing.end)
                for existing in issues
            ):
                continue
            if key in seen:
                continue
            seen.add(key)
            phrases.append(
                UserPhrase(
                    text=item.text,
                    start=item.start,
                    end=item.end,
                    ambiguity_type=llm.ambiguity_type,
                    type_label=_TYPE_LABELS.get(llm.ambiguity_type or "", None),
                    severity=llm.severity,
                    why=item.reason,
                    suggestion=item.suggestion,
                    specify=_MISSING.get("contextual"),
                )
            )
    return phrases


def _missing_information(
    issues: list[LinguisticIssue],
    llm: LlmReasoningResult | None,
) -> list[str]:
    values: list[str] = []
    for item in issues:
        hint = _MISSING.get(item.category)
        if hint and hint not in values:
            values.append(hint)
    if llm and llm.available and llm.is_ambiguous and not issues:
        hint = _MISSING["contextual"]
        if hint not in values:
            values.append(hint)
    return values


def _why(
    needs_work: bool,
    phrases: list[UserPhrase],
    issues: list[LinguisticIssue],
    llm: LlmReasoningResult | None,
) -> str:
    if not needs_work:
        return "The requirement already includes a measurable, testable condition."
    if phrases:
        first = phrases[0]
        return first.why
    if issues:
        return issues[0].reason
    if llm and llm.available and llm.explanation:
        return llm.explanation
    return "The wording leaves an important implementation decision unspecified."
