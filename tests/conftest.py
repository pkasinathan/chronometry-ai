"""Shared pytest fixtures for Chronometry tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture()
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def isolate_chronometry_home(tmp_path, monkeypatch):
    """Ensure tests never touch the real ~/.chronometry directory."""
    test_home = tmp_path / ".chronometry"
    test_home.mkdir()
    monkeypatch.setattr("chronometry.CHRONOMETRY_HOME", test_home)
    monkeypatch.setattr("chronometry.common.CHRONOMETRY_HOME", test_home)


@pytest.fixture()
def sample_config(tmp_path: Path) -> dict[str, Any]:
    """Minimal valid configuration for testing."""
    root_dir = tmp_path / "data"
    root_dir.mkdir()
    (root_dir / "frames").mkdir()

    return {
        "root_dir": str(root_dir),
        "capture": {
            "capture_interval_seconds": 900,
            "monitor_index": 1,
            "retention_days": 30,
        },
        "annotation": {
            "backend": "local",
            "annotation_mode": "manual",
            "screenshot_analysis_batch_size": 1,
            "json_suffix": ".json",
            "screenshot_analysis_prompt": "Describe the activity.",
            "local_model": {
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "model_name": "qwen3-vl:8b",
                "fallback_model_name": "qwen2.5vl:7b",
                "timeout_sec": 300,
                "max_retries": 3,
            },
        },
        "timeline": {
            "bucket_minutes": 30,
            "exclude_keywords": [],
            "gap_minutes": 30,
        },
        "digest": {
            "backend": "local",
            "interval_seconds": 3600,
            "system_prompt": "Summarize work activities.",
        },
        "notifications": {
            "enabled": False,
            "notify_before_capture": False,
            "pre_capture_warning_seconds": 0,
            "pre_capture_sound": False,
        },
        "categories": {
            "focus_keywords": ["code", "development"],
            "distraction_keywords": ["social", "youtube"],
        },
    }


@pytest.fixture()
def frames_dir(sample_config: dict[str, Any]) -> Path:
    """Return the frames directory from sample config, creating date sub-dir."""
    frames = Path(sample_config["root_dir"]) / "frames"
    today = Path(sample_config["root_dir"]) / "frames" / "2026-02-27"
    today.mkdir(parents=True, exist_ok=True)
    return today
