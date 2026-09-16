import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.services.ambiguity_model import ModelPrediction
from backend.services.llm_analyzer import LlmAnalyzer, LlmPhrase, LlmReasoningResult
from backend.tests.fakes import FakeLlmAnalyzer, FakeModel, FakeRewriteService, llm_quickly_result

QUICKLY = "The software should respond quickly."
MEASURABLE = "The software shall respond within 2 seconds."
CONTEXTUAL = "Authorized users may access the records if they are valid."


def _prediction(
    classification="ambiguous",
    ambiguity_type="syntax",
    score=56,
    confidence=0.56,
) -> ModelPrediction:
    return ModelPrediction(
        classification=classification,
        ambiguity_type=ambiguity_type,
        ambiguity_score=score,
        confidence=confidence,
        stage_a_confidence=confidence,
        stage_b_confidence=0.61 if ambiguity_type else None,
    )


def _client(prediction: ModelPrediction, llm=None, settings=None) -> TestClient:
    app = create_app(
        settings=settings or Settings(llm_enabled=False, llm_api_key=""),
        model=FakeModel(prediction),
        rewrite_service=FakeRewriteService(),
        llm_analyzer=llm,
        load_model=False,
    )
    return TestClient(app)


def _assert_no_secret(body: dict) -> None:
    dumped = json.dumps(body)
    assert "sk-" not in dumped
    assert "LLM_API_KEY" not in dumped
    assert "api_key" not in dumped.lower()


def test_vague_requirement_includes_llm_and_preserves_other_evidence():
    client = _client(
        _prediction(),
        llm=FakeLlmAnalyzer(llm_quickly_result(QUICKLY)),
        settings=Settings(llm_enabled=True, llm_api_key="sk-test-not-a-real-key"),
    )
    body = client.post("/api/analyze", json={"requirement": QUICKLY}).json()
    assert body["overall_status"] == "ambiguous"
    assert body["final_assessment"]["status"] == "ambiguous"
    assert body["final_assessment"]["type"] == "syntax"
    assert body["final_assessment"]["ambiguity_score"] == 7.1
    assert body["final_assessment"]["clarity_score"] == 2.9
    assert body["final_assessment"]["score"] == 2.9
    assert body["ml_prediction"]["stage_a"]["label"] == "ambiguous"
    assert body["ml_prediction"]["stage_a"]["confidence"] == 0.56
    assert body["ml_prediction"]["stage_a"]["source"] == "bert"
    assert body["ml_prediction"]["stage_b"]["label"] == "syntax"
    assert any(item["phrase"].lower() == "quickly" for item in body["linguistic_findings"])
    assert body["linguistic_findings"][0]["source"] == "linguistic"
    llm = body["llm_analysis"]
    assert llm["available"] is True
    assert llm["is_ambiguous"] is True
    assert llm["type"] == "pragmatic"
    assert llm["source"] == "llm"
    assert llm["confidence"] == 0.94
    assert any(item["text"].lower() == "quickly" for item in llm["ambiguous_phrases"])
    phrase = llm["ambiguous_phrases"][0]
    assert QUICKLY[phrase["start"] : phrase["end"]].lower() == "quickly"
    _assert_no_secret(body)


def test_measurable_requirement_has_no_quickly_false_positive():
    llm = LlmReasoningResult(
        available=True,
        is_ambiguous=False,
        ambiguity_score=1.2,
        confidence=0.95,
        explanation="The response-time limit is measurable.",
        phrases=[],
    )
    client = _client(
        _prediction("clean", None, 8, 0.94),
        llm=FakeLlmAnalyzer(llm),
        settings=Settings(llm_enabled=True, llm_api_key="sk-test-not-a-real-key"),
    )
    body = client.post("/api/analyze", json={"requirement": MEASURABLE}).json()
    assert body["final_assessment"]["status"] == "clean"
    assert body["linguistic_findings"] == []
    assert body["llm_analysis"]["available"] is True
    assert body["llm_analysis"]["is_ambiguous"] is False
    phrases = [item.get("phrase", "").lower() for item in body["detected_issues"]]
    texts = [item.get("text", "").lower() for item in body["llm_analysis"]["ambiguous_phrases"]]
    assert "quickly" not in phrases
    assert "quickly" not in texts
    _assert_no_secret(body)


def test_contextual_ambiguity_uses_llm_reasoning():
    start = CONTEXTUAL.find("they")
    llm = LlmReasoningResult(
        available=True,
        is_ambiguous=True,
        ambiguity_score=7.6,
        ambiguity_type="semantic",
        severity="high",
        confidence=0.91,
        explanation="The pronoun they can refer to authorized users or to the records.",
        phrases=[
            LlmPhrase(
                text="they",
                reason="The pronoun has two possible antecedents.",
                suggestion="Authorized users may access the records if the records are valid.",
                start=start,
                end=start + 4,
            )
        ],
    )
    client = _client(
        _prediction("clean", None, 18, 0.82),
        llm=FakeLlmAnalyzer(llm),
        settings=Settings(llm_enabled=True, llm_api_key="sk-test-not-a-real-key"),
    )
    body = client.post("/api/analyze", json={"requirement": CONTEXTUAL}).json()
    assert body["ml_prediction"]["stage_a"]["label"] == "clean"
    assert body["linguistic_findings"] == []
    assert body["llm_analysis"]["available"] is True
    assert body["llm_analysis"]["is_ambiguous"] is True
    assert body["llm_analysis"]["explanation"]
    assert body["final_assessment"]["status"] == "ambiguous"
    assert body["final_assessment"]["type"] == "semantic"
    issue = body["issues"][0]
    assert issue["phrase"] == "they"
    assert issue["source"] == "llm"
    assert CONTEXTUAL[issue["start"] : issue["end"]] == "they"
    _assert_no_secret(body)


def test_llm_disabled_uses_bert_and_linguistic_only():
    client = _client(_prediction(), llm=None, settings=Settings(llm_enabled=False))
    body = client.post("/api/analyze", json={"requirement": QUICKLY}).json()
    assert body["llm_analysis"]["available"] is False
    assert body["llm_analysis"]["reason"] in {
        "Optional review skipped",
        "Optional review unavailable",
    }
    assert body["ml_prediction"]["stage_a"]["source"] == "bert"
    assert body["linguistic_findings"][0]["phrase"].lower() == "quickly"
    assert body["final_assessment"]["status"] == "ambiguous"
    assert body["final_assessment"]["type"] == "syntax"
    assert body["final_assessment"]["ambiguity_score"] == 6.6
    assert body["final_assessment"]["clarity_score"] == 3.4
    assert body["final_assessment"]["score"] == 3.4
    _assert_no_secret(body)


def test_invalid_llm_response_does_not_crash_api():
    settings = Settings(
        llm_enabled=True,
        llm_api_key="sk-test-not-a-real-key",
        llm_model="gpt-4o-mini",
    )
    analyzer = LlmAnalyzer(settings)
    client_ctx = MagicMock()
    http_client = MagicMock()
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"choices": [{"message": {"content": "not-json {{"}}]}
    http_client.post.return_value = response
    client_ctx.__enter__.return_value = http_client
    client_ctx.__exit__.return_value = False

    app = create_app(
        settings=settings,
        model=FakeModel(_prediction()),
        rewrite_service=FakeRewriteService(),
        llm_analyzer=analyzer,
        load_model=False,
    )
    client = TestClient(app)
    with patch("backend.services.llm_client.httpx.Client", return_value=client_ctx):
        response = client.post("/api/analyze", json={"requirement": QUICKLY})
    assert response.status_code == 200
    body = response.json()
    assert body["llm_analysis"]["available"] is False
    assert body["llm_analysis"]["reason"] == "Optional review unavailable"
    assert body["final_assessment"]["status"] == "ambiguous"
    assert body["linguistic_findings"][0]["phrase"].lower() == "quickly"
    _assert_no_secret(body)
