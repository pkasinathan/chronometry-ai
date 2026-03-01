"""Tests for llm_backends.py module — backend routing and response parsing."""

import os
import sys
from unittest.mock import patch

import pytest


from chronometry.llm_backends import (
    _parse_openai_text_response,
    call_text_api,
    call_vision_api,
)

# ---------------------------------------------------------------------------
# Vision API routing
# ---------------------------------------------------------------------------


class TestVisionRouting:
    """Tests for call_vision_api provider routing."""

    @patch("chronometry.llm_backends.call_ollama_vision")
    def test_routes_to_ollama(self, mock_fn):
        mock_fn.return_value = {"summary": "ollama", "sources": []}
        config = {
            "annotation": {
                "screenshot_analysis_prompt": "t",
                "local_model": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "model_name": "qwen2.5vl:7b",
                    "timeout_sec": 60,
                },
            }
        }
        result = call_vision_api([], config)
        mock_fn.assert_called_once()
        assert result["summary"] == "ollama"

    @patch("chronometry.llm_backends.call_openai_vision")
    def test_routes_to_openai_compatible(self, mock_fn):
        mock_fn.return_value = {"summary": "vllm", "sources": []}
        config = {
            "annotation": {
                "screenshot_analysis_prompt": "t",
                "local_model": {
                    "provider": "openai_compatible",
                    "base_url": "http://localhost:8000",
                    "model_name": "qwen",
                    "timeout_sec": 60,
                },
            }
        }
        result = call_vision_api([], config)
        mock_fn.assert_called_once()
        assert result["summary"] == "vllm"

    def test_unknown_provider_raises(self):
        config = {
            "annotation": {
                "screenshot_analysis_prompt": "t",
                "local_model": {"provider": "unknown"},
            }
        }
        with pytest.raises(ValueError, match="unknown"):
            call_vision_api([], config)

    def test_defaults_to_ollama(self):
        config = {
            "annotation": {
                "screenshot_analysis_prompt": "t",
                "local_model": {},
            }
        }
        with patch("chronometry.llm_backends.call_ollama_vision") as mock_fn:
            mock_fn.return_value = {"summary": "default", "sources": []}
            result = call_vision_api([], config)
            mock_fn.assert_called_once()


# ---------------------------------------------------------------------------
# Text API routing
# ---------------------------------------------------------------------------


class TestTextRouting:
    """Tests for call_text_api provider routing."""

    @patch("chronometry.llm_backends.call_ollama_text")
    def test_routes_to_ollama(self, mock_fn):
        mock_fn.return_value = {"content": "ok", "tokens": 10, "prompt_tokens": 5, "completion_tokens": 5}
        config = {
            "digest": {
                "local_model": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "model_name": "q",
                    "timeout_sec": 60,
                },
            }
        }
        result = call_text_api("hello", config)
        mock_fn.assert_called_once()
        assert result["content"] == "ok"

    @patch("chronometry.llm_backends.call_openai_text")
    def test_routes_to_openai_compatible(self, mock_fn):
        mock_fn.return_value = {"content": "oai", "tokens": 10, "prompt_tokens": 5, "completion_tokens": 5}
        config = {
            "digest": {
                "local_model": {
                    "provider": "openai_compatible",
                    "base_url": "http://localhost:8000",
                    "model_name": "q",
                    "timeout_sec": 60,
                },
            }
        }
        result = call_text_api("hello", config)
        mock_fn.assert_called_once()

    def test_unknown_provider_raises(self):
        config = {"digest": {"local_model": {"provider": "bad"}}}
        with pytest.raises(ValueError, match="bad"):
            call_text_api("hello", config)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestParseOpenAITextResponse:
    """Tests for _parse_openai_text_response."""

    def test_extracts_content_and_tokens(self):
        response = {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20},
        }
        config = {"root_dir": "/tmp/test"}
        result = _parse_openai_text_response(response, config)
        assert result["content"] == "hello"
        assert result["tokens"] == 50

    def test_handles_missing_choices(self):
        config = {"root_dir": "/tmp/test"}
        result = _parse_openai_text_response({"usage": {}}, config)
        assert "Error" in result["content"]
        assert result["tokens"] == 0

    def test_handles_empty_choices(self):
        config = {"root_dir": "/tmp/test"}
        result = _parse_openai_text_response({"choices": []}, config)
        assert "Error" in result["content"]

    def test_handles_missing_usage(self):
        response = {"choices": [{"message": {"content": "ok"}}]}
        config = {"root_dir": "/tmp/test"}
        result = _parse_openai_text_response(response, config)
        assert result["content"] == "ok"
        assert result["tokens"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
