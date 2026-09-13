"""Analyze a requirement: BERT, linguistic checks, and optional LLM reasoning."""

from __future__ import annotations

import logging

from backend.config import Settings, get_settings
from backend.schemas import (
    AnalyzeResponse,
    DetectedIssue,
    FinalAssessment,
    IssueSeverity,
    IssueView,
    LlmAnalysis,
    LlmPhraseView,
    MlPrediction,
    StageAPrediction,
    StageBPrediction,
)
from backend.services.ambiguity_model import (
    ModelPrediction,
    ModelUnavailableError,
    TwoStageAmbiguityModel,
)
from backend.services.explanation import explain
from backend.services.fusion import fuse_evidence
from backend.services.linguistic_detector import LinguisticIssue, detect_linguistic_issues
from backend.services.llm_analyzer import (
    LLM_UNAVAILABLE,
    LlmAnalyzer,
    LlmPhrase,
    LlmReasoningResult,
)
from backend.services.rewrite import RewriteService, compose_improved_requirement
from backend.services.user_assessment import build_user_assessment

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


class AnalyzeService:
    """Combine two-stage BERT with linguistic and optional LLM evidence.

    The BERT model is trained on the provided labeled dataset and therefore
    reflects the dataset's annotation patterns. The linguistic layer supplements
    the model by detecting requirements-quality issues that may not be
    represented reliably in the training labels. The LLM layer reasons
    independently and must not overwrite the raw Stage A/B prediction.
    AnalyzeService never mutates the Stage A/B prediction. Fusion produces a
    separate final assessment.
    """

    def __init__(
        self,
        model: TwoStageAmbiguityModel,
        rewrite_service: RewriteService | None = None,
        llm_analyzer: LlmAnalyzer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._model = model
        self._rewrite = rewrite_service or RewriteService(self._settings)
        self._llm = llm_analyzer or LlmAnalyzer(self._settings)

    def analyze(self, requirement: str) -> AnalyzeResponse:
        prediction = self._predict_bert(requirement)
        issues = self._detect_linguistic(requirement)
        if prediction is None and not issues:
            raise ModelUnavailableError(
                "Inference failed while classifying the requirement."
            )

        preliminary = fuse_evidence(prediction, issues)
        llm_result = self._analyze_llm(requirement, prediction, issues, preliminary)
        fused = fuse_evidence(prediction, issues, llm_result)
        primary = issues[0] if issues else None
        llm_primary = _primary_llm_phrase(llm_result)
        suggested = compose_improved_requirement(
            requirement,
            issues,
            llm_result,
            fused.ambiguity_type,
        )
        if not issues and not (llm_result.available and llm_result.phrases):
            suggested = self._suggestion(
                requirement, fused.ambiguity_type, primary, llm_primary
            )
        user = build_user_assessment(
            fused, issues, llm_result, suggested, requirement
        )

        detected = [
            DetectedIssue(
                phrase=item.phrase,
                start=item.start,
                end=item.end,
                ambiguity_type=item.ambiguity_type,
                category=item.category,
                reason=item.reason,
                suggestion=item.suggestion,
                severity=item.severity,
                confidence=item.confidence,
                source="linguistic",
            )
            for item in issues
        ]

        issue_views = [
            IssueView(
                id=f"issue-{index + 1}",
                phrase=item.phrase,
                start=item.start,
                end=item.end,
                type=item.ambiguity_type,
                ambiguity_type=item.ambiguity_type,
                severity=item.severity,
                confidence=item.confidence,
                source="linguistic",
                reason=item.reason,
                suggestion=item.suggestion,
                category=item.category,
            )
            for index, item in enumerate(detected)
        ]
        issue_views.extend(
            _llm_issue_views(requirement, llm_result, issues, start_index=len(issue_views))
        )

        flagged_phrase, flagged_start, flagged_end = _flagged_span(primary, llm_primary)

        return AnalyzeResponse(
            requirement=requirement,
            classification=prediction.classification if prediction else "clean",
            ambiguity_type=fused.ambiguity_type,
            ambiguity_score=prediction.ambiguity_score if prediction else 0,
            confidence=_stage_a_confidence(prediction),
            explanation=explain(
                requirement,
                prediction.classification if prediction else "unavailable",
                fused.ambiguity_type,
                fused.type_source,
                overall_status=fused.status,
                issues=issues,
                llm=llm_result,
            ),
            suggested_requirement=suggested,
            type_source=fused.type_source,
            flagged_phrase=flagged_phrase,
            flagged_start=flagged_start,
            flagged_end=flagged_end,
            overall_status=fused.status,
            ml_prediction=_ml_view(prediction),
            detected_issues=detected,
            linguistic_findings=detected,
            issues=issue_views,
            linguistic_severity=_highest_severity(detected),
            final_assessment=FinalAssessment(
                status=fused.status,
                score=fused.score,
                severity=fused.severity,
                ambiguity_type=fused.ambiguity_type,
                type=fused.ambiguity_type,
                source=fused.evidence_source,
            ),
            final_score=fused.score,
            llm_analysis=_llm_view(llm_result),
            user_assessment=user,
            missing_information=user.missing_information,
        )

    def _predict_bert(self, requirement: str) -> ModelPrediction | None:
        try:
            return self._model.predict(requirement)
        except Exception:
            logger.exception(
                "BERT inference failed; continuing with linguistic analysis"
            )
            return None

    def _detect_linguistic(self, requirement: str) -> list[LinguisticIssue]:
        try:
            return detect_linguistic_issues(requirement)
        except Exception:
            logger.exception("Linguistic detection failed; continuing with BERT analysis")
            return []

    def _analyze_llm(
        self,
        requirement: str,
        prediction: ModelPrediction | None,
        issues: list[LinguisticIssue],
        preliminary,
    ) -> LlmReasoningResult:
        try:
            return self._llm.analyze(requirement, prediction, issues, preliminary)
        except Exception:
            logger.warning("LLM analysis failed; continuing without LLM.")
            return LlmReasoningResult.unavailable(LLM_UNAVAILABLE)

    def _suggestion(
        self,
        requirement: str,
        ambiguity_type: str | None,
        primary: LinguisticIssue | None,
        llm_primary: LlmPhrase | None,
    ) -> str:
        if primary is not None:
            return primary.suggestion
        if llm_primary is not None and llm_primary.suggestion:
            return llm_primary.suggestion
        return self._rewrite.rewrite(requirement, ambiguity_type)


def _highest_severity(issues: list[DetectedIssue]) -> IssueSeverity | None:
    if not issues:
        return None
    return min(issues, key=lambda item: _SEVERITY_RANK.get(item.severity, 9)).severity


def _stage_a_confidence(prediction: ModelPrediction | None) -> float:
    if prediction is None:
        return 0.0
    if prediction.stage_a_confidence is not None:
        return prediction.stage_a_confidence
    return prediction.confidence


def _ml_view(prediction: ModelPrediction | None) -> MlPrediction | None:
    if prediction is None:
        return None
    stage_a_confidence = _stage_a_confidence(prediction)
    stage_b = None
    if prediction.ambiguity_type:
        stage_b = StageBPrediction(
            label=prediction.ambiguity_type,
            confidence=prediction.stage_b_confidence,
            source="bert",
            stage="stage_b",
        )
    return MlPrediction(
        classification=prediction.classification,
        confidence=stage_a_confidence,
        ambiguity_score=prediction.ambiguity_score,
        source="bert",
        stage="stage_a",
        stage_b_type=prediction.ambiguity_type,
        stage_a=StageAPrediction(
            label=prediction.classification,
            confidence=stage_a_confidence,
            source="bert",
            stage="stage_a",
        ),
        stage_b=stage_b,
    )


def _llm_view(result: LlmReasoningResult) -> LlmAnalysis:
    if not result.available:
        return LlmAnalysis(available=False, reason=result.reason or LLM_UNAVAILABLE)
    return LlmAnalysis(
        available=True,
        is_ambiguous=result.is_ambiguous,
        score=result.ambiguity_score,
        type=result.ambiguity_type,
        ambiguity_type=result.ambiguity_type,
        severity=result.severity,
        confidence=result.confidence,
        explanation=result.explanation,
        ambiguous_phrases=[
            LlmPhraseView(
                text=item.text,
                reason=item.reason,
                suggestion=item.suggestion,
                start=item.start,
                end=item.end,
            )
            for item in result.phrases
        ],
        source="llm",
    )


def _primary_llm_phrase(result: LlmReasoningResult) -> LlmPhrase | None:
    if not result.available:
        return None
    for item in result.phrases:
        if item.start is not None and item.end is not None:
            return item
    return result.phrases[0] if result.phrases else None


def _flagged_span(
    primary: LinguisticIssue | None,
    llm_primary: LlmPhrase | None,
) -> tuple[str | None, int | None, int | None]:
    if primary is not None:
        return primary.phrase, primary.start, primary.end
    if llm_primary is not None and llm_primary.start is not None:
        return llm_primary.text, llm_primary.start, llm_primary.end
    return None, None, None


def _llm_issue_views(
    requirement: str,
    result: LlmReasoningResult,
    issues: list[LinguisticIssue],
    start_index: int,
) -> list[IssueView]:
    if not result.available or not result.is_ambiguous:
        return []
    views: list[IssueView] = []
    offset = start_index
    for item in result.phrases:
        if item.start is None or item.end is None:
            continue
        if _overlaps_linguistic(item, issues):
            continue
        if requirement[item.start : item.end].strip() == requirement.strip() and len(
            requirement.split()
        ) > 3:
            continue
        offset += 1
        views.append(
            IssueView(
                id=f"issue-{offset}",
                phrase=item.text,
                start=item.start,
                end=item.end,
                type=result.ambiguity_type or "semantic",
                ambiguity_type=result.ambiguity_type or "semantic",
                severity=result.severity or "medium",
                confidence=result.confidence or 0.0,
                source="llm",
                reason=item.reason,
                suggestion=item.suggestion,
                category="contextual",
            )
        )
    return views


def _overlaps_linguistic(phrase: LlmPhrase, issues: list[LinguisticIssue]) -> bool:
    if phrase.start is None or phrase.end is None:
        return False
    for issue in issues:
        if not (phrase.end <= issue.start or phrase.start >= issue.end):
            return True
        if issue.phrase.lower() in phrase.text.lower() or phrase.text.lower() in issue.phrase.lower():
            return True
    return False
