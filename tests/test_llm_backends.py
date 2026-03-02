"""Tests for llm_backends.py module — backend routing and response parsing."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

from chronometry.llm_backends import (
    ModelNotFoundError,
    _parse_openai_text_response,
    _pull_ollama_model,
    _raise_or_restart_ollama,
    call_ollama_text,
    call_ollama_vision,
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


# ---------------------------------------------------------------------------
# Model not found / auto-pull
# ---------------------------------------------------------------------------


class TestRaiseOrRestartOllama:
    """Tests for _raise_or_restart_ollama error classification."""

    def _make_response(self, status_code, json_body=None, text=""):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = status_code
        resp.ok = 200 <= status_code < 300
        resp.text = text
        if json_body is not None:
            resp.json.return_value = json_body
        else:
            resp.json.side_effect = ValueError("no json")
        return resp

    def test_ok_response_is_noop(self):
        resp = self._make_response(200)
        _raise_or_restart_ollama(resp, "http://localhost:11434")

    def test_404_model_not_found_raises_model_not_found_error(self):
        resp = self._make_response(404, {"error": "model 'qwen2.5:7b' not found"})
        with pytest.raises(ModelNotFoundError):
            _raise_or_restart_ollama(resp, "http://localhost:11434")

    @patch("chronometry.llm_backends._restart_ollama")
    def test_500_runner_crash_restarts(self, mock_restart):
        resp = self._make_response(500, {"error": "model is no longer running"})
        with pytest.raises(RuntimeError, match="runner crashed"):
            _raise_or_restart_ollama(resp, "http://localhost:11434")
        mock_restart.assert_called_once()

    def test_other_error_raises_http_error(self):
        resp = self._make_response(400, {"error": "bad request"})
        with pytest.raises(requests.HTTPError, match="bad request"):
            _raise_or_restart_ollama(resp, "http://localhost:11434")


class TestPullOllamaModel:
    """Tests for _pull_ollama_model."""

    @patch("chronometry.llm_backends.requests.post")
    def test_successful_pull(self, mock_post):
        mock_post.return_value = MagicMock(ok=True)
        assert _pull_ollama_model("http://localhost:11434", "qwen2.5:7b") is True

    @patch("chronometry.llm_backends.requests.post")
    def test_failed_pull(self, mock_post):
        resp = MagicMock(ok=False, status_code=500, text="server error")
        mock_post.return_value = resp
        assert _pull_ollama_model("http://localhost:11434", "qwen2.5:7b") is False

    @patch("chronometry.llm_backends.requests.post")
    def test_timeout_pull(self, mock_post):
        mock_post.side_effect = requests.Timeout("timed out")
        assert _pull_ollama_model("http://localhost:11434", "qwen2.5:7b") is False

    @patch("chronometry.llm_backends.requests.post")
    def test_connection_error_pull(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")
        assert _pull_ollama_model("http://localhost:11434", "qwen2.5:7b") is False


class TestOllamaTextAutoPull:
    """Tests for call_ollama_text auto-pull on model not found."""

    @pytest.fixture
    def text_config(self):
        return {
            "root_dir": "/tmp/test",
            "digest": {
                "system_prompt": "You are a test assistant.",
                "local_model": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "model_name": "qwen2.5:7b",
                    "timeout_sec": 60,
                },
            },
        }

    @patch("chronometry.llm_backends.ensure_ollama_running")
    @patch("chronometry.llm_backends.requests.post")
    def test_success_without_pull(self, mock_post, mock_ensure, text_config):
        """Normal case: model exists, no pull needed."""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "summary text"},
            "prompt_eval_count": 10,
            "eval_count": 20,
        }
        mock_post.return_value = mock_resp

        result = call_ollama_text("test prompt", text_config)
        assert result["content"] == "summary text"
        assert mock_post.call_count == 1

    @patch("chronometry.llm_backends.ensure_ollama_running")
    @patch("chronometry.llm_backends._pull_ollama_model", return_value=True)
    @patch("chronometry.llm_backends.requests.post")
    def test_auto_pull_on_404_then_success(self, mock_post, mock_pull, mock_ensure, text_config):
        """Model not found on first try, auto-pull succeeds, retry succeeds."""
        not_found_resp = MagicMock(spec=requests.Response)
        not_found_resp.ok = False
        not_found_resp.status_code = 404
        not_found_resp.json.return_value = {"error": "model 'qwen2.5:7b' not found"}
        not_found_resp.text = "model 'qwen2.5:7b' not found"

        ok_resp = MagicMock(spec=requests.Response)
        ok_resp.ok = True
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "message": {"content": "pulled and ready"},
            "prompt_eval_count": 5,
            "eval_count": 15,
        }

        mock_post.side_effect = [not_found_resp, ok_resp]

        result = call_ollama_text("test prompt", text_config)
        assert result["content"] == "pulled and ready"
        mock_pull.assert_called_once_with("http://localhost:11434", "qwen2.5:7b")
        assert mock_post.call_count == 2

    @patch("chronometry.llm_backends.ensure_ollama_running")
    @patch("chronometry.llm_backends._pull_ollama_model", return_value=False)
    @patch("chronometry.llm_backends.requests.post")
    def test_auto_pull_fails_raises_http_error(self, mock_post, mock_pull, mock_ensure, text_config):
        """Model not found and auto-pull fails — raises HTTPError with actionable message."""
        not_found_resp = MagicMock(spec=requests.Response)
        not_found_resp.ok = False
        not_found_resp.status_code = 404
        not_found_resp.json.return_value = {"error": "model 'qwen2.5:7b' not found"}
        not_found_resp.text = "model 'qwen2.5:7b' not found"

        mock_post.return_value = not_found_resp

        with pytest.raises(requests.HTTPError, match="auto-pull failed"):
            call_ollama_text("test prompt", text_config)
        mock_pull.assert_called_once()


class TestOllamaVisionAutoPull:
    """Tests for call_ollama_vision auto-pull on model not found."""

    @pytest.fixture
    def vision_config(self):
        return {
            "annotation": {
                "screenshot_analysis_prompt": "Describe the activity.",
                "local_model": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "model_name": "qwen2.5vl:7b",
                    "timeout_sec": 60,
                },
            },
        }

    @patch("chronometry.llm_backends.ensure_ollama_running")
    @patch("chronometry.llm_backends._pull_ollama_model", return_value=True)
    @patch("chronometry.llm_backends.requests.post")
    def test_auto_pull_on_404_then_success(self, mock_post, mock_pull, mock_ensure, vision_config):
        """Vision model not found, auto-pull succeeds, retry succeeds."""
        not_found_resp = MagicMock(spec=requests.Response)
        not_found_resp.ok = False
        not_found_resp.status_code = 404
        not_found_resp.json.return_value = {"error": "model 'qwen2.5vl:7b' not found"}
        not_found_resp.text = "model 'qwen2.5vl:7b' not found"

        ok_resp = MagicMock(spec=requests.Response)
        ok_resp.ok = True
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"message": {"content": "activity description"}}

        mock_post.side_effect = [not_found_resp, ok_resp]

        images = [{"base64_data": "abc123", "content_type": "image/jpeg"}]
        result = call_ollama_vision(images, vision_config)
        assert result["summary"] == "activity description"
        mock_pull.assert_called_once_with("http://localhost:11434", "qwen2.5vl:7b")

    @patch("chronometry.llm_backends.ensure_ollama_running")
    @patch("chronometry.llm_backends._pull_ollama_model", return_value=False)
    @patch("chronometry.llm_backends.requests.post")
    def test_auto_pull_fails_raises_http_error(self, mock_post, mock_pull, mock_ensure, vision_config):
        """Vision model not found and auto-pull fails — raises HTTPError."""
        not_found_resp = MagicMock(spec=requests.Response)
        not_found_resp.ok = False
        not_found_resp.status_code = 404
        not_found_resp.json.return_value = {"error": "model 'qwen2.5vl:7b' not found"}
        not_found_resp.text = "model 'qwen2.5vl:7b' not found"

        mock_post.return_value = not_found_resp

        images = [{"base64_data": "abc123", "content_type": "image/jpeg"}]
        with pytest.raises(requests.HTTPError, match="auto-pull failed"):
            call_ollama_vision(images, vision_config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
