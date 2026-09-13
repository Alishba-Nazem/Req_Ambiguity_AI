"""Evidence fusion: BERT + linguistic findings + optional LLM → final assessment.

The BERT model is trained on the provided labeled dataset and therefore
reflects the dataset's annotation patterns. This layer never mutates the
raw ML prediction. It combines independent evidence into a separate
sentence-level assessment. Linguistic detection does not catch all
ambiguity. The LLM is an additional reasoning source, not a replacement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.schemas import (
    AmbiguityType,
    Classification,
    EvidenceSource,
    IssueSeverity,
    TypeSource,
)
from backend.services.ambiguity_model import ModelPrediction
from backend.services.linguistic_detector import LinguisticIssue
from backend.services.llm_analyzer import LlmPhrase, LlmReasoningResult

logger = logging.getLogger(__name__)

_SEVERITY_SCORE = {"high": 8.0, "medium": 6.0, "low": 4.0}
_STRONG_HIGH_FLOOR = 7.8


@dataclass(frozen=True)
class FusionResult:
    status: Classification
    score: float
    severity: IssueSeverity | None
    ambiguity_type: AmbiguityType | None
    type_source: TypeSource | None
    evidence_source: EvidenceSource


def fuse_evidence(
    prediction: ModelPrediction | None,
    issues: list[LinguisticIssue],
    llm: LlmReasoningResult | None = None,
) -> FusionResult:
    """Combine ML, linguistic, and optional LLM evidence.

    When LLM evidence is missing or unavailable, the result matches the
    existing BERT + linguistic fusion exactly.
    """
    ml_ambiguous = bool(prediction and prediction.classification == "ambiguous")
    has_linguistic = bool(issues)
    status: Classification = (
        "ambiguous" if ml_ambiguous or has_linguistic else "clean"
    )
    ml_10 = _ml_score_out_of_ten(prediction)
    ling_10 = _linguistic_score_out_of_ten(issues)
    score = _combined_score(ml_10, ling_10, ml_ambiguous, issues)
    ambiguity_type, type_source = _select_type(prediction, issues)
    evidence_source = _evidence_source(has_linguistic, prediction, llm=None)
    severity = _final_severity(status, score, issues)

    result = FusionResult(
        status=status,
        score=score,
        severity=severity,
        ambiguity_type=ambiguity_type,
        type_source=type_source,
        evidence_source=evidence_source,
    )
    if llm is None or not llm.available:
        _log_fusion(prediction, issues, ml_10, result, llm)
        return result

    merged = _merge_llm(result, prediction, issues, llm)
    _log_fusion(prediction, issues, ml_10, merged, llm)
    return merged


def _ml_score_out_of_ten(prediction: ModelPrediction | None) -> float:
    if prediction is None:
        return 0.0
    return max(0.0, min(10.0, prediction.ambiguity_score / 10.0))


def _linguistic_score_out_of_ten(issues: list[LinguisticIssue]) -> float:
    if not issues:
        return 0.0
    best = max(
        _SEVERITY_SCORE.get(item.severity, 4.0) * item.confidence for item in issues
    )
    extra = min(1.2, 0.4 * (len(issues) - 1))
    return min(10.0, best + extra)


def _combined_score(
    ml_10: float,
    ling_10: float,
    ml_ambiguous: bool,
    issues: list[LinguisticIssue],
) -> float:
    if ling_10 <= 0:
        return round(ml_10, 1)
    strong_high = any(
        item.severity == "high" and item.confidence >= 0.85 for item in issues
    )
    floor = _STRONG_HIGH_FLOOR if strong_high else 0.0
    combined = max(ml_10, ling_10, floor)
    if ml_ambiguous and ling_10 > 0:
        combined = min(10.0, combined + 0.2)
    return round(combined, 1)


def _merge_llm(
    base: FusionResult,
    prediction: ModelPrediction | None,
    issues: list[LinguisticIssue],
    llm: LlmReasoningResult,
) -> FusionResult:
    """Apply LLM evidence without averaging scores or hiding disagreement."""
    status = base.status
    score = base.score
    ambiguity_type = base.ambiguity_type
    type_source = base.type_source
    llm_ambiguous = bool(llm.is_ambiguous)
    llm_score = float(llm.ambiguity_score) if llm.ambiguity_score is not None else 0.0
    llm_conf = float(llm.confidence) if llm.confidence is not None else 0.0
    confirmed = llm_ambiguous and _phrases_overlap(issues, llm.phrases)
    ml_ambiguous = bool(prediction and prediction.classification == "ambiguous")
    ml_confidence = 0.0
    if prediction is not None:
        ml_confidence = (
            prediction.stage_a_confidence
            if prediction.stage_a_confidence is not None
            else prediction.confidence
        )
    ml_uncertain = (not ml_ambiguous) or ml_confidence < 0.60

    if confirmed:
        status = "ambiguous"
        score = min(10.0, score + 0.5)
    elif llm_ambiguous and llm_conf >= 0.70 and ml_uncertain and not issues:
        status = "ambiguous"
        score = max(score, min(10.0, max(7.0, llm_score)))
        if llm.ambiguity_type:
            ambiguity_type = llm.ambiguity_type
            type_source = (
                "hybrid" if prediction and prediction.ambiguity_type else "llm"
            )
    elif ml_ambiguous and issues and llm_ambiguous:
        score = min(10.0, score + 0.2)

    evidence_source = _evidence_source(bool(issues), prediction, llm)
    severity = _final_severity(status, score, issues, llm)
    return FusionResult(
        status=status,
        score=round(score, 1),
        severity=severity,
        ambiguity_type=ambiguity_type,
        type_source=type_source,
        evidence_source=evidence_source,
    )


def _phrases_overlap(
    issues: list[LinguisticIssue],
    phrases: list[LlmPhrase],
) -> bool:
    for issue in issues:
        issue_text = issue.phrase.lower()
        for phrase in phrases:
            llm_text = phrase.text.lower()
            if issue_text in llm_text or llm_text in issue_text:
                return True
            if (
                phrase.start is not None
                and phrase.end is not None
                and not (phrase.end <= issue.start or phrase.start >= issue.end)
            ):
                return True
    return False


def _select_type(
    prediction: ModelPrediction | None,
    issues: list[LinguisticIssue],
) -> tuple[AmbiguityType | None, TypeSource | None]:
    """Phrase-specific linguistic type wins over Stage B sentence type."""
    if issues:
        ranked = sorted(
            issues,
            key=lambda item: (
                0 if item.severity == "high" else 1 if item.severity == "medium" else 2,
                -item.confidence,
                item.start,
            ),
        )
        linguistic_type = ranked[0].ambiguity_type
        stage_b_type = prediction.ambiguity_type if prediction else None
        if stage_b_type:
            return linguistic_type, "hybrid"
        return linguistic_type, "linguistic"
    if prediction and prediction.ambiguity_type:
        return prediction.ambiguity_type, "stage_b"
    return None, None


def _evidence_source(
    has_linguistic: bool,
    prediction: ModelPrediction | None,
    llm: LlmReasoningResult | None = None,
) -> EvidenceSource:
    has_ml = prediction is not None
    has_llm = bool(llm and llm.available)
    sources = sum([has_linguistic, has_ml, has_llm])
    if sources >= 2:
        return "hybrid"
    if has_llm:
        return "llm"
    if has_linguistic:
        return "linguistic"
    if has_ml:
        return "bert"
    return "linguistic"


def _final_severity(
    status: Classification,
    score: float,
    issues: list[LinguisticIssue],
    llm: LlmReasoningResult | None = None,
) -> IssueSeverity | None:
    if status == "clean":
        return None
    if any(item.severity == "high" for item in issues) or score >= 7.5:
        return "high"
    if llm and llm.available and llm.is_ambiguous and llm.severity == "high":
        return "high"
    if score >= 4.5:
        return "medium"
    return "low"


def _log_fusion(
    prediction: ModelPrediction | None,
    issues: list[LinguisticIssue],
    ml_10: float,
    result: FusionResult,
    llm: LlmReasoningResult | None,
) -> None:
    llm_state = "unavailable"
    if llm is not None and llm.available:
        llm_state = f"ambiguous={llm.is_ambiguous} score={llm.ambiguity_score}"
    logger.info(
        "Fusion BERT=%s p_amb=%.3f type=%s | linguistic=%s | llm=%s | "
        "final status=%s score=%.1f type=%s source=%s",
        prediction.classification if prediction else "unavailable",
        ml_10 / 10.0,
        prediction.ambiguity_type if prediction else None,
        [(item.phrase, item.category, item.confidence) for item in issues],
        llm_state,
        result.status,
        result.score,
        result.ambiguity_type,
        result.evidence_source,
    )
