import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.config import Settings
from backend.services.ambiguity_model import ModelPrediction
from backend.services.llm_analyzer import (
    LLM_DISABLED,
    LLM_UNAVAILABLE,
    LlmAnalyzer,
    locate_phrase_span,
    map_ambiguity_type,
    parse_llm_json,
)
from backend.services.linguistic_detector import detect_linguistic_issues


def _enabled_settings(**kwargs) -> Settings:
    values = {
        "llm_enabled": True,
        "llm_provider": "openai",
        "llm_api_key": "sk-test-not-a-real-key",
        "llm_model": "gpt-4o-mini",
        "llm_timeout_seconds": 5.0,
        "llm_max_output_tokens": 200,
    }
    values.update(kwargs)
    return Settings(**values)


def _quickly_payload() -> dict:
    return {
        "is_ambiguous": True,
        "ambiguity_score": 8.5,
        "ambiguity_type": "pragmatic",
        "severity": "high",
        "ambiguous_phrases": [
            {
                "text": "quickly",
                "reason": "The word does not define a measurable response-time limit.",
                "suggestion": "The software shall respond within [X] seconds.",
            }
        ],
        "explanation": "The requirement uses an undefined time constraint.",
        "confidence": 0.94,
    }


def test_locate_phrase_span_is_exact():
    text = "The software should respond quickly."
    span = locate_phrase_span(text, "quickly")
    assert span is not None
    start, end = span
    assert text[start:end] == "quickly"


def test_locate_phrase_does_not_cover_whole_sentence():
    text = "The software should respond quickly."
    assert locate_phrase_span(text, text) is None


def test_map_ambiguity_type_uses_project_taxonomy():
    assert map_ambiguity_type("pragmatic") == "pragmatic"
    assert map_ambiguity_type("syntax") == "syntax"
    assert map_ambiguity_type("clean") is None
    assert map_ambiguity_type("invented") is None


def test_parse_llm_json_rejects_invalid_payload():
    with pytest.raises(Exception):
        parse_llm_json("not-json")
    with pytest.raises(Exception):
        parse_llm_json('{"is_ambiguous": "yes"}')


def test_disabled_llm_does_not_call_provider():
    analyzer = LlmAnalyzer(Settings(llm_enabled=False, llm_api_key="sk-test-not-a-real-key"))
    with patch("backend.services.llm_client.httpx.Client") as client_cls:
        result = analyzer.analyze(
            "The software should respond quickly.",
            None,
            [],
            None,
        )
    assert result.available is False
    assert result.reason == LLM_DISABLED
    client_cls.assert_not_called()


def test_missing_key_is_unavailable_without_http():
    analyzer = LlmAnalyzer(Settings(llm_enabled=True, llm_api_key=""))
    with patch("backend.services.llm_client.httpx.Client") as client_cls:
        result = analyzer.analyze("The software should respond quickly.", None, [], None)
    assert result.available is False
    assert result.reason == LLM_UNAVAILABLE
    client_cls.assert_not_called()


def _mock_client(content: str | Exception):
    client = MagicMock()
    if isinstance(content, Exception):
        client.post.side_effect = content
    else:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": content}}]}
        client.post.return_value = response
    context = MagicMock()
    context.__enter__.return_value = client
    context.__exit__.return_value = False
    return context, client


def test_valid_structured_response_locates_quickly():
    text = "The software should respond quickly."
    context, client = _mock_client(json.dumps(_quickly_payload()))
    analyzer = LlmAnalyzer(_enabled_settings())
    prediction = ModelPrediction(
        classification="clean",
        ambiguity_type=None,
        ambiguity_score=40,
        confidence=0.56,
    )
    issues = detect_linguistic_issues(text)
    with patch("backend.services.llm_client.httpx.Client", return_value=context):
        result = analyzer.analyze(text, prediction, issues, None)
    assert result.available is True
    assert result.is_ambiguous is True
    assert result.ambiguity_type == "pragmatic"
    assert result.phrases[0].text.lower() == "quickly"
    assert text[result.phrases[0].start : result.phrases[0].end].lower() == "quickly"
    assert client.post.call_count == 1
    payload = json.dumps(client.post.call_args.kwargs["json"])
    assert "sk-test-not-a-real-key" not in payload
    assert "Authorization" in client.post.call_args.kwargs["headers"]


def test_invalid_llm_json_returns_unavailable():
    context, _client = _mock_client("this is not json {")
    analyzer = LlmAnalyzer(_enabled_settings())
    with patch("backend.services.llm_client.httpx.Client", return_value=context):
        result = analyzer.analyze("The software should respond quickly.", None, [], None)
    assert result.available is False
    assert result.reason == LLM_UNAVAILABLE


def test_gemini_provider_calls_generate_content():
    text = "The software should respond quickly."
    client = MagicMock()
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(_quickly_payload())}],
                }
            }
        ]
    }
    client.post.return_value = response
    context = MagicMock()
    context.__enter__.return_value = client
    context.__exit__.return_value = False
    analyzer = LlmAnalyzer(
        _enabled_settings(llm_provider="gemini", llm_model="your-model")
    )
    with patch("backend.services.llm_client.httpx.Client", return_value=context):
        result = analyzer.analyze(text, None, [], None)
    assert result.available is True
    url = client.post.call_args.args[0]
    assert "generateContent" in url
    assert "gemini-2.0-flash" in url
    headers = client.post.call_args.kwargs["headers"]
    assert "x-goog-api-key" in headers
    assert "Authorization" not in headers
    payload = json.dumps(client.post.call_args.kwargs["json"])
    assert "sk-test-not-a-real-key" not in payload


def test_timeout_returns_unavailable():
    context, _client = _mock_client(httpx.TimeoutException("timed out"))
    analyzer = LlmAnalyzer(_enabled_settings())
    with patch("backend.services.llm_client.httpx.Client", return_value=context):
        result = analyzer.analyze("The software should respond quickly.", None, [], None)
    assert result.available is False
    assert result.reason == LLM_UNAVAILABLE
    assert "timed out" not in (result.reason or "")
