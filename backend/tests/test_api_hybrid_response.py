from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.ambiguity_model import ModelPrediction
from backend.tests.fakes import FakeModel, FakeRewriteService


def _client(prediction: ModelPrediction) -> TestClient:
    app = create_app(
        model=FakeModel(prediction),
        rewrite_service=FakeRewriteService(),
        load_model=False,
    )
    return TestClient(app)


def test_api_quickly_exposes_fused_and_ml_evidence_separately():
    client = _client(
        ModelPrediction(
            classification="ambiguous",
            ambiguity_type="syntax",
            ambiguity_score=56,
            confidence=0.56,
            stage_a_confidence=0.56,
            stage_b_confidence=0.61,
        )
    )
    body = client.post(
        "/api/analyze",
        json={"requirement": "The software should respond quickly"},
    ).json()

    final = body["final_assessment"]
    assert final["status"] == "ambiguous"
    # User-facing score is CLARITY (higher = better).
    assert final["clarity_score"] == 3.4
    assert final["ambiguity_score"] == 6.6
    assert final["score"] == final["clarity_score"]
    # Stage B type is preserved; linguistic phrase remains evidence.
    assert final["type"] == "syntax"
    assert final["ambiguity_type"] == "syntax"
    assert final["severity"] == "high"
    assert body["final_score"] == 3.4
    assert body["clarity_score"] == 3.4
    assert body["fused_ambiguity_score"] == 6.6
    assert body["final_score"] != round(body["confidence"] * 10, 1)

    stage_a = body["ml_prediction"]["stage_a"]
    assert stage_a["label"] == "ambiguous"
    assert stage_a["confidence"] == 0.56
    assert stage_a["source"] == "bert"
    assert stage_a["stage"] == "stage_a"
    assert body["ml_prediction"]["stage_b"]["label"] == "syntax"
    assert body["ml_prediction"]["stage_b"]["source"] == "bert"
    assert body["ml_prediction"]["stage_b_type"] == "syntax"

    findings = body["linguistic_findings"]
    assert findings
    assert findings[0]["phrase"].lower() == "quickly"
    assert findings[0]["type"] == "pragmatic"
    assert findings[0]["source"] == "linguistic"
    assert findings[0]["severity"] == "high"
    assert findings[0]["confidence"] >= 0.9
    assert "[maximum response time]" in findings[0]["suggestion"]

    issue = body["issues"][0]
    assert issue["id"] == "issue-1"
    assert issue["phrase"].lower() == "quickly"
    assert issue["type"] == "pragmatic"
    assert issue["source"] == "linguistic"
    text = "The software should respond quickly"
    assert text[issue["start"] : issue["end"]].lower() == "quickly"

    user = body["user_assessment"]
    assert user["score"] == 3.4
    assert user["clarity_score"] == 3.4
    assert user["ambiguity_score"] == 6.6
    assert user["type_label"] == "Structural"
    assert user["phrases"][0]["text"].lower() == "quickly"


def test_api_measurable_time_has_no_vague_time_finding():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=14,
            confidence=0.86,
        )
    )
    body = client.post(
        "/api/analyze",
        json={"requirement": "The software shall respond within 2 seconds."},
    ).json()
    assert body["final_assessment"]["status"] == "clean"
    assert body["linguistic_findings"] == []
    assert body["issues"] == []
    phrases = [item.get("phrase", "").lower() for item in body["detected_issues"]]
    assert "quickly" not in phrases


def test_api_multiple_findings_have_separate_spans():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=12,
            confidence=0.88,
        )
    )
    text = "The software should respond quickly and support many users."
    body = client.post("/api/analyze", json={"requirement": text}).json()
    findings = body["linguistic_findings"]
    phrases = [item["phrase"].lower() for item in findings]
    assert any("quickly" in phrase for phrase in phrases)
    assert any("many" in phrase for phrase in phrases)
    assert len({item["start"] for item in findings}) == len(findings)
    assert body["final_assessment"]["status"] == "ambiguous"
    assert len(body["issues"]) >= 2


def test_api_low_bert_confidence_still_uses_strong_linguistic_evidence():
    client = _client(
        ModelPrediction(
            classification="ambiguous",
            ambiguity_type="syntax",
            ambiguity_score=22,
            confidence=0.22,
            stage_a_confidence=0.22,
            stage_b_confidence=0.40,
        )
    )
    body = client.post(
        "/api/analyze",
        json={"requirement": "The software should respond quickly"},
    ).json()
    assert body["ml_prediction"]["stage_a"]["confidence"] == 0.22
    assert body["final_assessment"]["status"] == "ambiguous"
    assert body["final_assessment"]["type"] == "syntax"
    assert body["final_assessment"]["ambiguity_score"] < 7.5
    assert body["final_assessment"]["clarity_score"] == round(
        10.0 - body["final_assessment"]["ambiguity_score"], 1
    )
    assert body["final_assessment"]["score"] == body["final_assessment"]["clarity_score"]
    assert body["final_assessment"]["score"] != 2.2
