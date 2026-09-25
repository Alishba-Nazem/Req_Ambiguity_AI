from backend.services.ambiguity_model import ModelPrediction
from backend.services.fusion import fuse_evidence
from backend.services.linguistic_detector import LinguisticIssue, detect_linguistic_issues
from backend.services.llm_analyzer import LlmPhrase, LlmReasoningResult
from backend.tests.fakes import llm_quickly_result


def _issue(phrase: str = "quickly", start: int = 28) -> LinguisticIssue:
    return LinguisticIssue(
        phrase=phrase,
        start=start,
        end=start + len(phrase),
        ambiguity_type="pragmatic",
        category="unmeasurable_time",
        reason=f"The term '{phrase}' does not define an objective response-time threshold.",
        suggestion="The software shall respond within [X] seconds.",
        severity="high",
        confidence=0.95,
    )


def test_unavailable_llm_matches_bert_linguistic_fusion():
    prediction = ModelPrediction(
        classification="ambiguous",
        ambiguity_type="syntax",
        ambiguity_score=56,
        confidence=0.56,
    )
    issues = [_issue()]
    without = fuse_evidence(prediction, issues)
    with_llm = fuse_evidence(
        prediction,
        issues,
        LlmReasoningResult.unavailable("Optional review unavailable"),
    )
    assert with_llm == without
    # ml=5.6, ling=7.6 → 0.6*5.6 + 0.4*7.6 + 0.2 = 6.6
    assert without.score == 6.6
    assert without.clarity_score == 3.4
    assert without.ambiguity_type == "syntax"


def test_llm_confirmation_raises_score_but_keeps_stage_b_type():
    prediction = ModelPrediction(
        classification="ambiguous",
        ambiguity_type="syntax",
        ambiguity_score=56,
        confidence=0.56,
        stage_a_confidence=0.56,
        stage_b_confidence=0.61,
    )
    fused = fuse_evidence(
        prediction,
        [_issue()],
        llm_quickly_result("The software should respond quickly."),
    )
    assert fused.status == "ambiguous"
    assert fused.ambiguity_type == "syntax"
    assert fused.type_source == "stage_b"
    assert fused.score == 7.1  # 6.6 + 0.5 confirmation
    assert fused.clarity_score == 2.9
    assert fused.evidence_source == "hybrid"


def test_llm_can_mark_contextual_ambiguity_when_bert_is_clean():
    prediction = ModelPrediction(
        classification="clean",
        ambiguity_type=None,
        ambiguity_score=18,
        confidence=0.82,
        stage_a_confidence=0.82,
    )
    llm = LlmReasoningResult(
        available=True,
        is_ambiguous=True,
        ambiguity_score=7.6,
        ambiguity_type="semantic",
        severity="high",
        confidence=0.91,
        explanation="The pronoun they can refer to users or records.",
        phrases=[
            LlmPhrase(
                text="they",
                reason="Unclear whether they refers to users or records.",
                suggestion="Authorized users may access the records if the records are valid.",
                start=42,
                end=46,
            )
        ],
    )
    fused = fuse_evidence(prediction, [], llm)
    assert fused.status == "ambiguous"
    assert fused.ambiguity_type == "semantic"
    assert fused.type_source == "llm"
    assert fused.score >= 7.0
    assert fused.score != 1.8
    assert fused.clarity_score == round(10.0 - fused.score, 1)


def test_llm_clean_does_not_cancel_linguistic_evidence():
    prediction = ModelPrediction(
        classification="clean",
        ambiguity_type=None,
        ambiguity_score=12,
        confidence=0.88,
    )
    llm = LlmReasoningResult(
        available=True,
        is_ambiguous=False,
        ambiguity_score=1.2,
        confidence=0.80,
        explanation="No additional ambiguity found.",
        phrases=[],
    )
    fused = fuse_evidence(prediction, [_issue()], llm)
    assert fused.status == "ambiguous"
    assert fused.ambiguity_type == "pragmatic"
    assert fused.type_source == "linguistic"
    # Proportional blend, not ≥7.5 floor
    assert fused.score < 7.0
    assert fused.clarity_score > 3.0


def test_measurable_requirement_stays_low_when_llm_agrees_clear():
    issues = detect_linguistic_issues("The software shall respond within 2 seconds.")
    assert issues == []
    prediction = ModelPrediction(
        classification="clean",
        ambiguity_type=None,
        ambiguity_score=8,
        confidence=0.94,
    )
    llm = LlmReasoningResult(
        available=True,
        is_ambiguous=False,
        ambiguity_score=1.0,
        confidence=0.96,
        explanation="The response time is measurable.",
        phrases=[],
    )
    fused = fuse_evidence(prediction, issues, llm)
    assert fused.status == "clean"
    assert fused.score == 0.8
    assert fused.clarity_score == 9.2
