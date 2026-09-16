from backend.services.ambiguity_model import ModelPrediction
from backend.services.generate import fallback_generate
from backend.services.requirement_text import (
    apply_measurable_placeholders,
    build_requirement,
    extract_action,
    infer_requirement_kind,
    is_broken_requirement,
    sanitize_requirement,
)
from backend.tests.test_user_facing_analysis import _client


def _assert_single_shall(text: str) -> None:
    lowered = text.lower()
    assert lowered.startswith("the system shall ")
    assert lowered.count("the system shall") == 1
    assert "shall shall" not in lowered
    assert "shall must" not in lowered
    assert "shall should" not in lowered
    assert "shall will" not in lowered
    assert "shall be able to" not in lowered
    assert "use shall" not in lowered
    assert not is_broken_requirement(text)


def test_navigate_idea_is_not_prefixed_with_i_want():
    text = build_requirement("I want the system allow users to navigate")
    assert text.lower().startswith("the system shall")
    assert "i want" not in text.lower()
    assert "shall i" not in text.lower()
    assert "allow users to navigate" in text.lower()


def test_fallback_navigate_quickly_is_usability_not_performance():
    draft = fallback_generate("I want users to navigate through the dashboard quickly.")
    assert "i want" not in draft.suggested_requirement.lower()
    assert draft.suggested_requirement.lower().startswith("the system shall")
    assert "quickly" not in draft.suggested_requirement.lower()
    assert "[" in draft.suggested_requirement
    assert infer_requirement_kind(draft.suggested_requirement) == "usability"
    assert infer_requirement_kind("The system shall respond quickly.") == "performance"


def test_subjective_word_becomes_placeholder_without_inventing_a_number():
    text = apply_measurable_placeholders(
        "The system shall allow users to navigate through the dashboard quickly.",
        "usability",
    )
    assert "quickly" not in text.lower()
    assert "[" in text
    assert not any(char.isdigit() for char in text)


def test_sanitize_rejects_shall_i_want():
    cleaned = sanitize_requirement(
        "The system shall I want the system allow users to navigate.",
        "I want the system allow users to navigate",
    )
    assert "i want" not in cleaned.lower()
    assert is_broken_requirement(
        "The system shall I want the system allow users to navigate."
    )


def test_generate_api_navigate_is_grammatical():
    body = _client().post(
        "/api/generate-requirement",
        json={"idea": "I want the system allow users to navigate"},
    ).json()
    text = body["suggested_requirement"]
    assert text.startswith("The system shall")
    assert "I want" not in text
    assert "shall I" not in text
    assert "that allows users to complete [specific task]" not in text
    assert body["quality_checks"]
    assert any(item["id"] == "actor" and item["passed"] for item in body["quality_checks"])
    assert not any(item["id"] == "copied" and not item["passed"] for item in body["quality_checks"])


def test_respond_quickly_highlights_phrase_and_keeps_stage_b_when_present():
    body = _client(
        ModelPrediction(
            classification="ambiguous",
            ambiguity_type="lexical",
            ambiguity_score=60,
            confidence=0.70,
        )
    ).post(
        "/api/analyze",
        json={"requirement": "The system shall respond quickly."},
    ).json()
    user = body["user_assessment"]
    assert user["phrases"][0]["text"].lower() == "quickly"
    assert user["ambiguity_type"] == "lexical"
    assert user["type_label"] == "Lexical / wording"
    assert user["requirement_type"] == "performance"
    assert user["clarity_score"] == user["score"]
    assert user["score"] == round(10.0 - user["ambiguity_score"], 1)
    assert user["score_label"]


def test_screenshot_input_does_not_duplicate_shall():
    idea = (
        "Use shall be able to create a password and fill other credentials "
        "while logging into the system"
    )
    built = build_requirement(idea)
    _assert_single_shall(built)
    assert "allow the user to create a password" in built.lower()
    assert "credentials" in built.lower()
    assert built != idea

    body = _client().post("/api/generate-requirement", json={"idea": idea}).json()
    suggested = body["suggested_requirement"]
    _assert_single_shall(suggested)
    assert body["idea"] == idea
    assert body["idea"] != suggested
    assert body["analysis"]["requirement"] == suggested
    analysis = body["analysis"]
    assert analysis["clarity_score"] == analysis["final_score"]
    assert analysis["user_assessment"]["score"] == analysis["clarity_score"]
    assert analysis["user_assessment"]["clarity_score"] == analysis["clarity_score"]
    assert analysis["user_assessment"]["score"] == round(
        10.0 - analysis["fused_ambiguity_score"], 1
    )


def test_existing_shall_requirement_is_not_double_prefixed():
    idea = "The system shall allow users to reset their password."
    built = build_requirement(idea)
    _assert_single_shall(built)
    assert built.lower().count("the system shall") == 1
    assert "the system shall the system shall" not in built.lower()
    assert extract_action(idea) == "allow users to reset their password"


def test_users_must_be_able_to_becomes_single_shall():
    idea = "Users must be able to reset their password."
    built = build_requirement(idea)
    _assert_single_shall(built)
    assert "must" not in built.lower()
    assert "reset their password" in built.lower()


def test_login_should_let_users_becomes_single_shall():
    idea = "Login should let users enter their credentials."
    built = build_requirement(idea)
    _assert_single_shall(built)
    assert "should" not in built.lower()
    assert "enter their credentials" in built.lower()
    assert "login" in built.lower()


def test_clear_password_reset_has_high_clarity():
    body = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=8,
            confidence=0.94,
        )
    ).post(
        "/api/analyze",
        json={
            "requirement": (
                "The system shall allow registered users to reset their password "
                "using a verified email address."
            )
        },
    ).json()
    user = body["user_assessment"]
    assert user["status"] == "clear"
    assert user["phrases"] == []
    assert user["score"] >= 8.0
    assert user["clarity_score"] == user["score"]
    assert user["score_label"] == "Very clear"
    assert body["linguistic_findings"] == []


def test_many_and_quickly_keep_stage_b_type():
    body = _client(
        ModelPrediction(
            classification="ambiguous",
            ambiguity_type="semantic",
            ambiguity_score=55,
            confidence=0.60,
        )
    ).post(
        "/api/analyze",
        json={"requirement": "The system shall process many requests quickly."},
    ).json()
    phrases = [item["text"].lower() for item in body["user_assessment"]["phrases"]]
    assert any("many" in item for item in phrases)
    assert any("quickly" in item for item in phrases)
    assert body["user_assessment"]["ambiguity_type"] == "semantic"
    assert body["final_assessment"]["type"] == "semantic"
    assert body["final_assessment"]["clarity_score"] == body["final_score"]
    assert body["ml_prediction"]["stage_b_type"] == "semantic"
