from __future__ import annotations

from backend.services.ambiguity_model import ModelPrediction
from backend.services.llm_analyzer import LlmPhrase, LlmReasoningResult
from backend.services.rewrite import RewriteService


class FakeModel:
    loaded = True

    def __init__(self, prediction: ModelPrediction) -> None:
        self.prediction = prediction

    def predict(self, requirement: str) -> ModelPrediction:
        return self.prediction


class FakeRewriteService(RewriteService):
    def __init__(
        self,
        text: str = "The system shall respond within [specify maximum response time].",
    ) -> None:
        self._text = text

    def rewrite(self, requirement: str, ambiguity_type: str | None = None) -> str:
        return self._text


class FakeLlmAnalyzer:
    """Injected LLM layer for tests. Does not call a provider."""

    def __init__(self, result: LlmReasoningResult | None = None) -> None:
        self.result = result or LlmReasoningResult.unavailable("Optional review skipped")
        self.calls = 0

    def analyze(self, *args, **kwargs) -> LlmReasoningResult:
        self.calls += 1
        return self.result


def llm_quickly_result(requirement: str = "The software should respond quickly.") -> LlmReasoningResult:
    start = requirement.lower().find("quickly")
    end = start + len("quickly") if start >= 0 else None
    start = start if start >= 0 else None
    return LlmReasoningResult(
        available=True,
        is_ambiguous=True,
        ambiguity_score=8.8,
        ambiguity_type="pragmatic",
        severity="high",
        confidence=0.94,
        explanation="The requirement uses an undefined time constraint.",
        phrases=[
            LlmPhrase(
                text="quickly",
                reason="The word does not define a measurable response-time limit.",
                suggestion="The software shall respond within [X] seconds.",
                start=start,
                end=end,
            )
        ],
    )
