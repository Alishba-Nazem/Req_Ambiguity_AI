from backend.services.generate import fallback_generate
from backend.services.requirement_text import (
    apply_measurable_placeholders,
    build_requirement,
    infer_requirement_kind,
    is_broken_requirement,
    sanitize_requirement,
)
from backend.tests.test_user_facing_analysis import _client


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


def test_respond_quickly_is_pragmatic_not_just_performance_label():
    body = _client().post(
        "/api/analyze",
        json={"requirement": "The system shall respond quickly."},
    ).json()
    user = body["user_assessment"]
    assert user["phrases"][0]["text"].lower() == "quickly"
    assert user["ambiguity_type"] == "pragmatic"
    assert user["requirement_type"] == "performance"
    assert user["score"] is not None
    assert user["score_label"]
