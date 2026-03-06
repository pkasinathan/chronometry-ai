"""OS metadata capture for Chronometry.

Collects active application, window title, browser URL, and workspace path
using macOS AppleScript via osascript. All functions are fault-tolerant and
return sensible defaults on failure.
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

_SENSITIVE_PARAMS = frozenset(
    {
        "token",
        "key",
        "secret",
        "auth",
        "session",
        "code",
        "access_token",
        "api_key",
        "apikey",
        "password",
        "credential",
        "jwt",
        "refresh_token",
        "client_secret",
        "state",
        "nonce",
        "id_token",
        "authorization",
    }
)


def _strip_sensitive_url_params(url: str) -> str:
    """Remove query parameters whose names suggest authentication credentials."""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in params.items() if k.lower() not in _SENSITIVE_PARAMS}
        cleaned = parsed._replace(query=urlencode(filtered, doseq=True))
        return urlunparse(cleaned)
    except Exception:
        return url


def _run_osascript(script: str, timeout: float = 2.0) -> str | None:
    """Run an AppleScript snippet and return its stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.debug(f"osascript timed out: {script[:60]}...")
    except Exception as e:
        logger.debug(f"osascript failed: {e}")
    return None


def get_active_app() -> str | None:
    """Return the name of the frontmost application."""
    return _run_osascript(
        'tell application "System Events" to get name of first application process whose frontmost is true'
    )


def get_front_window_title() -> str | None:
    """Return the title of the front window of the active application."""
    return _run_osascript(
        'tell application "System Events" to get name of front window of '
        "first application process whose frontmost is true"
    )


def get_chrome_url(active_app: str | None = None) -> str | None:
    """Return the URL of Chrome's active tab, or None if Chrome is not frontmost.

    Args:
        active_app: Pre-fetched active app name to avoid a redundant AppleScript call.
                    If None, fetches it internally.
    """
    if active_app is None:
        active_app = get_active_app()
    if active_app and "chrome" not in active_app.lower():
        return None
    return _run_osascript('tell application "Google Chrome" to get URL of active tab of front window')


def get_workspace_path(window_title: str | None = None) -> str | None:
    """Infer a workspace/file path from the front window title.

    Looks for common IDE title patterns like "filename — ProjectName" or
    absolute paths like "/Users/.../file.py".

    Args:
        window_title: Pre-fetched window title to avoid a redundant AppleScript call.
                      If None, fetches it internally.
    """
    if window_title is None:
        window_title = get_front_window_title()
    if not window_title:
        return None

    path_match = re.search(r"(/[\w./-]+)", window_title)
    if path_match:
        return path_match.group(1)

    if " — " in window_title:
        parts = window_title.split(" — ")
        return parts[-1].strip() if len(parts) > 1 else None
    if " - " in window_title:
        parts = window_title.split(" - ")
        return parts[-1].strip() if len(parts) > 1 else None

    return None


def capture_metadata() -> dict:
    """Capture all available OS metadata and return as a structured dict.

    Every sub-call is wrapped in try/except so a single failure never blocks
    the rest of the metadata or the capture pipeline.

    Pre-fetched values are reused to minimize subprocess calls (3-4 instead of 6).
    """
    metadata: dict = {"timestamp": datetime.now().isoformat()}

    active_app = None
    try:
        active_app = get_active_app()
        metadata["active_app"] = active_app
    except Exception as e:
        logger.debug(f"Failed to get active app: {e}")
        metadata["active_app"] = None

    window_title = None
    try:
        window_title = get_front_window_title()
        metadata["window_title"] = window_title
    except Exception as e:
        logger.debug(f"Failed to get window title: {e}")
        metadata["window_title"] = None

    try:
        raw_url = get_chrome_url(active_app=active_app)
        metadata["url"] = _strip_sensitive_url_params(raw_url) if raw_url else None
    except Exception as e:
        logger.debug(f"Failed to get Chrome URL: {e}")
        metadata["url"] = None

    try:
        metadata["workspace"] = get_workspace_path(window_title=window_title)
    except Exception as e:
        logger.debug(f"Failed to get workspace path: {e}")
        metadata["workspace"] = None

    return metadata
