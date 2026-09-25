"""Normalize informal ideas into standalone software requirements."""

from __future__ import annotations

import re

from backend.schemas import RequirementKind

_PERFORMANCE = re.compile(
    r"\b(?:respond(?:s|ing)?|response\s+time|latency|throughput|"
    r"load\s+time|page\s+load|requests?\s+per|within\s+\d+)\b",
    re.IGNORECASE,
)
_USABILITY = re.compile(
    r"\b(?:navigate|navigation|dashboard|interface|usable|usability|"
    r"menu|click|workflow)\b",
    re.IGNORECASE,
)
_SECURITY = re.compile(r"\b(?:secur(?:e|ity)|encrypt|auth|password|tls|oauth|mfa)\b", re.IGNORECASE)
_AVAILABILITY = re.compile(r"\b(?:availab|uptime|reliability)\b", re.IGNORECASE)
_COMPAT = re.compile(r"\b(?:compatib|browser|platform|device)\b", re.IGNORECASE)
_SUBJECTIVE = re.compile(
    r"\b(?:quickly|fast|easily|easy|simple|user-friendly|appropriate|"
    r"reasonable|sufficient|soon)\b",
    re.IGNORECASE,
)
_LEAD_IN = re.compile(
    r"^(?:please\s+)?"
    r"(?:i\s+want(?:\s+you\s+to)?|i\s+need|i'd\s+like|id\s+like|"
    r"we\s+want|we\s+need|help\s+me(?:\s+to)?)\s+",
    re.IGNORECASE,
)
_SYSTEM_SHALL = re.compile(
    r"^(?:the\s+)?(?:system|application|software|website|app)\s+"
    r"(?:shall|must|should|will)\s+",
    re.IGNORECASE,
)
_SYSTEM_LEAD = re.compile(
    r"^(?:the\s+)?(?:system|application|software|website|app)\s+"
    r"(?:to\s+|should\s+|shall\s+|must\s+|will\s+|can\s+)?",
    re.IGNORECASE,
)
# "Users/User/Use shall|must|should|will be able to …"
_ABLE_TO = re.compile(
    r"^(?:(?:the\s+)?(?:users?|use)\s+)?"
    r"(?:shall|must|should|will|can)\s+be\s+able\s+to\s+",
    re.IGNORECASE,
)
_USER_LEAD = re.compile(
    r"^(?:(?:the\s+)?(?:users?|use))\s+"
    r"(?:should\s+|shall\s+|must\s+|will\s+|can\s+|to\s+)?"
    r"(?:be\s+able\s+to\s+)?",
    re.IGNORECASE,
)
# "Login should let users enter…" / "The app must allow users to…"
_LET_USERS = re.compile(
    r"^(?P<context>.+?)\s+(?:should|shall|must|will|can)\s+"
    r"(?:let|allow|enable)\s+(?:the\s+)?users?\s+(?:to\s+)?",
    re.IGNORECASE,
)
_BROKEN = re.compile(
    r"\bshall\s+(?:shall|must|should|will|can)\b|"
    r"\bshall\s+be\s+able\s+to\b|"
    r"\buse\s+shall\b|"
    r"\bshall\s+i\b|"
    r"\bi\s+want\b|"
    r"\bi\s+need\b|"
    r"the system shall the system",
    re.IGNORECASE,
)
_KIND_LABELS = {
    "functional": "Functional",
    "performance": "Performance",
    "security": "Security",
    "usability": "Usability",
    "availability": "Availability",
    "compatibility": "Compatibility",
    "other": "Other",
}
_SCORE_BANDS = (
    (2.0, "Very clear"),
    (4.0, "Mostly clear"),
    (6.0, "Needs improvement"),
    (8.0, "Ambiguous"),
    (10.1, "Highly ambiguous"),
)

# Clarity bands (higher = better). Used for user-facing score labels.
_CLARITY_BANDS = (
    (4.0, "Highly ambiguous"),
    (6.0, "Needs improvement"),
    (8.0, "Mostly clear"),
    (10.1, "Very clear"),
)


def infer_requirement_kind(text: str) -> RequirementKind:
    """Infer requirement category from context, not from a vague adverb alone."""
    if re.search(r"\breset(?:ting)?\s+(?:their\s+|the\s+|a\s+)?password", text, re.I):
        return "functional"
    if _USABILITY.search(text):
        return "usability"
    if _PERFORMANCE.search(text):
        return "performance"
    if _AVAILABILITY.search(text):
        return "availability"
    if _COMPAT.search(text):
        return "compatibility"
    if _SECURITY.search(text):
        return "security"
    return "functional"


def requirement_kind_label(kind: RequirementKind | None) -> str | None:
    if not kind:
        return None
    return _KIND_LABELS.get(kind, kind)


def score_band(score: float) -> str:
    """Legacy ambiguity-oriented bands (higher score = more ambiguous)."""
    for limit, label in _SCORE_BANDS:
        if score < limit:
            return label
    return "Highly ambiguous"


def clarity_band(clarity_score: float) -> str:
    """User-facing clarity bands (higher score = clearer / higher quality)."""
    for limit, label in _CLARITY_BANDS:
        if clarity_score < limit:
            return label
    return "Very clear"


def _finish_action(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip()).strip(" .")
    if not cleaned:
        return "perform [specify the intended action]"
    return cleaned[0].lower() + cleaned[1:]


def extract_action(idea: str) -> str:
    """Return the intended system behavior without wrappers or modal verbs.

    Never returns a string that still starts with shall/must/should/will so
    ``build_requirement`` can safely prepend a single "The system shall".
    """
    text = re.sub(r"\s+", " ", (idea or "").strip()).rstrip(".!?")
    text = _LEAD_IN.sub("", text).strip()
    text = re.sub(
        r"\bfill other credentials to log in their system\b",
        "enter the required credentials to log in",
        text,
        flags=re.IGNORECASE,
    )

    # Already a shall-statement: keep only the predicate.
    system_shall = _SYSTEM_SHALL.match(text)
    if system_shall:
        return _finish_action(text[system_shall.end() :])

    # "Login should let users enter credentials" → allow users to enter…
    let_users = _LET_USERS.match(text)
    if let_users:
        remainder = text[let_users.end() :].strip()
        context = (let_users.group("context") or "").strip()
        action = remainder
        if context and context.lower() not in remainder.lower():
            if len(context.split()) <= 4 and not re.search(
                r"\b(?:system|application|software|users?)\b", context, re.I
            ):
                if not re.search(re.escape(context), remainder, re.I):
                    action = f"{remainder} during {context.lower()}"
        if not re.match(r"^(allow|enable)\b", action, re.I):
            action = f"allow users to {action}"
        return _finish_action(action)

    # "Use/User(s) shall be able to create…" → allow the user to create…
    able = _ABLE_TO.match(text)
    if able:
        remainder = text[able.end() :].strip()
        if re.match(r"^(?:the\s+)?(?:users?|use)\b", text, re.I):
            return _finish_action(f"allow the user to {remainder}")
        return _finish_action(f"allow users to {remainder}")

    text = _SYSTEM_LEAD.sub("", text).strip()
    text = re.sub(r"^to\s+", "", text, flags=re.IGNORECASE).strip()

    user_match = _USER_LEAD.match(text)
    if user_match:
        remainder = text[user_match.end() :].strip()
        if remainder:
            if not re.match(r"^(allow|enable)\b", remainder, re.IGNORECASE):
                text = f"allow users to {remainder}"
            else:
                text = remainder
        else:
            text = remainder

    text = re.sub(r"^(?:allow|enable)\s+the\s+system\s+to\s+", "", text, flags=re.IGNORECASE)
    if re.match(r"^allow\s+users\s+(?!to\b)", text, re.IGNORECASE):
        text = re.sub(r"^allow\s+users\s+", "allow users to ", text, flags=re.IGNORECASE)

    # Strip a leftover leading modal before we prefix "The system shall".
    text = re.sub(
        r"^(?:shall|must|should|will|can)\s+(?:be\s+able\s+to\s+)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    if not text:
        return "perform [specify the intended action]"
    if re.match(
        r"^(navigate|reset|open|view|export|upload|download|search|filter|edit|create|delete|login)\b",
        text,
        re.IGNORECASE,
    ):
        text = f"allow users to {text}"
    return _finish_action(text)


def build_requirement(idea: str, extras: str | None = None) -> str:
    """Build exactly one 'The system shall …' sentence from an informal idea."""
    action = extract_action(idea)
    # Guard: never concatenate a second modal after shall.
    action = re.sub(
        r"^(?:shall|must|should|will|can)\s+(?:be\s+able\s+to\s+)?",
        "",
        action,
        flags=re.IGNORECASE,
    ).strip()
    action = re.sub(r"^(?:use|users?)\s+shall\s+", "", action, flags=re.IGNORECASE).strip()
    if not action:
        action = "perform [specify the intended action]"
    extra = (extras or "").strip()
    if extra:
        extra = extra.rstrip(".")
        if extra.lower() not in action.lower():
            action = f"{action} {extra}"
    sentence = f"The system shall {action}."
    sentence = re.sub(r"\s+", " ", sentence).strip()
    sentence = re.sub(r"\s+\.", ".", sentence)
    # Final safety net against duplicated modals.
    sentence = re.sub(
        r"\bshall\s+(?:shall|must|should|will|can)\b",
        "shall",
        sentence,
        flags=re.I,
    )
    sentence = re.sub(
        r"\bshall\s+be\s+able\s+to\b",
        "shall allow the user to",
        sentence,
        flags=re.I,
    )
    sentence = re.sub(
        r"\bshall\s+use\s+shall\b",
        "shall allow the user to",
        sentence,
        flags=re.I,
    )
    return sentence


def is_broken_requirement(text: str) -> bool:
    if not text or not text.strip():
        return True
    if _BROKEN.search(text):
        return True
    if text.lower().count("the system shall") > 1:
        return True
    if re.search(r"\ba\s+that\s+allows\b|\bshall\s+shall\b|\bshall\s+within\b", text, re.I):
        return True
    if re.search(r"that allows users to complete \[specific task\]", text, re.I):
        if "interface" not in text.lower() and "user-friendly" not in text.lower():
            return True
    return False


def apply_measurable_placeholders(text: str, kind: RequirementKind | None = None) -> str:
    """Replace leftover subjective wording with an explicit missing measure."""
    candidate = (text or "").strip()
    if not candidate or re.search(r"\[[^\]]+\]", candidate):
        return candidate
    match = _SUBJECTIVE.search(candidate)
    if not match:
        return candidate
    cleaned = _SUBJECTIVE.sub("", candidate)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned).strip().rstrip(".")
    inferred = kind or infer_requirement_kind(candidate)
    if inferred == "performance" or _PERFORMANCE.search(candidate):
        clause = "within [maximum response time]"
    elif inferred == "usability":
        clause = "within [maximum completion time]"
    else:
        clause = "meeting [measurable acceptance criterion]"
    if re.search(r"\bwithin\b", cleaned, re.IGNORECASE):
        return f"{cleaned}."
    return f"{cleaned} {clause}."


def sanitize_requirement(text: str, idea: str, extras: str | None = None) -> str:
    candidate = (text or "").strip()
    if is_broken_requirement(candidate):
        return build_requirement(idea, extras)
    if "i want" in idea.lower() and idea.lower()[:24] in candidate.lower():
        return build_requirement(idea, extras)
    if not re.match(r"^(the\s+)?(system|application|software)\s+shall\b", candidate, re.I):
        if candidate.lower().startswith("the system should"):
            candidate = re.sub(r"\bshould\b", "shall", candidate, count=1, flags=re.I)
            if is_broken_requirement(candidate):
                return build_requirement(idea, extras)
        else:
            return build_requirement(idea, extras)
    return candidate if candidate.endswith(".") else f"{candidate}."


class QualityItem:
    def __init__(self, item_id: str, label: str, passed: bool, detail: str | None = None) -> None:
        self.id = item_id
        self.label = label
        self.passed = passed
        self.detail = detail


def quality_checks(requirement: str, idea: str = "") -> list[dict[str, object]]:
    text = requirement or ""
    lowered = text.lower()
    has_actor = bool(re.search(r"\b(system|application|software|user)\b", lowered))
    has_shall = bool(re.search(r"\bshall\b", lowered))
    has_behavior = len(re.findall(r"\b[a-z]{3,}\b", lowered)) >= 5
    copied = bool(idea) and "i want" in idea.lower() and "i want" in lowered
    broken = is_broken_requirement(text)
    subjective = bool(_SUBJECTIVE.search(text))
    placeholder = bool(re.search(r"\[[^\]]+\]", text))
    testable = has_actor and has_shall and has_behavior and not broken and not copied
    if subjective and not placeholder:
        testable = False
    items = [
        QualityItem("actor", "Clear actor or system subject", has_actor and not broken),
        QualityItem("shall", "Uses a shall statement", has_shall and not broken),
        QualityItem("behavior", "Describes one system behavior", has_behavior and not copied),
        QualityItem("copied", "Does not copy the original prompt", not copied and not broken),
        QualityItem(
            "testable",
            "Testable as written" if testable else "Not fully testable yet",
            testable,
            "A measurable limit is still missing." if subjective or placeholder else None,
        ),
    ]
    if subjective or placeholder:
        items.append(
            QualityItem(
                "measure",
                "Measurable constraint specified",
                False,
                "Replace bracketed placeholders with a concrete limit.",
            )
        )
    return [
        {
            "id": item.id,
            "label": item.label,
            "passed": item.passed,
            "detail": item.detail,
        }
        for item in items
        if (not item.passed) or item.id in {"actor", "behavior", "testable"}
    ]
