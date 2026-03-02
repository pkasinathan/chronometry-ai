"""LLM backend abstraction for Chronometry.

Supports local vision/text models via:
  - Ollama (default, with auto-start and crash recovery)
  - OpenAI-compatible APIs (vLLM, LM Studio, llama.cpp, etc.)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time

import requests

from chronometry.token_usage import TokenUsageTracker

logger = logging.getLogger(__name__)

_inference_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Ollama lifecycle management
# ---------------------------------------------------------------------------


def _is_ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """Quick health check against the Ollama server."""
    try:
        resp = requests.get(base_url, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def _find_ollama_bin() -> str | None:
    """Locate the ollama binary."""
    path = shutil.which("ollama")
    if path:
        return path
    for candidate in ("/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _start_ollama(ollama_bin: str, base_url: str, start_timeout: int = 30) -> bool:
    """Spawn ``ollama serve`` and wait for it to become reachable.

    Returns True if the server became reachable within the timeout.
    """
    logger.info(f"Starting Ollama via {ollama_bin} serve …")
    try:
        subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        return False

    deadline = time.monotonic() + start_timeout
    while time.monotonic() < deadline:
        if _is_ollama_reachable(base_url):
            logger.info("Ollama is now running")
            return True
        time.sleep(1)

    logger.warning(f"Ollama did not become reachable within {start_timeout}s")
    return False


def ensure_ollama_running(base_url: str = "http://localhost:11434", start_timeout: int = 30) -> None:
    """Start Ollama if it is not already running."""
    if _is_ollama_reachable(base_url):
        return

    ollama_bin = _find_ollama_bin()
    if ollama_bin is None:
        logger.error("Ollama binary not found -- cannot auto-start the server")
        return

    logger.info(f"Ollama not reachable at {base_url}")
    _start_ollama(ollama_bin, base_url, start_timeout)


def _restart_ollama(base_url: str = "http://localhost:11434", start_timeout: int = 30) -> bool:
    """Kill the running Ollama server and start a fresh one.

    Used to recover from GPU runner crashes (e.g. Metal
    kIOGPUCommandBufferCallbackErrorImpactingInteractivity).
    """
    ollama_bin = _find_ollama_bin()
    if ollama_bin is None:
        logger.error("Ollama binary not found -- cannot restart")
        return False

    logger.info("Restarting Ollama to recover from server error …")
    try:
        subprocess.run(["pkill", "-x", "ollama"], capture_output=True, timeout=5)
    except Exception:
        pass
    time.sleep(2)
    return _start_ollama(ollama_bin, base_url, start_timeout)


class ModelNotFoundError(RuntimeError):
    """Raised when Ollama returns 404 for a model that isn't pulled."""

    def __init__(self, model_name: str, message: str):
        self.model_name = model_name
        super().__init__(message)


def _pull_ollama_model(base_url: str, model_name: str, timeout: int = 600) -> bool:
    """Pull an Ollama model via the API. Returns True on success."""
    logger.info(f"Auto-pulling Ollama model '{model_name}' — this may take several minutes …")
    try:
        resp = requests.post(
            f"{base_url}/api/pull",
            json={"name": model_name, "stream": False},
            timeout=timeout,
        )
        if resp.ok:
            logger.info(f"Successfully pulled model '{model_name}'")
            return True
        logger.error(f"Failed to pull model '{model_name}': {resp.status_code} {resp.text[:200]}")
    except requests.Timeout:
        logger.error(f"Timeout pulling model '{model_name}' (>{timeout}s)")
    except Exception as e:
        logger.error(f"Error pulling model '{model_name}': {e}")
    return False


def _raise_or_restart_ollama(response: requests.Response, base_url: str) -> None:
    """Inspect an Ollama HTTP response; restart the server on runner crashes.

    If the response is successful this is a no-op.  On a 500 whose body
    mentions a runner crash, Ollama is restarted and a clear exception is
    raised so the caller's retry loop can try again with a healthy server.
    For 404 model-not-found errors, raises ``ModelNotFoundError`` so the
    caller can attempt an auto-pull.
    For other errors, raise with the server's error message included.
    """
    if response.ok:
        return

    try:
        body = response.json()
        error_msg = body.get("error", response.text)
    except Exception:
        error_msg = response.text

    runner_crash = response.status_code == 500 and "no longer running" in error_msg

    if runner_crash:
        logger.warning(f"Ollama runner crashed: {error_msg}")
        _restart_ollama(base_url)
        raise RuntimeError(f"Ollama runner crashed (restarted): {error_msg}")

    if response.status_code == 404 and "not found" in error_msg.lower():
        raise ModelNotFoundError("", error_msg)

    raise requests.HTTPError(
        f"{response.status_code} Ollama error: {error_msg}",
        response=response,
    )


# ---------------------------------------------------------------------------
# Ollama backends
# ---------------------------------------------------------------------------


def call_ollama_vision(
    images: list[dict], config: dict, prompt_override: str | None = None, model_override: str | None = None
) -> dict:
    """Call Ollama vision model with base64 images.

    Args:
        images: List of image dicts with base64_data and content_type
        config: Configuration dictionary
        prompt_override: If set, use this prompt instead of the one in config
        model_override: If set, use this model instead of the one in config

    Returns:
        {"summary": str, "sources": list}
    """
    if len(images) > 1:
        logger.warning(f"Multiple images ({len(images)}) passed; using only the first for memory safety")
        images = images[:1]

    local_config = config["annotation"].get("local_model", {})
    base_url = local_config.get("base_url", "http://localhost:11434")
    model_name = model_override or local_config.get("model_name", "qwen3-vl:8b")
    timeout = local_config.get("timeout_sec", 300)
    keep_alive = local_config.get("keep_alive", "1m")

    ensure_ollama_running(base_url)

    prompt = (
        prompt_override
        or config["annotation"].get("screenshot_analysis_prompt")
        or config["annotation"].get("prompt", "")
    )

    logger.info(f"Ollama vision: POST {base_url}/api/chat model={model_name} images={len(images)}")

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt, "images": [img["base64_data"] for img in images]}],
        "stream": False,
        "think": False,
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    with _inference_lock:
        response = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)

    try:
        _raise_or_restart_ollama(response, base_url)
    except ModelNotFoundError:
        if _pull_ollama_model(base_url, model_name):
            with _inference_lock:
                response = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
            _raise_or_restart_ollama(response, base_url)
        else:
            raise requests.HTTPError(
                f"Model '{model_name}' not found and auto-pull failed. Run: ollama pull {model_name}",
                response=response,
            )

    data = response.json()

    summary = data.get("message", {}).get("content", "")
    logger.info(f"Ollama vision response: {len(summary)} chars")
    return {"summary": summary, "sources": []}


def call_ollama_text(
    prompt: str,
    config: dict,
    max_tokens: int | None = None,
    system_prompt: str | None = None,
    context: str | None = None,
) -> dict:
    """Call Ollama text model for completion.

    Returns:
        {"content": str, "tokens": int, "prompt_tokens": int, "completion_tokens": int}
    """
    local_config = config.get("digest", {}).get("local_model", {})
    base_url = local_config.get("base_url", "http://localhost:11434")
    model_name = local_config.get("model_name", "qwen3:8b")
    timeout = local_config.get("timeout_sec", 300)
    keep_alive = local_config.get("keep_alive", "1m")

    ensure_ollama_running(base_url)

    digest_config = config.get("digest", {})
    if system_prompt is None:
        system_prompt = digest_config.get(
            "system_prompt", "You are an AI assistant that creates concise, professional summaries of work activities."
        )

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

    options = {}
    if max_tokens is not None:
        options["num_predict"] = max_tokens

    logger.info(f"Ollama text: POST {base_url}/api/chat model={model_name}")

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": options,
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    response = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)

    try:
        _raise_or_restart_ollama(response, base_url)
    except ModelNotFoundError:
        if _pull_ollama_model(base_url, model_name):
            response = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
            _raise_or_restart_ollama(response, base_url)
        else:
            raise requests.HTTPError(
                f"Model '{model_name}' not found and auto-pull failed. Run: ollama pull {model_name}",
                response=response,
            )

    data = response.json()

    content = data.get("message", {}).get("content", "")
    prompt_tokens = data.get("prompt_eval_count", 0)
    completion_tokens = data.get("eval_count", 0)
    total_tokens = prompt_tokens + completion_tokens

    logger.info(
        f"Ollama text response: {len(content)} chars, {total_tokens} tokens ({prompt_tokens}+{completion_tokens})"
    )

    if total_tokens > 0:
        _track_tokens(config, total_tokens, prompt_tokens, completion_tokens, context)

    return {
        "content": content,
        "tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


# ---------------------------------------------------------------------------
# OpenAI-compatible backends (vLLM, LM Studio, llama.cpp, etc.)
# ---------------------------------------------------------------------------


def call_openai_vision(
    images: list[dict], config: dict, prompt_override: str | None = None, model_override: str | None = None
) -> dict:
    """Call an OpenAI-compatible vision endpoint with base64 images.

    Args:
        images: List of image dicts with base64_data and content_type
        config: Configuration dictionary
        prompt_override: If set, use this prompt instead of the one in config
        model_override: If set, use this model instead of the one in config

    Returns:
        {"summary": str, "sources": list}
    """
    if len(images) > 1:
        logger.warning(f"Multiple images ({len(images)}) passed; using only the first for memory safety")
        images = images[:1]

    local_config = config["annotation"].get("local_model", {})
    base_url = local_config.get("base_url", "http://localhost:8000")
    model_name = model_override or local_config.get("model_name", "Qwen/Qwen3-VL-8B-Instruct")
    timeout = local_config.get("timeout_sec", 300)

    prompt = (
        prompt_override
        or config["annotation"].get("screenshot_analysis_prompt")
        or config["annotation"].get("prompt", "")
    )

    logger.info(
        f"OpenAI-compatible vision: POST {base_url}/v1/chat/completions model={model_name} images={len(images)}"
    )

    content_parts = [{"type": "text", "text": prompt}]
    for img in images:
        content_type = img.get("content_type", "image/png")
        content_parts.append(
            {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{img['base64_data']}"}}
        )

    with _inference_lock:
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": content_parts}],
                "max_tokens": 512,
            },
            timeout=timeout,
        )
    response.raise_for_status()
    data = response.json()

    choices = data.get("choices", [])
    if choices:
        summary = choices[0].get("message", {}).get("content", "")
    else:
        logger.error(f"Unexpected vision API response (no choices): {data}")
        summary = ""
    return {"summary": summary, "sources": []}


def call_openai_text(
    prompt: str,
    config: dict,
    max_tokens: int | None = None,
    system_prompt: str | None = None,
    context: str | None = None,
) -> dict:
    """Call an OpenAI-compatible text completion endpoint.

    Returns:
        {"content": str, "tokens": int, "prompt_tokens": int, "completion_tokens": int}
    """
    local_config = config.get("digest", {}).get("local_model", {})
    base_url = local_config.get("base_url", "http://localhost:8000")
    model_name = local_config.get("model_name", "Qwen/Qwen3-8B-Instruct")
    timeout = local_config.get("timeout_sec", 300)

    digest_config = config.get("digest", {})
    if max_tokens is None:
        max_tokens = digest_config.get("max_tokens_default", 500)
    if system_prompt is None:
        system_prompt = digest_config.get(
            "system_prompt", "You are an AI assistant that creates concise, professional summaries of work activities."
        )

    logger.info(f"OpenAI-compatible text: POST {base_url}/v1/chat/completions model={model_name}")

    response = requests.post(
        f"{base_url}/v1/chat/completions",
        json={
            "model": model_name,
            "temperature": digest_config.get("temperature", 0.7),
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return _parse_openai_text_response(data, config, context)


# ---------------------------------------------------------------------------
# Router functions
# ---------------------------------------------------------------------------


def call_vision_api(
    images: list[dict], config: dict, prompt_override: str | None = None, model_override: str | None = None
) -> dict:
    """Route a vision (image summarization) call to the configured backend.

    Args:
        images: List of image dicts with base64_data and content_type
        config: Configuration dictionary
        prompt_override: If set, use this prompt instead of the one in config
        model_override: If set, use this model instead of the one in config

    Returns:
        {"summary": str, "sources": list}
    """
    from chronometry.runtime_stats import stats

    provider = config["annotation"].get("local_model", {}).get("provider", "ollama")
    logger.info(f"Vision API provider: {provider}")

    stats.record("llm.vision_calls")
    try:
        if provider == "ollama":
            result = call_ollama_vision(images, config, prompt_override=prompt_override, model_override=model_override)
        elif provider == "openai_compatible":
            result = call_openai_vision(images, config, prompt_override=prompt_override, model_override=model_override)
        else:
            raise ValueError(f"Unknown vision provider: {provider}")
        stats.record("llm.vision_succeeded")
        return result
    except Exception:
        stats.record("llm.vision_failed")
        raise


def call_text_api(
    prompt: str,
    config: dict,
    max_tokens: int | None = None,
    system_prompt: str | None = None,
    context: str | None = None,
) -> dict:
    """Route a text completion call to the configured backend.

    Returns:
        {"content": str, "tokens": int, "prompt_tokens": int, "completion_tokens": int}
    """
    from chronometry.runtime_stats import stats

    provider = config.get("digest", {}).get("local_model", {}).get("provider", "ollama")
    logger.info(f"Text API provider: {provider}")

    stats.record("llm.text_calls")
    try:
        if provider == "ollama":
            result = call_ollama_text(prompt, config, max_tokens, system_prompt, context)
        elif provider == "openai_compatible":
            result = call_openai_text(prompt, config, max_tokens, system_prompt, context)
        else:
            raise ValueError(f"Unknown text provider: {provider}")

        if not result.get("content") and result.get("tokens", 0) > 0:
            stats.record("llm.text_empty_content")
            logger.warning(
                f"Text LLM returned empty content with {result['tokens']} tokens (likely thinking-mode exhaustion)"
            )

        stats.record("llm.text_succeeded")
        return result
    except Exception:
        stats.record("llm.text_failed")
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_openai_text_response(response: dict, config: dict, context: str | None = None) -> dict:
    """Parse an OpenAI-format chat completion response into our standard shape."""
    if "choices" in response and len(response["choices"]) > 0:
        content = response["choices"][0]["message"]["content"]
    else:
        logger.error(f"Unexpected API response: {response}")
        return {"content": "Error: Invalid API response", "tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}

    usage = response.get("usage", {})
    total_tokens = usage.get("total_tokens", 0)
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    if total_tokens > 0:
        _track_tokens(config, total_tokens, prompt_tokens, completion_tokens, context)

    return {
        "content": content,
        "tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def _track_tokens(config: dict, total: int, prompt: int, completion: int, context: str | None = None):
    """Log token usage to the tracker."""
    try:
        tracker = TokenUsageTracker(config["root_dir"])
        tracker.log_tokens(
            api_type="digest", tokens=total, prompt_tokens=prompt, completion_tokens=completion, context=context
        )
    except Exception as e:
        logger.warning(f"Failed to track token usage: {e}")
