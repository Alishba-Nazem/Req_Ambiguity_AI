from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.ambiguity_model import ModelPrediction
from backend.tests.fakes import FakeModel, FakeRewriteService

CLEAN_TEXT = "The system shall lock the account after 5 failed login attempts."
AMBIGUOUS_TEXT = "The system should respond quickly."


def _client(prediction: ModelPrediction) -> TestClient:
    app = create_app(
        model=FakeModel(prediction),
        rewrite_service=FakeRewriteService(),
        load_model=False,
    )
    return TestClient(app)


def test_empty_requirement_rejected():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=0,
            confidence=1.0,
        )
    )
    response = client.post("/api/analyze", json={"requirement": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_whitespace_requirement_rejected():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=0,
            confidence=1.0,
        )
    )
    response = client.post("/api/analyze", json={"requirement": "   "})
    assert response.status_code == 422
    assert "empty" in response.json()["error"].lower() or "whitespace" in response.json()["error"].lower()


def test_missing_requirement_rejected():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=0,
            confidence=1.0,
        )
    )
    response = client.post("/api/analyze", json={})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert "requirement" in response.json()["error"].lower()


def test_invalid_json_rejected():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=0,
            confidence=1.0,
        )
    )
    response = client.post(
        "/api/analyze",
        content="{not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_extremely_long_requirement_rejected():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=0,
            confidence=1.0,
        )
    )
    response = client.post("/api/analyze", json={"requirement": "x" * 2001})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_analyze_without_model_returns_503():
    app = create_app(load_model=False, rewrite_service=FakeRewriteService())
    client = TestClient(app)
    response = client.post("/api/analyze", json={"requirement": CLEAN_TEXT})
    assert response.status_code == 503
    assert response.json()["code"] == "model_unavailable"
    assert "error" in response.json()


def test_valid_requirement_clean_response_structure():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=8,
            confidence=0.94,
        )
    )
    response = client.post("/api/analyze", json={"requirement": CLEAN_TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["requirement"] == CLEAN_TEXT
    assert body["classification"] == "clean"
    assert body["ambiguity_type"] is None
    assert body["type_source"] is None
    assert body["flagged_phrase"] is None
    assert body["overall_status"] == "clean"
    assert body["detected_issues"] == []
    assert body["ml_prediction"]["classification"] == "clean"
    assert body["ml_prediction"]["confidence"] == 0.94
    assert body["ml_prediction"]["ambiguity_score"] == 8
    assert body["ambiguity_score"] == 8
    assert body["confidence"] == 0.94
    assert isinstance(body["explanation"], str) and body["explanation"]
    assert "specific and measurable" in body["explanation"].lower()
    assert "bert" not in body["explanation"].lower()
    assert body["suggested_requirement"] == (
        "The system shall respond within [specify maximum response time]."
    )


def test_clean_with_vague_term_gets_heuristic_type():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=11,
            confidence=0.89,
        )
    )
    response = client.post("/api/analyze", json={"requirement": AMBIGUOUS_TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["classification"] == "clean"
    assert body["ml_prediction"]["classification"] == "clean"
    assert body["ml_prediction"]["confidence"] == 0.89
    assert body["ml_prediction"]["ambiguity_score"] == 11
    assert body["ambiguity_score"] == 11
    assert body["confidence"] == 0.89
    assert body["overall_status"] == "ambiguous"
    assert body["final_assessment"]["status"] == "ambiguous"
    # Clarity is user-facing; fused ambiguity is lower without the 7.8 floor.
    assert body["final_assessment"]["ambiguity_score"] < 7.0
    assert body["final_assessment"]["clarity_score"] > 3.0
    assert body["final_assessment"]["score"] == body["final_assessment"]["clarity_score"]
    assert body["final_score"] == body["final_assessment"]["score"]
    assert body["ambiguity_type"] == "pragmatic"
    assert body["type_source"] == "linguistic"
    assert body["flagged_phrase"].lower() == "quickly"
    assert body["flagged_start"] == AMBIGUOUS_TEXT.lower().index("quickly")
    assert body["flagged_end"] == body["flagged_start"] + len("quickly")
    assert body["linguistic_severity"] == "high"
    assert len(body["detected_issues"]) == 1
    issue = body["detected_issues"][0]
    assert issue["phrase"].lower() == "quickly"
    assert issue["ambiguity_type"] == "pragmatic"
    assert issue["source"] == "linguistic"
    assert issue["severity"] == "high"
    assert "[X]" in issue["suggestion"]
    assert "quickly" in body["explanation"].lower()
    assert "pragmatic" in body["explanation"].lower()
    assert "bert" not in body["explanation"].lower()
    assert "llm" not in body["explanation"].lower()


def test_quantity_and_subjective_api_overlay():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=9,
            confidence=0.91,
        )
    )
    many = client.post(
        "/api/analyze",
        json={"requirement": "The system shall process many requests."},
    ).json()
    assert many["classification"] == "clean"
    assert many["overall_status"] == "ambiguous"
    assert "many" in many["detected_issues"][0]["phrase"].lower()
    assert many["ambiguity_score"] == 9

    friendly = client.post(
        "/api/analyze",
        json={"requirement": "The system shall provide a user-friendly interface."},
    ).json()
    assert friendly["classification"] == "clean"
    assert friendly["overall_status"] == "ambiguous"
    assert friendly["ambiguity_type"] == "pragmatic"
    assert "step" in friendly["suggested_requirement"].lower()


def test_measurable_time_stays_clean_when_bert_is_clean():
    text = "The system shall respond within 2 seconds."
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=8,
            confidence=0.94,
        )
    )
    body = client.post("/api/analyze", json={"requirement": text}).json()
    assert body["classification"] == "clean"
    assert body["overall_status"] == "clean"
    assert body["detected_issues"] == []
    assert body["ambiguity_score"] == 8


def test_valid_requirement_ambiguous_response_structure():
    rewrite = "The system shall respond within [specify maximum response time]."
    app = create_app(
        model=FakeModel(
            ModelPrediction(
                classification="ambiguous",
                ambiguity_type="pragmatic",
                ambiguity_score=78,
                confidence=0.81,
            )
        ),
        rewrite_service=FakeRewriteService(rewrite),
        load_model=False,
    )
    client = TestClient(app)
    response = client.post("/api/analyze", json={"requirement": AMBIGUOUS_TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["requirement"] == AMBIGUOUS_TEXT
    assert body["classification"] == "ambiguous"
    assert body["overall_status"] == "ambiguous"
    assert body["ambiguity_type"] == "pragmatic"
    assert body["type_source"] == "hybrid"
    assert body["final_assessment"]["ambiguity_type"] == "pragmatic"
    assert body["final_assessment"]["score"] != round(body["confidence"] * 10, 1)
    assert body["ml_prediction"]["stage_b_type"] == "pragmatic"
    assert body["ml_prediction"]["classification"] == "ambiguous"
    assert body["ml_prediction"]["confidence"] == 0.81
    assert body["flagged_phrase"].lower() == "quickly"
    assert body["ambiguity_score"] == 78
    assert body["confidence"] == 0.81
    assert "quickly" in body["explanation"].lower() or "context" in body["explanation"].lower()
    assert body["detected_issues"][0]["phrase"].lower() == "quickly"
    assert "[maximum response time]" in body["suggested_requirement"]


def test_stage_b_without_linguistic_hits_keeps_rewrite_service():
    rewrite = "Stage B rewrite from the service."
    app = create_app(
        model=FakeModel(
            ModelPrediction(
                classification="ambiguous",
                ambiguity_type="syntactic",
                ambiguity_score=72,
                confidence=0.77,
            )
        ),
        rewrite_service=FakeRewriteService(rewrite),
        load_model=False,
    )
    client = TestClient(app)
    body = client.post("/api/analyze", json={"requirement": CLEAN_TEXT}).json()
    assert body["classification"] == "ambiguous"
    assert body["overall_status"] == "ambiguous"
    assert body["ambiguity_type"] == "syntactic"
    assert body["type_source"] == "stage_b"
    assert body["detected_issues"] == []
    assert body["suggested_requirement"] == rewrite
    assert body["ambiguity_score"] == 72


def test_quickly_keeps_stage_b_type_while_highlighting_linguistic_phrase():
    client = _client(
        ModelPrediction(
            classification="ambiguous",
            ambiguity_type="syntax",
            ambiguity_score=56,
            confidence=0.56,
        )
    )
    text = "The software should respond quickly"
    body = client.post("/api/analyze", json={"requirement": text}).json()
    assert body["classification"] == "ambiguous"
    assert body["confidence"] == 0.56
    assert body["ambiguity_score"] == 56
    assert body["ml_prediction"]["confidence"] == 0.56
    assert body["ml_prediction"]["stage_b_type"] == "syntax"
    assert body["overall_status"] == "ambiguous"
    assert body["ambiguity_type"] == "syntax"
    assert body["final_assessment"]["ambiguity_type"] == "syntax"
    assert body["final_assessment"]["status"] == "ambiguous"
    assert body["final_assessment"]["ambiguity_score"] == 6.6
    assert body["final_assessment"]["clarity_score"] == 3.4
    assert body["final_score"] == 3.4
    assert body["user_assessment"]["score"] == 3.4
    assert body["user_assessment"]["score_label"] == "Highly ambiguous"
    issue = body["detected_issues"][0]
    assert issue["phrase"].lower() == "quickly"
    assert issue["source"] == "linguistic"
    assert issue["severity"] == "high"
    assert issue["confidence"] >= 0.9
    assert text[issue["start"] : issue["end"]].lower() == "quickly"
    assert "[X]" in issue["suggestion"]
    assert "second" in issue["suggestion"].lower()


def test_multiple_linguistic_findings_have_separate_spans():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=12,
            confidence=0.88,
        )
    )
    text = (
        "The system should respond quickly and provide a user-friendly "
        "interface with sufficient information."
    )
    body = client.post("/api/analyze", json={"requirement": text}).json()
    phrases = [item["phrase"].lower().replace(" ", "-") for item in body["detected_issues"]]
    assert any("quickly" in phrase for phrase in phrases)
    assert any("user-friendly" in phrase for phrase in phrases)
    assert any("sufficient" in phrase for phrase in phrases)
    starts = [item["start"] for item in body["detected_issues"]]
    assert len(starts) == len(set(starts))
    assert all(item["source"] == "linguistic" for item in body["detected_issues"])


def test_bert_failure_still_returns_linguistic_result():
    class FailingModel:
        loaded = True

        def predict(self, requirement: str):
            raise RuntimeError("cuda exploded")

    app = create_app(
        model=FailingModel(),  # type: ignore[arg-type]
        rewrite_service=FakeRewriteService(),
        load_model=False,
    )
    client = TestClient(app)
    body = client.post(
        "/api/analyze",
        json={"requirement": "The software should respond quickly"},
    ).json()
    assert body["overall_status"] == "ambiguous"
    assert body["ambiguity_type"] == "pragmatic"
    assert body["ml_prediction"] is None
    assert body["detected_issues"][0]["phrase"].lower() == "quickly"


def test_llm_unavailable_uses_fallback():
    from backend.services.rewrite import RewriteService, fallback_rewrite

    service = RewriteService()
    result = service.rewrite(AMBIGUOUS_TEXT, "pragmatic")
    assert result == fallback_rewrite(AMBIGUOUS_TEXT, "pragmatic")
    assert "shall" in result.lower()
