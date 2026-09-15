import pytest

from backend.services.ambiguity_model import ModelPrediction
from backend.services.space_runtime import (
    analyze_payload,
    configure_runtime,
    generate_payload,
    health_payload,
    reset_runtime,
)
from backend.tests.fakes import FakeModel


@pytest.fixture(autouse=True)
def _clear_space_runtime():
    reset_runtime()
    yield
    reset_runtime()


def _clean_model() -> FakeModel:
    return FakeModel(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=12,
            confidence=0.88,
        )
    )


def test_health_without_model():
    body = health_payload()
    assert body["status"] == "ok"
    assert body["model_loaded"] is False
    assert body["error"]


def test_health_with_injected_model():
    configure_runtime(_clean_model())
    body = health_payload()
    assert body["model_loaded"] is True
    assert body["stage_a_loaded"] is True
    assert body["stage_b_loaded"] is True
    assert body["error"] is None


def test_analyze_payload_matches_fastapi_shape():
    configure_runtime(_clean_model())
    result = analyze_payload("The system shall respond quickly.")
    assert "error" not in result
    assert result["requirement"] == "The system shall respond quickly."
    assert result["classification"] in {"clean", "ambiguous"}
    assert "final_assessment" in result
    assert "user_assessment" in result
    assert "ml_prediction" in result
    assert result["user_assessment"]["phrases"][0]["text"].lower() == "quickly"


def test_analyze_rejects_blank_requirement():
    configure_runtime(_clean_model())
    result = analyze_payload("   ")
    assert result["code"] == "validation_error"
    assert "requirement" in result["error"].lower() or "empty" in result["error"].lower()


def test_analyze_without_model_returns_unavailable():
    result = analyze_payload("The system shall lock the account after 5 failed login attempts.")
    assert result["code"] == "model_unavailable"
    assert result["error"]


def test_generate_payload_matches_fastapi_shape():
    configure_runtime(_clean_model())
    result = generate_payload(
        "I want the system allow users to navigate",
        "auto",
        "",
    )
    assert "error" not in result
    assert result["suggested_requirement"].startswith("The system shall")
    assert "I want" not in result["suggested_requirement"]
    assert result["analysis"]
    assert result["analysis"]["requirement"] == result["suggested_requirement"]
    assert result["quality_checks"]


def test_generate_rejects_blank_idea():
    configure_runtime(_clean_model())
    result = generate_payload("  ", "functional", None)
    assert result["code"] == "validation_error"
