"""Suggested requirement rewrite. LLM is optional; fallback is always available."""

from __future__ import annotations

import logging
import re

from backend.config import Settings, get_settings
from backend.services.linguistic_detector import LinguisticIssue, _finish_sentence
from backend.services.llm_analyzer import LlmReasoningResult
from backend.services.llm_client import complete_chat
from backend.services.requirement_text import infer_requirement_kind

logger = logging.getLogger(__name__)

REWRITE_SYSTEM_PROMPT = """You rewrite software requirements to remove ambiguity.

Hard rules:
- Return exactly ONE complete requirement sentence.
- Preserve the original intent, actor, action, and object.
- Change only the ambiguous portion of the sentence when possible.
- Do not concatenate suggestion templates or duplicate clauses.
- Do not invent numbers, SLAs, fields, or business rules that are not in the original.
- If a measurable value is missing, use a scoped placeholder such as
  [maximum response time], [maximum number of steps], [maximum number of concurrent users],
  [specific task], [specified view format], [target availability percentage],
  [measurement period], [security control], or [specify: what must be defined].
- Do NOT use vague meta-phrases such as "measurable acceptance criterion",
  "specific requirement", "appropriate criteria", or "specified criteria".
- Start with "The system shall" when appropriate.
- Return only the rewritten requirement. No quotes, labels, or commentary.
"""

_TYPE_HINTS = {
    "lexical": " Replace vague words with one defined term, or mark undefined terms in square brackets.",
    "syntactic": " Rephrase so the sentence has a single, unambiguous reading.",
    "semantic": " State the intended meaning in one testable way.",
    "syntax": " Rewrite as a complete 'The system shall ...' requirement.",
    "pragmatic": " Make unstated assumptions and acceptance criteria explicit, using named placeholders where the original omits values.",
}

_ARTIFACTS = (
    r"\ba\s+that\s+allows\b",
    r"\ban\s+that\s+allows\b",
    r"\bshall\s+shall\b",
    r"\bshall\s+i\b",
    r"\bi\s+want\b",
    r"\bi\s+need\b",
    r"\bthe system shall the system\b",
    r"\bwithin\s+within\b",
    r"\bthat\s+that\b",
    r"\ballows users to complete \[specific task\].*allows users to complete",
    r"\[\s*\]",
    r"\bshall\s+within\b",
    r"\bprovide\s+a\s+that\b",
)

_THIN_STEM = re.compile(
    r"^(?:the\s+)?(?:system|application|software)\s+shall(?:\s+be)?\.?$",
    re.IGNORECASE,
)

_BANNED_GENERIC_PHRASES = (
    r"\bmeasurable acceptance criterion\b",
    r"\bappropriate criteria\b",
    r"\bspecified criteria\b",
    r"\bspecific requirement\b",
)

_FORMAT_VAGUE = re.compile(
    r"\bin\s+an?\s+appropriate\s+format\b",
    re.IGNORECASE,
)


class RewriteService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def rewrite(self, requirement: str, ambiguity_type: str | None = None) -> str:
        llm_text = self._rewrite_with_llm(requirement, ambiguity_type)
        if llm_text:
            cleaned = _normalize_sentence(llm_text)
            if is_valid_suggestion(cleaned, requirement):
                return cleaned
        return _validated_or_safe(
            fallback_rewrite(requirement, ambiguity_type),
            requirement,
            [],
        )

    def _rewrite_with_llm(self, requirement: str, ambiguity_type: str | None) -> str | None:
        if not self._settings.llm_enabled:
            return None
        api_key = (self._settings.llm_api_key or "").strip()
        if not api_key:
            return None

        type_line = (
            f"Ambiguity type: {ambiguity_type}.{_TYPE_HINTS.get(ambiguity_type, '')}\n"
            if ambiguity_type
            else "The classifier marked this as clean; still make the wording more testable if it is vague.\n"
        )
        try:
            content = complete_chat(
                self._settings,
                REWRITE_SYSTEM_PROMPT,
                f"{type_line}Original requirement:\n{requirement}",
                json_mode=False,
            )
        except Exception:
            logger.warning("LLM rewrite failed; using fallback.", exc_info=False)
            return None

        cleaned = (content or "").strip().strip('"').strip("'")
        return cleaned or None


def compose_improved_requirement(
    requirement: str,
    issues: list[LinguisticIssue],
    llm: LlmReasoningResult | None = None,
    ambiguity_type: str | None = None,
    rewrite_service: RewriteService | None = None,
) -> str:
    """Build exactly one complete rewritten requirement from the original and issues."""
    candidates: list[str] = []
    if issues:
        candidates.extend(_context_aware_rule_rewrites(requirement, issues))
        if len(issues) > 1:
            candidates.append(_rewrite_from_issues(requirement, issues))
            candidates.append(_rewrite_all_spans(requirement, issues))
        for item in issues:
            if item.suggestion:
                candidates.append(item.suggestion)
    service = rewrite_service or RewriteService()
    llm_rewrite = service._rewrite_with_llm(requirement, ambiguity_type)
    if llm_rewrite:
        candidates.append(llm_rewrite)
    if issues:
        candidates.append(_rewrite_from_issues(requirement, issues))
        candidates.append(_category_sentence(requirement, issues))
    if llm and llm.available:
        for phrase in llm.phrases:
            if phrase.suggestion and _looks_complete(phrase.suggestion):
                candidates.append(phrase.suggestion)
    candidates.append(fallback_rewrite(requirement, ambiguity_type))
    if issues:
        candidates.append(_safe_fallback(requirement, issues))

    seen: set[str] = set()
    for candidate in candidates:
        cleaned = _normalize_sentence(candidate)
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        if is_valid_suggestion(cleaned, requirement):
            return cleaned
    return _safe_fallback(requirement, issues)


def fallback_rewrite(requirement: str, ambiguity_type: str | None = None) -> str:
    """Sentence-level fallback. Never splices phrase templates into the original."""
    text = _normalize_modals(requirement)
    if not issues_need_measure(text) and is_valid_suggestion(text, requirement):
        return text
    stem = _strip_subjective_words(text)
    kind = infer_requirement_kind(requirement)
    if kind == "usability":
        clause = "within [maximum completion time]"
    elif kind == "performance" or re.search(r"\brespond", requirement, re.I):
        clause = "within [maximum response time]"
    else:
        clause = "under [specify: conditions needed to verify this requirement]"
    if re.search(r"\bwithin\b", stem, re.IGNORECASE):
        return _normalize_sentence(stem)
    assembled = f"{stem.rstrip('.')} {clause}."
    return _normalize_sentence(assembled)


def is_valid_suggestion(text: str, original: str | None = None) -> bool:
    if not text or not text.strip():
        return False
    cleaned = text.strip()
    if not cleaned.endswith("."):
        return False
    if cleaned.count("[") != cleaned.count("]"):
        return False
    if cleaned.lower().count("the system shall") > 1:
        return False
    if not re.search(r"\bshall\b", cleaned, re.IGNORECASE):
        return False
    if not re.match(
        r"^(the\s+)?(system|application|software)\s+shall\b",
        cleaned,
        re.IGNORECASE,
    ):
        return False
    if re.search(r"\b(the|a|an|to|and|that|within|using)\.$", cleaned, re.IGNORECASE):
        return False
    if _THIN_STEM.match(cleaned.rstrip(".")):
        return False
    for pattern in _ARTIFACTS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return False
    if _has_duplicate_clause(cleaned):
        return False
    if original and _invents_numbers(original, cleaned):
        return False
    for pattern in _BANNED_GENERIC_PHRASES:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return False
    if re.search(r"\ban\s+format\b", cleaned, re.IGNORECASE):
        return False
    return True


def issues_need_measure(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:quickly|fast|easily|easy|simple|soon|promptly|rapidly|"
            r"user-friendly|appropriate|reasonable|sufficient)\b",
            text,
            re.IGNORECASE,
        )
    )


def _context_aware_rule_rewrites(
    requirement: str, issues: list[LinguisticIssue]
) -> list[str]:
    """Category-specific full-sentence rewrites (after span suggestions)."""
    out: list[str] = []
    categories = {item.category for item in issues}

    if _FORMAT_VAGUE.search(requirement):
        text = _FORMAT_VAGUE.sub("in a [specified view format]", requirement)
        out.append(_normalize_modals(text))

    if categories == {"unmeasurable_time"} or (
        "unmeasurable_time" in categories
        and len(categories) == 1
        and re.search(r"\brespond\b", requirement, re.IGNORECASE)
    ):
        out.append("The system shall respond within [maximum response time].")

    if "unclear_quantity" in categories and re.search(
        r"\b(?:many|large|numerous|several|few)\b", requirement, re.IGNORECASE
    ):
        user_quantity = re.search(
            r"\ba\s+(?:large|many|numerous|several|few)\s+number\s+of\s+users?\b",
            requirement,
            re.IGNORECASE,
        )
        if user_quantity:
            out.append(
                _normalize_modals(
                    requirement[: user_quantity.start()]
                    + "at least [maximum number of concurrent users]"
                    + requirement[user_quantity.end() :]
                )
            )
            return out
        stem = _stem_without_phrases(requirement, issues)
        if re.search(r"\buser", stem, re.IGNORECASE):
            out.append(
                _normalize_sentence(
                    f"{stem.rstrip('.')} at least [maximum number of concurrent users]."
                )
            )

    if "unmeasurable_availability" in categories or re.search(
        r"\bat all times\b", requirement, re.IGNORECASE
    ):
        out.append(
            "The system shall maintain [target availability percentage] "
            "availability during [measurement period]."
        )

    if "subjective_quality" in categories and re.search(
        r"\binterface\b", requirement, re.IGNORECASE
    ):
        out.append(
            "The system shall provide an interface that allows users to complete "
            "[specific task] in no more than [maximum number of steps]."
        )
    return out


def _rewrite_from_issues(requirement: str, issues: list[LinguisticIssue]) -> str:
    categories = {item.category for item in issues}
    if _FORMAT_VAGUE.search(requirement):
        return _normalize_modals(
            _FORMAT_VAGUE.sub("in a [specified view format]", requirement)
        )
    if categories == {"unmeasurable_availability"} or (
        "unmeasurable_availability" in categories and _thin_after_removal(requirement, issues)
    ):
        return (
            "The system shall maintain [target availability percentage] "
            "during [measurement period]."
        )
    if categories == {"unmeasurable_quality"} or (
        "unmeasurable_quality" in categories and _thin_after_removal(requirement, issues)
    ):
        return "The system shall protect [asset] using [security control]."
    if "subjective_quality" in categories and (
        re.search(r"\binterface\b", requirement, re.IGNORECASE)
        or _thin_after_removal(requirement, issues)
        or re.search(r"\bshall\s+be\s*$", _stem_without_phrases(requirement, issues), re.I)
    ):
        return (
            "The system shall provide an interface that allows users to complete "
            "[specific task] in no more than [maximum number of steps]."
        )

    stem = _stem_without_phrases(requirement, issues)
    clauses = _constraint_clauses(requirement, issues)
    return _assemble(stem, clauses)


def _rewrite_all_spans(requirement: str, issues: list[LinguisticIssue]) -> str:
    """Apply every detector replacement while retaining the original sentence."""
    text = requirement
    for item in sorted(issues, key=lambda issue: issue.start, reverse=True):
        replacement = item.replacement
        if not replacement:
            continue
        text = text[: item.start] + replacement + text[item.end :]
    return _normalize_modals(text)


def _category_sentence(requirement: str, issues: list[LinguisticIssue]) -> str:
    """Second-pass complete sentence if the first assembly is invalid."""
    categories = {item.category for item in issues}
    action = _core_action(requirement, issues)
    parts = [f"The system shall {action}" if action else "The system shall perform [specific task]"]
    if "unclear_quantity" in categories and "user" in _joined_phrases(issues, "unclear_quantity"):
        parts.append("for at least [maximum number of concurrent users]")
    elif "unclear_quantity" in categories and "request" in _joined_phrases(issues, "unclear_quantity"):
        parts.append("for at least [maximum number of requests]")
    elif "unclear_quantity" in categories:
        parts.append("for at least [maximum quantity]")
    if "unmeasurable_time" in categories:
        parts.append(_time_placeholder(requirement))
    if "subjective_quality" in categories:
        parts.append(
            "so users can complete [specific task] in no more than [maximum number of steps]"
        )
    if "vague_degree" in categories and not _FORMAT_VAGUE.search(requirement):
        parts.append("[specify: measurable threshold for this quality]")
    if "vague_frequency" in categories:
        parts.append("at [required frequency]")
    if "open_ended" in categories:
        parts.append("under [specified conditions]")
    if "unmeasurable_availability" in categories:
        return (
            "The system shall maintain [target availability percentage] "
            "during [measurement period]."
        )
    if "unmeasurable_quality" in categories:
        return "The system shall protect [asset] using [security control]."
    return _normalize_sentence(" ".join(parts) + ".")


def _constraint_clauses(
    requirement: str, issues: list[LinguisticIssue]
) -> list[tuple[str, str]]:
    categories = {item.category for item in issues}
    clauses: list[tuple[str, str]] = []
    if "unclear_quantity" in categories:
        phrases = _joined_phrases(issues, "unclear_quantity")
        if "user" in phrases:
            clauses.append(("quantity", "at least [maximum number of concurrent users]"))
        elif "request" in phrases:
            clauses.append(("quantity", "at least [maximum number of requests]"))
        else:
            clauses.append(("quantity", "at least [maximum quantity]"))
    if "unmeasurable_time" in categories:
        clauses.append(("time", _time_placeholder(requirement)))
    if "vague_frequency" in categories:
        clauses.append(("frequency", "at [required frequency]"))
    if "subjective_quality" in categories:
        clauses.append(
            (
                "usability",
                "that allows users to complete [specific task] in no more than [maximum number of steps]",
            )
        )
    if "vague_degree" in categories and not _FORMAT_VAGUE.search(requirement):
        clauses.append(
            ("quality", "[specify: measurable threshold for this quality]")
        )
    if "open_ended" in categories:
        clauses.append(("scope", "under [specified conditions]"))
    return clauses


def _time_placeholder(requirement: str) -> str:
    kind = infer_requirement_kind(requirement)
    if kind == "usability":
        return "within [maximum completion time]"
    return "within [maximum response time]"


def _assemble(stem: str, clauses: list[tuple[str, str]]) -> str:
    text = stem.rstrip(".")
    by_type = {key: value for key, value in clauses}

    if "quantity" in by_type:
        quantity = by_type["quantity"]
        if re.search(r"\b(support|process|handle|serve|allow)\s*$", text, re.IGNORECASE):
            text = f"{text} {quantity}"
        elif re.search(r"\b(users?|requests?|items?|records?|customers?)\s*$", text, re.I):
            text = re.sub(
                r"\b(users?|requests?|items?|records?|customers?)\s*$",
                quantity,
                text,
                flags=re.IGNORECASE,
            )
        elif quantity.lower() not in text.lower():
            text = f"{text} {quantity}"

    for key in ("usability", "quality", "time", "frequency", "scope"):
        clause = by_type.get(key)
        if clause and clause.lower() not in text.lower():
            text = f"{text} {clause}"

    return _normalize_sentence(text)


def _stem_without_phrases(requirement: str, issues: list[LinguisticIssue]) -> str:
    text = requirement
    for item in sorted(issues, key=lambda issue: issue.start, reverse=True):
        text = text[: item.start] + text[item.end :]
    text = _normalize_modals(text)
    text = _fix_articles(text)
    if not re.match(
        r"^(the\s+)?(system|application|software)\s+shall\b",
        text,
        re.IGNORECASE,
    ):
        remainder = text[0].lower() + text[1:] if text else text
        remainder = re.sub(
            r"^(the\s+)?(system|application|software)\s+",
            "",
            remainder,
            flags=re.IGNORECASE,
        )
        text = f"The system shall {remainder}"
    return text.rstrip(" .")


def _core_action(requirement: str, issues: list[LinguisticIssue]) -> str:
    stem = _stem_without_phrases(requirement, issues)
    action = re.sub(
        r"^(?:the\s+)?(?:system|application|software)\s+shall\s+",
        "",
        stem,
        flags=re.IGNORECASE,
    )
    action = re.sub(r"\s+", " ", action).strip(" .")
    return action


def _thin_after_removal(requirement: str, issues: list[LinguisticIssue]) -> bool:
    return bool(_THIN_STEM.match(_stem_without_phrases(requirement, issues)))


def _joined_phrases(issues: list[LinguisticIssue], category: str) -> str:
    return " ".join(item.phrase.lower() for item in issues if item.category == category)


def _normalize_modals(requirement: str) -> str:
    text = re.sub(r"\s+", " ", (requirement or "").strip()).rstrip(".")
    text = re.sub(r"\bshould\b", "shall", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmust\b", "shall", text, flags=re.IGNORECASE)
    if re.match(r"^(the\s+)?(system|application|software)\s+shall\b", text, re.I):
        return _finish_sentence(text)
    if re.search(r"\bshall\b", text, re.I):
        text = re.sub(
            r"^(?:the\s+)?\w+\s+shall\s+",
            "The system shall ",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        return _finish_sentence(text)
    remainder = text[0].lower() + text[1:] if text else text
    text = f"The system shall {remainder}"
    return _finish_sentence(text)


def _strip_subjective_words(text: str) -> str:
    cleaned = re.sub(
        r"\b(?:quickly|fast|easily|easy|simple|soon|promptly|rapidly|"
        r"user-friendly|appropriate|reasonable|sufficient)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return _fix_articles(_normalize_modals(cleaned)).rstrip(" .")


def _fix_articles(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\bin\s+an\s+format\b", "in a format", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\ban\s+format\b", "a format", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\ba\s+([aeiou])", r"an \1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    return cleaned


def _normalize_sentence(text: str) -> str:
    cleaned = _finish_sentence(_fix_articles(text or ""))
    cleaned = re.sub(r"\bshall\s+shall\b", "shall", cleaned, flags=re.IGNORECASE)
    return cleaned


def _looks_complete(text: str) -> bool:
    return bool(
        re.match(
            r"^(the\s+)?(system|application|software)\s+shall\b",
            text.strip(),
            re.IGNORECASE,
        )
    )


def _has_duplicate_clause(text: str) -> bool:
    words = re.findall(r"[a-z0-9\[\]]+", text.lower())
    if len(words) < 8:
        return False
    seen: set[tuple[str, ...]] = set()
    for index in range(len(words) - 3):
        gram = tuple(words[index : index + 4])
        if gram in seen:
            return True
        seen.add(gram)
    return False


def _invents_numbers(original: str, suggested: str) -> bool:
    original_nums = set(re.findall(r"\d+(?:\.\d+)?", original))
    suggested_nums = set(re.findall(r"\d+(?:\.\d+)?", suggested))
    return bool(suggested_nums - original_nums)


def _safe_fallback(requirement: str, issues: list[LinguisticIssue]) -> str:
    if any(item.category == "unmeasurable_availability" for item in issues):
        return (
            "The system shall maintain [target availability percentage] "
            "during [measurement period]."
        )
    if any(item.category == "unmeasurable_quality" for item in issues):
        return "The system shall protect [asset] using [security control]."
    action = _core_action(requirement, issues) if issues else ""
    if not action or _THIN_STEM.match(f"The system shall {action}"):
        action = "perform [specific task]"
    kind = infer_requirement_kind(requirement)
    if kind == "usability":
        return _normalize_sentence(
            f"The system shall {action} within [maximum completion time]."
        )
    if kind == "performance" or any(item.category == "unmeasurable_time" for item in issues):
        return _normalize_sentence(
            f"The system shall {action} within [maximum response time]."
        )
    if _FORMAT_VAGUE.search(requirement):
        return _normalize_modals(
            _FORMAT_VAGUE.sub("in a [specified view format]", requirement)
        )
    return _normalize_sentence(
        f"The system shall {action} under [specify: conditions needed to verify this requirement]."
    )


def _validated_or_safe(
    candidate: str, requirement: str, issues: list[LinguisticIssue]
) -> str:
    cleaned = _normalize_sentence(candidate)
    if is_valid_suggestion(cleaned, requirement):
        return cleaned
    return _safe_fallback(requirement, issues)
