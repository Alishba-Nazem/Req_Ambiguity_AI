from backend.services.linguistic_detector import detect_linguistic_issues


def _phrases(text: str) -> list[str]:
    return [item.phrase.lower() for item in detect_linguistic_issues(text)]


def test_quickly_is_pragmatic_unmeasurable_time():
    text = "The system shall respond quickly."
    issues = detect_linguistic_issues(text)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.phrase.lower() == "quickly"
    assert text[issue.start : issue.end].lower() == "quickly"
    assert issue.ambiguity_type == "pragmatic"
    assert issue.category == "unmeasurable_time"
    assert issue.severity == "high"
    assert "quickly" in issue.reason.lower()
    assert "measurable" in issue.reason.lower() or "threshold" in issue.reason.lower()
    assert issue.confidence >= 0.9
    assert "[maximum response time]" in issue.suggestion


def test_measurable_response_time_is_not_flagged():
    text = "The system shall respond within 2 seconds."
    issues = detect_linguistic_issues(text)
    assert issues == []
    assert "quickly" not in _phrases(text)


def test_quickly_cleared_by_following_time_constraint():
    text = "The system shall respond quickly, within 2 seconds."
    assert detect_linguistic_issues(text) == []


def test_many_requests_is_quantity_ambiguity():
    text = "The system shall process many requests."
    issues = detect_linguistic_issues(text)
    assert len(issues) == 1
    assert issues[0].phrase.lower() == "many requests"
    assert issues[0].category == "unclear_quantity"
    assert issues[0].ambiguity_type == "pragmatic"
    assert "at least [maximum quantity]" in issues[0].suggestion


def test_measurable_quantity_is_not_flagged():
    text = "The system shall process at least 100 requests per minute."
    assert detect_linguistic_issues(text) == []


def test_user_friendly_is_subjective_pragmatic():
    text = "The system shall provide a user-friendly interface."
    issues = detect_linguistic_issues(text)
    assert len(issues) == 1
    assert "user-friendly" in issues[0].phrase.lower().replace(" ", "-")
    assert issues[0].category == "subjective_quality"
    assert issues[0].ambiguity_type == "pragmatic"
    assert "[maximum number of steps]" in issues[0].suggestion
    assert "step" in issues[0].suggestion.lower()


def test_measurable_interface_has_no_user_friendly_false_positive():
    text = (
        "The system shall provide an interface that allows users "
        "to complete checkout in 3 steps."
    )
    issues = detect_linguistic_issues(text)
    assert all("user-friendly" not in item.phrase.lower() for item in issues)
    assert all(item.category != "subjective_quality" for item in issues)


def test_high_level_collocation_is_not_flagged():
    text = "The system shall provide a high-level configuration API."
    issues = detect_linguistic_issues(text)
    assert all(item.phrase.lower() != "high" for item in issues)


def test_many_users_and_user_friendly_application():
    quantity = detect_linguistic_issues("The system shall support many users.")
    assert quantity[0].phrase.lower() == "many users"
    assert quantity[0].ambiguity_type == "pragmatic"
    assert "at least [maximum number of concurrent users]" in quantity[0].suggestion

    quality = detect_linguistic_issues("The application shall be user-friendly.")
    assert quality
    assert quality[0].ambiguity_type == "pragmatic"
    assert quality[0].reason
    assert quality[0].suggestion


def test_as_soon_as_possible_preferred_over_soon():
    text = "The system shall notify the operator as soon as possible."
    issues = detect_linguistic_issues(text)
    assert len(issues) == 1
    assert issues[0].phrase.lower() == "as soon as possible"
