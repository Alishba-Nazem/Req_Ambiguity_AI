import pytest

from backend.config import get_settings
from backend.tests.fakes import FakeLlmAnalyzer, FakeModel, FakeRewriteService

__all__ = ["FakeLlmAnalyzer", "FakeModel", "FakeRewriteService"]


@pytest.fixture(autouse=True)
def isolate_llm_settings(monkeypatch):
    """Keep default tests on the BERT + linguistic path."""
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
