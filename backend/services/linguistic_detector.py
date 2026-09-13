"""Requirements-quality linguistic detector.

The BERT model is trained on the provided labeled dataset and therefore
reflects the dataset's annotation patterns. This linguistic layer supplements
the model by detecting requirements-quality issues that may not be represented
reliably in the training labels. It does not catch all ambiguity, does not
replace Stage A or Stage B, and must not overwrite the ML prediction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.schemas import AmbiguityType, IssueSeverity

_TIME_CONSTRAINT = re.compile(
    r"(?:"
    r"(?:within|in|under|inside|less than|no more than|at most|no later than)"
    r"\s+\d+(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?|minutes?|hours?|days?)"
    r"|"
    r"\d+(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?|minutes?|hours?|days?)"
    r")",
    re.IGNORECASE,
)
_QUANTITY_CONSTRAINT = re.compile(
    r"(?:"
    r"(?:at least|at most|no more than|no fewer than|exactly|up to|"
    r"minimum of|maximum of|not less than)\s+\d+"
    r"|"
    r"\d+(?:\.\d+)?\s*(?:requests?|items?|users?|records?|transactions?|"
    r"messages?|events?)\s*(?:per\s+(?:second|minute|hour|day))?"
    r")",
    re.IGNORECASE,
)
_UX_CONSTRAINT = re.compile(
    r"(?:"
    r"\d+\s+steps?"
    r"|"
    r"(?:within|in|under|no more than)\s+\d+(?:\.\d+)?\s*"
    r"(?:seconds?|minutes?|steps?)"
    r")",
    re.IGNORECASE,
)
_AVAILABILITY_CONSTRAINT = re.compile(
    r"\d+(?:\.\d+)?\s*%|\b(?:uptime|sla)\b",
    re.IGNORECASE,
)
_SECURITY_CONSTRAINT = re.compile(
    r"\b(?:encrypt|encryption|authenticate|authentication|authorize|"
    r"authorization|password|tls|https|oauth|mfa|rbac)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\bnot\s+$", re.IGNORECASE)


@dataclass(frozen=True)
class IndicatorRule:
    """One semantic class of potentially vague wording."""

    category: str
    ambiguity_type: AmbiguityType
    severity: IssueSeverity
    reason: str
    patterns: tuple[str, ...]
    skip_collocations: tuple[str, ...] = ()
    clear_if: tuple[re.Pattern[str], ...] = ()
    require_no_nearby_number: bool = False
    replacement: str | None = None
    full_suggestion: str | None = None
    confidence: float = 0.95


@dataclass(frozen=True)
class LinguisticIssue:
    phrase: str
    start: int
    end: int
    ambiguity_type: AmbiguityType
    category: str
    reason: str
    suggestion: str
    severity: IssueSeverity
    confidence: float = 0.95
    source: str = "linguistic"
    replacement: str | None = None


# Configuration: add phrases/categories here rather than in the matching loop.
RULES: tuple[IndicatorRule, ...] = (
    IndicatorRule(
        category="unmeasurable_time",
        ambiguity_type="pragmatic",
        severity="high",
        reason="The term '{phrase}' does not define an objective response-time threshold.",
        patterns=(
            r"\bas\s+soon\s+as\s+possible\b",
            r"\bin\s+a\s+timely\s+manner\b",
            r"\breal(?:\s+|-)time\b",
            r"\bimmediately\b",
            r"\bpromptly\b",
            r"\bquickly\b",
            r"\brapidly\b",
            r"\bshortly\b",
            r"\basap\b",
            r"\bsoon\b",
        ),
        skip_collocations=("immediate mode",),
        clear_if=(_TIME_CONSTRAINT,),
        replacement="within [X] seconds",
    ),
    IndicatorRule(
        category="unclear_quantity",
        ambiguity_type="pragmatic",
        severity="high",
        reason="The term '{phrase}' does not define a measurable quantity.",
        patterns=(
            r"\b(?:a\s+number\s+of|numerous|several|many|few)\s+"
            r"(?:concurrent\s+)?(?:users?|requests?|items?|records?|customers?)",
            r"\ba\s+number\s+of\b",
            r"\bnumerous\b",
            r"\bsufficient\b",
            r"\badequate\b",
            r"\bseveral\b",
            r"\bmany\b",
            r"\blarge\b",
            r"\bsmall\b",
            r"\bfew\b",
        ),
        clear_if=(_QUANTITY_CONSTRAINT,),
        replacement="at least [X]",
    ),
    IndicatorRule(
        category="subjective_quality",
        ambiguity_type="pragmatic",
        severity="high",
        reason="The term '{phrase}' is a subjective quality with no testable acceptance criterion.",
        patterns=(
            r"\buser(?:\s+|-)friendly\b",
            r"\battractive\b",
            r"\bintuitive\b",
            r"\bconvenient\b",
            r"\beasily\b",
            r"\beasy\b",
            r"\bsimple\b",
        ),
        skip_collocations=(
            "simple object access",
            "simple mail transfer",
            "simple network management",
        ),
        clear_if=(_UX_CONSTRAINT,),
        replacement=(
            "that allows users to complete [specific task] "
            "in no more than [X] steps"
        ),
        full_suggestion=(
            "The system shall allow users to complete [specific task] "
            "in no more than [X] steps."
        ),
    ),
    IndicatorRule(
        category="vague_degree",
        ambiguity_type="pragmatic",
        severity="medium",
        reason="The term '{phrase}' is not tied to a measurable threshold.",
        patterns=(
            r"\breasonable\b",
            r"\bappropriate\b",
            r"\bappropriately\b",
            r"\befficiently\b",
            r"\befficient\b",
            r"\beffective\b",
            r"\breliable\b",
            r"\bflexible\b",
            r"\brobust\b",
            r"\bbetter\b",
            r"\bhigh\b",
            r"\blow\b",
            r"\bfast\b",
        ),
        skip_collocations=(
            "high-level",
            "high level",
            "low-level",
            "low level",
            "fast fourier",
            "fastcgi",
            "high-order",
            "higher-order",
        ),
        clear_if=(),
        require_no_nearby_number=True,
        replacement="meeting [specify measurable threshold]",
    ),
    IndicatorRule(
        category="open_ended",
        ambiguity_type="pragmatic",
        severity="medium",
        reason="The requirement leaves the set of cases or items open-ended.",
        patterns=(
            r"\band\s+so\s+on\b",
            r"\bwhenever\s+necessary\b",
            r"\bwhere\s+possible\b",
            r"\bas\s+appropriate\b",
            r"\bas\s+needed\b",
            r"\bif\s+necessary\b",
            r"\betc\.?",
        ),
        replacement="[specify remaining items]",
        confidence=0.88,
    ),
    IndicatorRule(
        category="vague_frequency",
        ambiguity_type="pragmatic",
        severity="high",
        reason="The term '{phrase}' does not define a measurable frequency.",
        patterns=(
            r"\bfrequently\b",
            r"\brarely\b",
            r"\boften\b",
            r"\bsometimes\b",
        ),
        replacement="at least [X] times per [time period]",
    ),
    IndicatorRule(
        category="unmeasurable_availability",
        ambiguity_type="pragmatic",
        severity="high",
        reason=(
            "The term '{phrase}' does not define the expected availability "
            "level or a measurable condition."
        ),
        patterns=(r"\bavailability\b", r"\bavailable\b"),
        skip_collocations=("available in memory", "available disk"),
        clear_if=(_AVAILABILITY_CONSTRAINT,),
        replacement="able to maintain [X]% availability during each calendar month",
        full_suggestion=(
            "The system shall maintain [X]% availability during each calendar month."
        ),
    ),
    IndicatorRule(
        category="unmeasurable_quality",
        ambiguity_type="pragmatic",
        severity="high",
        reason=(
            "The term '{phrase}' is too broad to test. Specify the concrete "
            "control or acceptance criterion."
        ),
        patterns=(r"\bsecure\b", r"\bsecurity\b"),
        skip_collocations=(
            "security log",
            "security group",
            "secure socket",
            "secure sockets",
        ),
        clear_if=(_SECURITY_CONSTRAINT,),
        replacement="protected using [specify security control]",
    ),
)


def detect_linguistic_issues(requirement: str) -> list[LinguisticIssue]:
    """Return context-aware wording issues. Empty if none survive the checks."""
    if not requirement or not requirement.strip():
        return []

    issues: list[LinguisticIssue] = []
    occupied: list[tuple[int, int]] = []
    lowered = requirement.lower()

    for rule in RULES:
        if any(pattern.search(requirement) for pattern in rule.clear_if):
            continue
        compiled = [
            (pattern, re.compile(pattern, re.IGNORECASE)) for pattern in rule.patterns
        ]
        compiled.sort(key=lambda item: len(item[0]), reverse=True)
        for _, regex in compiled:
            for match in regex.finditer(requirement):
                start, end = match.start(), match.end()
                if _overlaps(start, end, occupied):
                    continue
                if _negated(requirement, start):
                    continue
                if _in_collocation(lowered, start, end, rule.skip_collocations):
                    continue
                if rule.require_no_nearby_number and _nearby_number(
                    requirement, start, end
                ):
                    continue
                if rule.category == "vague_degree" and _locally_constrained(
                    requirement, start, end
                ):
                    continue
                phrase = requirement[start:end]
                replacement = _replacement_for(requirement, start, end, rule)
                suggestion = _suggestion_for(
                    requirement, start, end, rule, replacement
                )
                reason = rule.reason.format(phrase=phrase)
                issues.append(
                    LinguisticIssue(
                        phrase=phrase,
                        start=start,
                        end=end,
                        ambiguity_type=rule.ambiguity_type,
                        category=rule.category,
                        reason=reason,
                        suggestion=suggestion,
                        severity=rule.severity,
                        confidence=rule.confidence,
                        replacement=replacement,
                    )
                )
                occupied.append((start, end))

    issues.sort(key=lambda item: item.start)
    return issues


def _overlaps(start: int, end: int, occupied: list[tuple[int, int]]) -> bool:
    return any(not (end <= left or start >= right) for left, right in occupied)


def _negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 12) : start]
    return bool(_NEGATION.search(prefix))


def _in_collocation(
    lowered: str, start: int, end: int, collocations: tuple[str, ...]
) -> bool:
    window = lowered[max(0, start - 24) : min(len(lowered), end + 24)]
    return any(item in window for item in collocations)


def _nearby_number(text: str, start: int, end: int, radius: int = 40) -> bool:
    window = text[max(0, start - radius) : min(len(text), end + radius)]
    return bool(re.search(r"\d", window))


def _locally_constrained(text: str, start: int, end: int, radius: int = 72) -> bool:
    window = text[max(0, start - radius) : min(len(text), end + radius)]
    return bool(_TIME_CONSTRAINT.search(window) or _QUANTITY_CONSTRAINT.search(window))


def _replacement_for(
    requirement: str, start: int, end: int, rule: IndicatorRule
) -> str | None:
    phrase = requirement[start:end].lower()
    if rule.category == "unclear_quantity" and "user" in phrase:
        return "at least [N] concurrent users"
    if rule.category == "vague_degree" and phrase == "fast":
        return "within [X] seconds"
    if rule.category == "unmeasurable_availability" and re.search(
        r"\bbe\s+available\b", requirement, re.IGNORECASE
    ):
        return None
    return rule.replacement


def _suggestion_for(
    requirement: str,
    start: int,
    end: int,
    rule: IndicatorRule,
    replacement: str | None = None,
) -> str:
    if rule.category == "subjective_quality" and rule.full_suggestion:
        if re.search(r"\binterface\b", requirement, re.IGNORECASE):
            rewritten = re.sub(
                r"\ba\s+user(?:\s+|-)friendly\s+interface\b",
                "an interface that allows users to complete [specific task] "
                "in no more than [X] steps",
                requirement,
                count=1,
                flags=re.IGNORECASE,
            )
            if rewritten != requirement:
                return _finish_sentence(rewritten)
            return rule.full_suggestion
        return rule.full_suggestion
    if rule.category == "unmeasurable_availability" and rule.full_suggestion:
        if re.search(r"\bbe\s+available\b", requirement, re.IGNORECASE):
            rewritten = re.sub(
                r"\bbe\s+available\b",
                "maintain [X]% availability during each calendar month",
                requirement,
                count=1,
                flags=re.IGNORECASE,
            )
            return _finish_sentence(rewritten)
        return rule.full_suggestion
    chosen = replacement if replacement is not None else rule.replacement
    if chosen:
        rewritten = requirement[:start] + chosen + requirement[end:]
        return _finish_sentence(rewritten)
    return _finish_sentence(requirement)


def _finish_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\bshould\b", "shall", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmust\b", "shall", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    if not cleaned.endswith("."):
        cleaned += "."
    return cleaned
