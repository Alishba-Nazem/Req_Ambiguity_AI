from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.services.ambiguity_model import ModelPrediction
from backend.services.linguistic_detector import detect_linguistic_issues
from backend.services.revision import SuggestionDecision, apply_decisions
from backend.services.rewrite import compose_improved_requirement
from backend.tests.fakes import FakeLlmAnalyzer, FakeModel, FakeRewriteService


def _client(prediction: ModelPrediction | None = None, llm=None) -> TestClient:
    app = create_app(
        settings=Settings(llm_enabled=False, llm_api_key=""),
        model=FakeModel(
            prediction
            or ModelPrediction(
                classification="clean",
                ambiguity_type=None,
                ambiguity_score=12,
                confidence=0.88,
            )
        ),
        rewrite_service=FakeRewriteService(),
        llm_analyzer=llm,
        load_model=False,
    )
    return TestClient(app)


def test_available_extracts_exact_phrase_and_span():
    text = "The system should be available."
    issues = detect_linguistic_issues(text)
    assert len(issues) == 1
    assert issues[0].phrase.lower() == "available"
    assert text[issues[0].start : issues[0].end].lower() == "available"
    assert issues[0].start > 0
    assert issues[0].end < len(text)
    assert issues[0].ambiguity_type == "pragmatic"
    assert "[X]" in issues[0].suggestion


def test_available_api_returns_user_assessment():
    body = _client().post(
        "/api/analyze",
        json={"requirement": "The system should be available."},
    ).json()
    assert body["user_assessment"]["status"] == "needs_improvement"
    phrases = body["user_assessment"]["phrases"]
    assert phrases[0]["text"].lower() == "available"
    assert body["requirement"][phrases[0]["start"] : phrases[0]["end"]].lower() == "available"
    assert "measurable" in phrases[0]["why"].lower() or "availability" in phrases[0]["why"].lower()
    assert body["suggested_requirement"]
    assert "[" in body["suggested_requirement"]
    assert "availability" in body["suggested_requirement"].lower()
    assert body["missing_information"]


def test_quickly_user_assessment_hides_nothing_needed_for_ui():
    body = _client(
        ModelPrediction(
            classification="ambiguous",
            ambiguity_type="syntax",
            ambiguity_score=56,
            confidence=0.56,
        )
    ).post(
        "/api/analyze",
        json={"requirement": "The system should respond quickly."},
    ).json()
    user = body["user_assessment"]
    assert user["status"] == "needs_improvement"
    assert user["phrases"][0]["text"].lower() == "quickly"
    assert user["ambiguity_type"] == "pragmatic"
    assert "response time" in user["suggested_requirement"].lower()
    assert "[maximum response time]" in user["suggested_requirement"]
    assert user["suggested_requirement"].lower().startswith("the system shall")
    assert "shall shall" not in user["suggested_requirement"].lower()


def test_measurable_requirement_stays_clear():
    body = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=8,
            confidence=0.94,
        )
    ).post(
        "/api/analyze",
        json={"requirement": "The system shall respond within 2 seconds."},
    ).json()
    assert body["user_assessment"]["status"] == "clear"
    assert body["user_assessment"]["phrases"] == []
    assert body["linguistic_findings"] == []


def test_exact_quantity_is_not_flagged():
    body = _client().post(
        "/api/analyze",
        json={"requirement": "The system shall support exactly 500 concurrent users."},
    ).json()
    assert body["user_assessment"]["status"] == "clear"
    phrases = [item["text"].lower() for item in body["user_assessment"]["phrases"]]
    assert "many" not in " ".join(phrases)


def test_many_users_phrase_and_placeholder():
    body = _client().post(
        "/api/analyze",
        json={"requirement": "The system should support many users."},
    ).json()
    phrase = body["user_assessment"]["phrases"][0]["text"].lower()
    assert phrase == "many users"
    assert "[maximum number of concurrent users]" in body["suggested_requirement"]
    assert body["suggested_requirement"].lower().count("the system shall") == 1


def test_multiple_ambiguities_have_separate_phrases_and_one_rewrite():
    text = "The system should quickly provide appropriate results to many users."
    issues = detect_linguistic_issues(text)
    phrases = [item.phrase.lower() for item in issues]
    assert any("quickly" in item for item in phrases)
    assert any("appropriate" in item for item in phrases)
    assert any("many" in item for item in phrases)
    combined = compose_improved_requirement(text, issues)
    assert combined.lower().count("the system shall") == 1
    assert "[" in combined
    assert "shall" in combined.lower()
    assert "a that allows" not in combined.lower()
    assert "shall shall" not in combined.lower()
    assert combined.count(".") == 1
    body = _client().post("/api/analyze", json={"requirement": text}).json()
    assert len(body["user_assessment"]["phrases"]) >= 2
    assert body["suggested_requirement"] == combined or body["suggested_requirement"]


def test_accept_edit_dismiss_decisions():
    original = "The system should respond quickly."
    combined = "The system shall respond within [X] seconds."
    decisions = [
        SuggestionDecision(status="accepted", suggestion=combined),
    ]
    assert apply_decisions(original, combined, decisions) == combined
    edited = apply_decisions(
        original,
        combined,
        [SuggestionDecision(status="edited", suggestion=combined, edited_text="The system shall respond within 2 seconds.")],
    )
    assert edited == "The system shall respond within 2 seconds."
    dismissed = apply_decisions(
        original,
        combined,
        [SuggestionDecision(status="dismissed", suggestion=combined)],
    )
    assert dismissed == original


def test_generated_password_reset_is_analyzed():
    client = _client()
    body = client.post(
        "/api/generate-requirement",
        json={"idea": "I want users to reset their password.", "requirement_type": "functional"},
    ).json()
    assert "password" in body["suggested_requirement"].lower()
    assert "email" in body["suggested_requirement"].lower()
    assert body["analysis"] is not None
    assert body["analysis"]["requirement"] == body["suggested_requirement"]
    assert "user_assessment" in body["analysis"]


def test_generated_secure_idea_asks_for_missing_information():
    body = _client().post(
        "/api/generate-requirement",
        json={"idea": "I want the system to be secure."},
    ).json()
    assert body["ready_to_use"] is False
    assert body["requirement_type"] == "security"
    joined = " ".join(body["missing_information"]).lower()
    assert "authentication" in joined or "authorization" in joined
    assert body["analysis"] is not None


def test_llm_unavailable_generate_still_works():
    body = _client().post(
        "/api/generate-requirement",
        json={"idea": "I want the website to be fast.", "requirement_type": "performance"},
    ).json()
    assert "[" in body["suggested_requirement"]
    assert body["missing_information"]
    assert body["analysis"]["llm_analysis"]["available"] is False
