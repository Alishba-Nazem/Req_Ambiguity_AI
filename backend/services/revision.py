"""Accept / edit / dismiss decisions for a suggested rewrite."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuggestionDecision:
    status: str
    suggestion: str
    edited_text: str | None = None


def apply_decisions(
    original: str,
    combined_suggestion: str | None,
    decisions: list[SuggestionDecision],
) -> str:
    """Return the requirement after accept/edit/dismiss actions.

    Dismissed issues keep the original wording. An edited text wins.
    If every remaining issue is accepted, the combined suggestion is used
    so multiple phrases in one sentence are rewritten together.
    """
    remaining = [item for item in decisions if item.status != "dismissed"]
    if not remaining:
        return original
    edited = next(
        (
            item.edited_text
            for item in remaining
            if item.status == "edited" and item.edited_text
        ),
        None,
    )
    if edited:
        return edited
    applied = [item for item in remaining if item.status in {"accepted", "edited"}]
    if not applied:
        return original
    if all(item.status in {"accepted", "edited"} for item in remaining):
        return combined_suggestion or applied[0].suggestion
    return applied[0].suggestion
