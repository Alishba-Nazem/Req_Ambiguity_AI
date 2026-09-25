from backend.services.ambiguity_model import ModelPrediction
from backend.services.fusion import clarity_from_ambiguity, fuse_evidence
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


def test_clarity_from_ambiguity():
    assert clarity_from_ambiguity(0.0) == 10.0
    assert clarity_from_ambiguity(0.9) == 9.1
    assert clarity_from_ambiguity(7.8) == 2.2
    assert clarity_from_ambiguity(10.0) == 0.0
    assert clarity_from_ambiguity(11.0) == 0.0
    assert clarity_from_ambiguity(-1.0) == 10.0


def test_fusion_keeps_stage_b_type_when_linguistic_hits():
    prediction = ModelPrediction(
        classification="ambiguous",
        ambiguity_type="syntax",
        ambiguity_score=52,
        confidence=0.56,
    )
    fused = fuse_evidence(prediction, [_issue()])
    assert fused.status == "ambiguous"
    # Stage B remains primary; linguistic is evidence only.
    assert fused.ambiguity_type == "syntax"
    assert fused.type_source == "stage_b"
    # Proportional blend — no 7.8 floor.
    # ml=5.2, ling≈7.6 → 0.6*5.2 + 0.4*7.6 + 0.2 = 6.36 → 6.4
    assert fused.score == 6.4
    assert fused.clarity_score == 3.6
    assert fused.clarity_score == clarity_from_ambiguity(fused.score)
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
    assert fused.clarity_score == 2.8
    assert fused.evidence_source == "bert"


def test_fusion_linguistic_does_not_force_78_floor_on_uncertain_bert():
    prediction = ModelPrediction(
        classification="ambiguous",
        ambiguity_type="syntax",
        ambiguity_score=56,
        confidence=0.56,
    )
    fused = fuse_evidence(prediction, [_issue()])
    assert fused.score < 7.5
    assert fused.score > 5.0
    assert prediction.confidence == 0.56


def test_fusion_multiple_findings_use_stage_b_when_present():
    issues = detect_linguistic_issues(
        "The system should respond quickly and provide a user-friendly interface."
    )
    assert len(issues) >= 2
    prediction = ModelPrediction(
        classification="ambiguous",
        ambiguity_type="lexical",
        ambiguity_score=40,
        confidence=0.70,
    )
    fused = fuse_evidence(prediction, issues)
    assert fused.status == "ambiguous"
    assert fused.ambiguity_type == "lexical"
    assert fused.type_source == "stage_b"
    assert fused.clarity_score == clarity_from_ambiguity(fused.score)


def test_fusion_uses_linguistic_type_only_when_stage_b_missing():
    issues = detect_linguistic_issues("The system shall respond quickly.")
    assert any(item.phrase.lower() == "quickly" for item in issues)
    prediction = ModelPrediction(
        classification="clean",
        ambiguity_type=None,
        ambiguity_score=10,
        confidence=0.90,
    )
    fused = fuse_evidence(prediction, issues)
    assert fused.status == "ambiguous"
    assert fused.ambiguity_type == "pragmatic"
    assert fused.type_source == "linguistic"
    # Clean Stage A (ml=1.0) + strong linguistic (~7.6): blend ≈ 3.6, not ≥7.8
    assert fused.score < 7.0
    assert fused.clarity_score > 3.0
