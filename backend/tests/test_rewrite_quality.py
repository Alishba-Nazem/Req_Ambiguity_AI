from backend.services.linguistic_detector import detect_linguistic_issues
from backend.services.rewrite import compose_improved_requirement, is_valid_suggestion


def test_user_friendly_is_a_complete_sentence_not_a_spliced_template():
    text = "The system shall provide a user-friendly interface."
    rewritten = compose_improved_requirement(text, detect_linguistic_issues(text))
    assert rewritten.lower().startswith("the system shall")
    assert "a that allows" not in rewritten.lower()
    assert "shall shall" not in rewritten.lower()
    assert "[specific task]" in rewritten
    assert "[maximum number of steps]" in rewritten
    assert rewritten.count(".") == 1
    assert is_valid_suggestion(rewritten, text)


def test_quickly_becomes_one_named_placeholder_clause():
    text = "The system shall respond quickly."
    rewritten = compose_improved_requirement(text, detect_linguistic_issues(text))
    assert rewritten == "The system shall respond within [maximum response time]."
    assert "quickly" not in rewritten.lower()
    assert is_valid_suggestion(rewritten, text)


def test_multiple_phrases_produce_one_coherent_requirement():
    text = "The system should quickly provide appropriate results to many users."
    issues = detect_linguistic_issues(text)
    rewritten = compose_improved_requirement(text, issues)
    assert rewritten.lower().count("the system shall") == 1
    assert rewritten.count(".") == 1
    assert "within [x] seconds" not in rewritten.lower()
    assert "a that allows" not in rewritten.lower()
    assert not rewritten.lower().startswith("the system shall within")
    assert "[maximum" in rewritten
    assert is_valid_suggestion(rewritten, text)


def test_rewrite_does_not_invent_numbers():
    text = "The system shall respond quickly."
    rewritten = compose_improved_requirement(text, detect_linguistic_issues(text))
    assert not any(char.isdigit() for char in rewritten)


def test_invalid_spliced_templates_are_rejected():
    assert not is_valid_suggestion(
        "The system shall provide a that allows users to complete [specific task] interface."
    )
    assert not is_valid_suggestion("The system shall shall respond within [maximum response time].")
    assert not is_valid_suggestion("The system shall I want users to navigate.")
