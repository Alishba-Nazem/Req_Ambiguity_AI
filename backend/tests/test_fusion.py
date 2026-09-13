from backend.services.ambiguity_model import ModelPrediction
from backend.services.fusion import fuse_evidence
from backend.services.linguistic_detector import LinguisticIssue, detect_linguistic_issues


def _issue(phrase: str = "quickly", start: int = 25) -> LinguisticIssue:
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


def test_fusion_prioritizes_linguistic_type_over_stage_b_syntax():
    prediction = ModelPrediction(
        classification="ambiguous",
        ambiguity_type="syntax",
        ambiguity_score=52,
        confidence=0.56,
    )
    fused = fuse_evidence(prediction, [_issue()])
    assert fused.status == "ambiguous"
    assert fused.ambiguity_type == "pragmatic"
    assert fused.type_source == "hybrid"
    assert fused.score >= 7.5
    assert fused.score != 5.2
    assert fused.severity == "high"


def test_fusion_preserves_ml_only_when_no_linguistic_hits():
    prediction = ModelPrediction(
        classification="ambiguous",
        ambiguity_type="syntactic",
        ambiguity_score=72,
        confidence=0.77,
    )
    fused = fuse_evidence(prediction, [])
    assert fused.status == "ambiguous"
    assert fused.ambiguity_type == "syntactic"
    assert fused.type_source == "stage_b"
    assert fused.score == 7.2
    assert fused.evidence_source == "bert"


def test_fusion_strong_linguistic_not_cancelled_by_uncertain_bert():
    prediction = ModelPrediction(
        classification="ambiguous",
        ambiguity_type="syntax",
        ambiguity_score=56,
        confidence=0.56,
    )
    fused = fuse_evidence(prediction, [_issue()])
    assert fused.score >= 7.5
    assert prediction.confidence == 0.56


def test_fusion_multiple_findings_aggregate_score():
    issues = detect_linguistic_issues(
        "The system should respond quickly and provide a user-friendly interface."
    )
    assert len(issues) >= 2
    prediction = ModelPrediction(
        classification="clean",
        ambiguity_type=None,
        ambiguity_score=10,
        confidence=0.90,
    )
    fused = fuse_evidence(prediction, issues)
    assert fused.status == "ambiguous"
    assert fused.ambiguity_type == "pragmatic"
    assert fused.score >= 7.5
