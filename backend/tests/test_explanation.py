from backend.services.explanation import explain
from backend.services.linguistic_detector import detect_linguistic_issues
from backend.services.rewrite import fallback_rewrite


def test_linguistic_explanation_mentions_quickly():
    text = "The system shall respond quickly."
    issues = detect_linguistic_issues(text)
    message = explain(
        text,
        "clean",
        "pragmatic",
        "linguistic",
        overall_status="ambiguous",
        issues=issues,
    )
    assert "quickly" in message.lower()
    assert "pragmatic" in message.lower()
    assert "bert" not in message.lower()
    assert "llm" not in message.lower()


def test_clean_measurable_explanation():
    text = "The system shall lock the account after 5 failed login attempts."
    message = explain(text, "clean", None, None, overall_status="clean", issues=[])
    assert "specific and measurable" in message.lower()
    assert "stage a" not in message.lower()


def test_fallback_rewrite_quickly_is_only_the_requirement():
    result = fallback_rewrite("The system shall respond quickly.", "pragmatic")
    assert result == "The system shall respond within [maximum response time]."
    assert "shall shall" not in result.lower()
